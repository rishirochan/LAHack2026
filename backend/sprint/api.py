"""FastAPI app for sprint backend features."""

import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from urllib.parse import quote
from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from backend.shared.db import close_database, get_media_store, get_session_repository, init_database
from backend.shared.db.repository import DEFAULT_USER_ID
from backend.sprint.phase_a.graph import build_initial_state, phase_a_graph
from backend.sprint.phase_a.schemas import (
    ContinueSessionRequest,
    ContinueSessionResponse,
    SessionSummaryResponse,
    StartSessionRequest,
    StartSessionResponse,
)
from backend.sprint.phase_a.session_manager import get_session_manager
from backend.sprint.phase_b.schemas import (
    ChunkUploadMeta,
    SessionStateResponse,
    StartConversationRequest,
    StartConversationResponse,
)
from backend.sprint.phase_b.graph import critique_graph, end_graph, prompt_graph
from backend.sprint.phase_b.session_manager import get_phase_b_manager
from backend.sprint.phase_c.constants import (
    PHASE_C_MAX_SECONDS,
    PHASE_C_MIN_SECONDS,
    RETRY_EMPTY_MESSAGE as PHASE_C_RETRY_EMPTY_MESSAGE,
    RETRY_INVALID_CHUNKS_MESSAGE as PHASE_C_RETRY_INVALID_CHUNKS_MESSAGE,
)
from backend.sprint.phase_c.graph import phase_c_graph
from backend.sprint.phase_c.schemas import (
    PhaseCSessionStateResponse,
    StartPhaseCSessionRequest,
    StartPhaseCSessionResponse,
)
from backend.sprint.phase_c.session_manager import get_phase_c_manager


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await init_database()
    try:
        yield
    finally:
        await close_database()


app = FastAPI(title="LAHacks 2026 Backend", lifespan=lifespan)

PHASE_B_MIN_SECONDS = 2
PHASE_B_MAX_SECONDS = 45
RETRY_TOO_SHORT_MESSAGE = "That recording was too short. Try again with a full response."
RETRY_EMPTY_MESSAGE = "The recording was empty. Check camera and microphone access."
RETRY_INVALID_CHUNKS_MESSAGE = "Some recording chunks were missing or overlapped. Please record that turn again."
PHASE_A_MEDIA_KINDS = {"video", "audio"}
PHASE_B_MEDIA_KINDS = {"video", "audio"}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/sessions/recent")
async def list_recent_sessions(
    user_id: str = Query(default=DEFAULT_USER_ID),
    limit: int = Query(default=10, ge=1, le=50),
) -> dict[str, object]:
    """Return recent persisted practice sessions for dashboard history."""

    sessions = await get_session_repository().list_recent_sessions(
        user_id=user_id,
        limit=limit,
    )
    return {"sessions": [_to_session_preview(session) for session in sessions]}


@app.get("/api/users/{user_id}/trends")
async def get_user_trends(user_id: str) -> dict[str, object]:
    """Return analytics trends calculated across a user's persisted sessions."""

    return await get_session_repository().get_user_trends(user_id=user_id)


@app.get("/api/sessions/{session_id}/chunks")
async def list_session_chunks(session_id: str) -> dict[str, object]:
    """Return normalized chunk analytics for one persisted session."""

    chunks = await get_session_repository().list_session_chunks(session_id)
    return {"session_id": session_id, "chunks": chunks}


@app.get("/api/sessions/{session_id}")
async def get_persisted_session(session_id: str) -> dict[str, object]:
    """Return one persisted session document."""

    session = await get_session_repository().get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session was not found.")
    return session


def _to_session_preview(session: dict) -> dict[str, object]:
    summary = session.get("summary") if isinstance(session.get("summary"), dict) else {}
    setup = session.get("setup") if isinstance(session.get("setup"), dict) else {}
    mode = str(session.get("mode") or "")
    label = "Practice Session"
    score = None

    if mode == "phase_a":
        label = str(setup.get("target_emotion") or "Emotion Drill")
        scores = summary.get("match_scores") if isinstance(summary, dict) else None
        if isinstance(scores, list) and scores:
            score = round(float(sum(scores) / len(scores)) * 100)
    elif mode == "phase_b":
        label = str(setup.get("scenario") or "Conversation").replace("_", " ").title()

    return {
        "session_id": session.get("session_id"),
        "mode": session.get("mode"),
        "mode_label": session.get("mode_label"),
        "label": label,
        "status": session.get("status"),
        "created_at": session.get("created_at"),
        "updated_at": session.get("updated_at"),
        "completed_at": session.get("completed_at"),
        "score": score,
        "total_turns": summary.get("total_turns") if isinstance(summary, dict) else None,
        "round_count": len(summary.get("rounds", [])) if isinstance(summary.get("rounds"), list) else None,
    }


@app.post("/api/phase-a/sessions", response_model=StartSessionResponse)
async def start_phase_a_session(request: StartSessionRequest) -> StartSessionResponse:
    """Start a background LangGraph run for a new Phase A session."""

    initial_state = build_initial_state(
        target_emotion=request.target_emotion,
    )
    session = get_session_manager().create_session(dict(initial_state))
    task = asyncio.create_task(_run_phase_a_graph(session.session_id, initial_state))
    get_session_manager().set_task(session.session_id, task)
    return StartSessionResponse(session_id=session.session_id)


@app.websocket("/api/phase-a/ws/{session_id}")
async def phase_a_websocket(websocket: WebSocket, session_id: str) -> None:
    """Keep one websocket open for the full Phase A session."""

    try:
        await get_session_manager().bind_websocket(session_id, websocket)
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        get_session_manager().unbind_websocket(session_id)
    except RuntimeError:
        await websocket.close(code=1008)


@app.post("/api/phase-a/sessions/{session_id}/recording")
async def submit_phase_a_recording(
    session_id: str,
    video_file: UploadFile = File(...),
    audio_file: UploadFile = File(...),
    duration_seconds: float = Form(...),
) -> dict[str, str]:
    """Receive recording blobs and unblock the graph's await_recording node."""

    try:
        if duration_seconds < 2:
            await get_session_manager().send_event(
                session_id,
                "retry_recording",
                {"message": "That recording was too short. Try again with a full response."},
            )
            return {"status": "retry"}

        round_index = get_session_manager().get_next_round_index(session_id)
        video_upload = await _save_media_upload(
            video_file,
            storage_key=_phase_a_storage_key(
                session_id,
                round_index,
                "video",
                _upload_suffix(video_file, ".webm"),
            ),
        )
        audio_upload = await _save_media_upload(
            audio_file,
            storage_key=_phase_a_storage_key(
                session_id,
                round_index,
                "audio",
                _upload_suffix(audio_file, ".wav"),
            ),
        )
        if int(video_upload.get("size_bytes") or 0) == 0 or int(audio_upload.get("size_bytes") or 0) == 0:
            await get_session_manager().send_event(
                session_id,
                "retry_recording",
                {"message": "The recording was empty. Check camera and microphone access."},
            )
            return {"status": "retry"}

        get_session_manager().submit_recording(session_id, video_upload, audio_upload)
        return {"status": "accepted"}
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post(
    "/api/phase-a/sessions/{session_id}/continue",
    response_model=ContinueSessionResponse,
)
async def continue_phase_a_session(
    session_id: str,
    request: ContinueSessionRequest,
) -> ContinueSessionResponse:
    """Submit the user's try-again/end-session choice."""

    try:
        get_session_manager().submit_continue(session_id, request.continue_session)
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return ContinueSessionResponse(
        session_id=session_id,
        continue_session=request.continue_session,
    )


@app.get(
    "/api/phase-a/sessions/{session_id}/summary",
    response_model=SessionSummaryResponse,
)
async def get_phase_a_summary(session_id: str) -> SessionSummaryResponse:
    """Return in-memory summary data for the active session."""

    try:
        return get_session_manager().get_summary(session_id)
    except RuntimeError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.get("/api/phase-a/sessions/{session_id}/rounds/{round_index}/{media_kind}")
async def download_phase_a_media(session_id: str, round_index: int, media_kind: str) -> StreamingResponse:
    """Download one persisted Phase A recording artifact."""

    if media_kind not in PHASE_A_MEDIA_KINDS:
        raise HTTPException(status_code=404, detail="Phase A media type was not found.")
    session = await get_session_repository().get_session(session_id)
    media_ref = _find_phase_a_media_ref(session, round_index, media_kind)
    return await _build_media_response(media_ref)


async def _save_media_upload(
    upload: UploadFile,
    *,
    storage_key: str,
) -> dict[str, object]:
    data = await upload.read()
    if not data:
        return {
            "file_id": None,
            "storage_key": storage_key,
            "filename": Path(storage_key).name,
            "original_filename": upload.filename or Path(storage_key).name,
            "mime_type": upload.content_type or "application/octet-stream",
            "size_bytes": 0,
            "uploaded_at": datetime.now(UTC).isoformat(),
        }

    stored_upload = await get_media_store().save_media(
        data=data,
        storage_key=storage_key,
        original_filename=upload.filename or Path(storage_key).name,
        mime_type=upload.content_type or "application/octet-stream",
    )
    return {
        **stored_upload,
        "download_url": None,
    }


async def _save_upload(upload: UploadFile, *, suffix: str) -> str:
    """Persist an upload to a temp file for background-only integrations."""

    with NamedTemporaryFile(delete=False, suffix=suffix) as output:
        data = await upload.read()
        output.write(data)
        return output.name


def _phase_a_storage_key(session_id: str, round_index: int, media_kind: str, suffix: str) -> str:
    return f"phase_a/{session_id}/round_{round_index}/{media_kind}{suffix}"


def _upload_suffix(upload: UploadFile, fallback: str) -> str:
    suffix = Path(upload.filename or "").suffix.lower()
    return suffix or fallback


def _phase_b_chunk_storage_key(
    session_id: str,
    turn_index: int,
    chunk_index: int,
    media_kind: str,
    suffix: str,
) -> str:
    return f"phase_b/{session_id}/turn_{turn_index}/chunk_{chunk_index}_{media_kind}{suffix}"


def _phase_b_transcript_storage_key(session_id: str, turn_index: int, suffix: str) -> str:
    return f"phase_b/{session_id}/turn_{turn_index}/transcript_audio{suffix}"


def _find_phase_a_media_ref(session: dict[str, object] | None, round_index: int, media_kind: str) -> dict[str, object]:
    if not isinstance(session, dict):
        raise HTTPException(status_code=404, detail="Session was not found.")
    for media_ref in session.get("media_refs") or []:
        if not isinstance(media_ref, dict):
            continue
        if _index_value(media_ref.get("round_index")) != round_index:
            continue
        if media_ref.get("kind") != media_kind:
            continue
        return media_ref
    raise HTTPException(status_code=404, detail="Phase A media was not found.")


def _find_phase_b_chunk_media_ref(
    session: dict[str, object] | None,
    turn_index: int,
    chunk_index: int,
    media_kind: str,
) -> dict[str, object]:
    if not isinstance(session, dict):
        raise HTTPException(status_code=404, detail="Session was not found.")
    expected_kind = f"{media_kind}_upload"
    for media_ref in session.get("media_refs") or []:
        if not isinstance(media_ref, dict):
            continue
        if _index_value(media_ref.get("turn_index")) != turn_index:
            continue
        if _index_value(media_ref.get("chunk_index")) != chunk_index:
            continue
        if media_ref.get("kind") != expected_kind:
            continue
        return media_ref
    raise HTTPException(status_code=404, detail="Phase B chunk media was not found.")


def _find_phase_b_transcript_media_ref(session: dict[str, object] | None, turn_index: int) -> dict[str, object]:
    if not isinstance(session, dict):
        raise HTTPException(status_code=404, detail="Session was not found.")
    for media_ref in session.get("media_refs") or []:
        if not isinstance(media_ref, dict):
            continue
        if _index_value(media_ref.get("turn_index")) != turn_index:
            continue
        if media_ref.get("kind") != "turn_transcript_audio":
            continue
        return media_ref
    raise HTTPException(status_code=404, detail="Phase B transcript audio was not found.")


async def _build_media_response(media_ref: dict[str, object]) -> StreamingResponse:
    upload = media_ref.get("upload")
    if not isinstance(upload, dict):
        raise HTTPException(status_code=404, detail="Media upload metadata was not found.")
    file_id = upload.get("file_id")
    if not file_id:
        raise HTTPException(status_code=404, detail="Media file identifier was not found.")
    iterator = get_media_store().iter_media(file_id=str(file_id))
    try:
        first_chunk = await anext(iterator)
    except StopAsyncIteration:
        first_chunk = b""
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    async def stream_media():
        if first_chunk:
            yield first_chunk
        async for chunk in iterator:
            yield chunk

    response = StreamingResponse(
        stream_media(),
        media_type=str(upload.get("mime_type") or "application/octet-stream"),
    )
    filename = str(upload.get("original_filename") or upload.get("filename") or "media.bin")
    response.headers["Content-Disposition"] = f'attachment; filename="{quote(filename)}"'
    return response


def _public_phase_b_turn(session_id: str, turn: object) -> dict[str, object] | None:
    if not isinstance(turn, dict):
        return None

    public_turn = dict(turn)
    transcript_upload = turn.get("transcript_audio_upload")
    if isinstance(transcript_upload, dict):
        public_turn["transcript_audio_upload"] = _public_upload_ref(
            upload=transcript_upload,
            download_url=(
                f"/api/phase-b/sessions/{session_id}/turns/{int(turn.get('turn_index') or 0)}/transcript-audio"
            ),
        )

    public_chunks: list[dict[str, object]] = []
    for chunk in turn.get("chunks") or []:
        if not isinstance(chunk, dict):
            continue
        public_chunk = dict(chunk)
        chunk_index = int(chunk.get("chunk_index") or 0)
        for media_kind in PHASE_B_MEDIA_KINDS:
            upload_key = f"{media_kind}_upload"
            upload = chunk.get(upload_key)
            if isinstance(upload, dict):
                public_chunk[upload_key] = _public_upload_ref(
                    upload=upload,
                    download_url=(
                        f"/api/phase-b/sessions/{session_id}/turns/{int(turn.get('turn_index') or 0)}"
                        f"/chunks/{chunk_index}/{media_kind}"
                    ),
                )
        public_chunks.append(public_chunk)
    public_turn["chunks"] = public_chunks
    return public_turn


def _public_upload_ref(
    *,
    upload: dict[str, object],
    download_url: str,
) -> dict[str, object]:
    return {
        "file_id": upload.get("file_id"),
        "storage_key": upload.get("storage_key"),
        "filename": upload.get("filename"),
        "original_filename": upload.get("original_filename"),
        "mime_type": upload.get("mime_type"),
        "size_bytes": upload.get("size_bytes"),
        "uploaded_at": upload.get("uploaded_at"),
        "download_url": download_url,
    }


def _index_value(value: object) -> int:
    if value is None:
        return -1
    return int(value)


async def _run_phase_a_graph(session_id: str, initial_state: dict) -> None:
    try:
        final_state = await phase_a_graph.ainvoke(
            initial_state,
            config={"configurable": {"session_id": session_id}},
        )
        get_session_manager().store_state(session_id, final_state)
    except Exception as error:
        await get_session_manager().send_event(
            session_id,
            "error",
            {"message": f"Phase A session stopped unexpectedly: {error}"},
        )


# ======================================================================
# Phase B — Long-form AI Conversation
# ======================================================================

@app.post("/api/phase-b/sessions", response_model=StartConversationResponse)
async def start_phase_b_session(request: StartConversationRequest) -> StartConversationResponse:
    """Create a new Phase B conversation session."""

    session = get_phase_b_manager().create_session(
        scenario=request.scenario,
        difficulty=request.difficulty,
        max_turns=request.max_turns,
    )
    return StartConversationResponse(session_id=session.session_id)


@app.get("/api/phase-b/sessions/{session_id}", response_model=SessionStateResponse)
async def get_phase_b_session(session_id: str) -> SessionStateResponse:
    """Return the full session state for a Phase B conversation."""

    try:
        state = get_phase_b_manager().get_state(session_id)
    except RuntimeError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    return SessionStateResponse(
        session_id=state["session_id"],
        scenario=state["scenario"],
        difficulty=state["difficulty"],
        persona=state["persona"],
        turn_index=state["turn_index"],
        max_turns=state["max_turns"],
        conversation_history=state["conversation_history"],
        current_turn=_public_phase_b_turn(session_id, state.get("current_turn")),
        turns=[turn for turn in (_public_phase_b_turn(session_id, turn) for turn in state["turns"]) if turn],
        status=state["status"],
    )


@app.websocket("/api/phase-b/ws/{session_id}")
async def phase_b_websocket(websocket: WebSocket, session_id: str) -> None:
    """Keep one websocket open for the full Phase B session."""

    try:
        await get_phase_b_manager().bind_websocket(session_id, websocket)
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        get_phase_b_manager().unbind_websocket(session_id)
    except RuntimeError:
        await websocket.close(code=1008)


@app.post("/api/phase-b/sessions/{session_id}/turns/next")
async def phase_b_next_turn(session_id: str) -> dict[str, str]:
    """Generate the next AI prompt and stream it as TTS over the websocket.

    This runs the ``prompt_graph`` LangGraph subgraph which calls Gemma via
    OpenRouter, then streams the result through ElevenLabs TTS.
    """

    try:
        state = get_phase_b_manager().get_state(session_id)
    except RuntimeError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    if state["status"] != "active":
        raise HTTPException(status_code=409, detail="Session is not active.")
    if state["turn_index"] >= state["max_turns"]:
        raise HTTPException(status_code=409, detail="All turns have been completed.")

    # Run generate_prompt subgraph (sends events over websocket)
    await prompt_graph.ainvoke(
        state,
        config={"configurable": {"session_id": session_id}},
    )

    # Stream TTS of the prompt over websocket
    updated = get_phase_b_manager().get_state(session_id)
    current = updated.get("current_turn")
    if current and current.get("prompt_text"):
        from backend.sprint.phase_b.elevenlabs import stream_tts_chunks
        from backend.shared.ai import get_ai_service

        await get_phase_b_manager().send_event(
            session_id,
            "tts_start",
            {"audio_type": "prompt", "text": current["prompt_text"]},
        )
        async for chunk in stream_tts_chunks(ai_service=get_ai_service(), text=current["prompt_text"]):
            await get_phase_b_manager().send_event(
                session_id,
                "audio_chunk",
                {"audio_type": "prompt", "chunk": chunk, "mime_type": "audio/mpeg"},
            )
        await get_phase_b_manager().send_event(
            session_id, "tts_end", {"audio_type": "prompt"},
        )

    # Signal frontend that recording can begin
    await get_phase_b_manager().send_event(
        session_id,
        "recording_ready",
        {"max_seconds": PHASE_B_MAX_SECONDS, "turn_index": updated["turn_index"]},
    )

    return {"status": "prompt_sent"}


@app.post("/api/phase-b/sessions/{session_id}/turns/{turn_index}/chunks")
async def phase_b_upload_chunk(
    session_id: str,
    turn_index: int,
    video_file: UploadFile = File(...),
    audio_file: UploadFile = File(...),
    chunk_index: int = Form(...),
    start_ms: int = Form(...),
    end_ms: int = Form(...),
    mediapipe_metrics: str = Form(default="{}"),
) -> dict[str, str]:
    """Receive a 5-second chunk and launch background Imentiv processing."""

    import json as _json

    try:
        state = get_phase_b_manager().get_state(session_id)
    except RuntimeError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    current = state.get("current_turn")
    if current is None or current["turn_index"] != turn_index:
        raise HTTPException(status_code=409, detail="Turn index mismatch or no active turn.")
    if chunk_index < 0:
        raise HTTPException(status_code=400, detail="Chunk index must be non-negative.")
    if start_ms < 0:
        raise HTTPException(status_code=400, detail="Chunk start_ms must be non-negative.")
    if end_ms <= start_ms:
        raise HTTPException(status_code=400, detail="Chunk end_ms must be greater than start_ms.")
    if get_phase_b_manager().has_chunk(session_id, chunk_index):
        raise HTTPException(status_code=409, detail=f"Chunk {chunk_index} has already been uploaded.")

    video_upload = await _save_media_upload(
        video_file,
        storage_key=_phase_b_chunk_storage_key(session_id, turn_index, chunk_index, "video", ".webm"),
    )
    audio_upload = await _save_media_upload(
        audio_file,
        storage_key=_phase_b_chunk_storage_key(session_id, turn_index, chunk_index, "audio", ".webm"),
    )
    if int(video_upload.get("size_bytes") or 0) == 0 or int(audio_upload.get("size_bytes") or 0) == 0:
        raise HTTPException(status_code=400, detail="Chunk uploads must contain non-empty audio and video.")

    try:
        mp_metrics = _json.loads(mediapipe_metrics)
    except _json.JSONDecodeError:
        mp_metrics = {}

    chunk_record = {
        "chunk_index": chunk_index,
        "start_ms": start_ms,
        "end_ms": end_ms,
        "mediapipe_metrics": mp_metrics,
        "video_emotions": None,
        "audio_emotions": None,
        "status": "pending",
        "video_upload": video_upload,
        "audio_upload": audio_upload,
    }
    get_phase_b_manager().add_chunk(session_id, chunk_record)

    # Launch background Imentiv processing
    asyncio.create_task(
        _process_phase_b_chunk(session_id, chunk_index, video_upload, audio_upload)
    )

    return {"status": "accepted", "chunk_index": str(chunk_index)}


@app.post("/api/phase-b/sessions/{session_id}/turns/{turn_index}/transcribe")
async def phase_b_transcribe(
    session_id: str,
    turn_index: int,
    audio_file: UploadFile = File(...),
) -> dict[str, object]:
    """Transcribe the full turn audio via ElevenLabs STT."""

    try:
        state = get_phase_b_manager().get_state(session_id)
    except RuntimeError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    current = state.get("current_turn")
    if current is None or current["turn_index"] != turn_index:
        raise HTTPException(status_code=409, detail="Turn index mismatch or no active turn.")

    transcript_audio_upload = await _save_media_upload(
        audio_file,
        storage_key=_phase_b_transcript_storage_key(session_id, turn_index, ".webm"),
    )
    if int(transcript_audio_upload.get("size_bytes") or 0) == 0:
        await get_phase_b_manager().send_event(
            session_id,
            "retry_recording",
            {"message": RETRY_EMPTY_MESSAGE},
        )
        raise HTTPException(status_code=409, detail=RETRY_EMPTY_MESSAGE)

    get_phase_b_manager().store_transcript_upload(session_id, transcript_audio_upload)

    from backend.sprint.phase_b.elevenlabs import transcribe_audio
    from backend.shared.ai import get_ai_service

    transcript, words = await transcribe_audio(
        ai_service=get_ai_service(),
        audio_source=transcript_audio_upload,
    )

    get_phase_b_manager().store_transcript(session_id, transcript, words)

    return {"transcript": transcript, "word_count": len(words)}


@app.post("/api/phase-b/sessions/{session_id}/turns/{turn_index}/complete")
async def phase_b_complete_turn(session_id: str, turn_index: int) -> dict[str, str]:
    """Run the critique pipeline after recording + chunks + STT are done.

    Executes: collect_chunks → merge_summary → judge_response → speak_critique
    """

    try:
        state = get_phase_b_manager().get_state(session_id)
    except RuntimeError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    current = state.get("current_turn")
    if current is None or current["turn_index"] != turn_index:
        raise HTTPException(status_code=409, detail="Turn index mismatch or no active turn.")

    is_valid, validation_error, recording_window = get_phase_b_manager().validate_turn_chunks(
        session_id,
        min_seconds=PHASE_B_MIN_SECONDS,
        max_seconds=PHASE_B_MAX_SECONDS,
    )
    if not is_valid:
        await get_phase_b_manager().send_event(
            session_id,
            "retry_recording",
            {"message": validation_error or RETRY_INVALID_CHUNKS_MESSAGE},
        )
        raise HTTPException(status_code=409, detail=validation_error or RETRY_INVALID_CHUNKS_MESSAGE)
    if recording_window is None:
        raise HTTPException(status_code=500, detail="Recording window could not be determined.")

    get_phase_b_manager().set_recording_window(
        session_id,
        recording_window["recording_start_ms"],
        recording_window["recording_end_ms"],
    )

    # Run the critique subgraph
    await critique_graph.ainvoke(
        state,
        config={"configurable": {"session_id": session_id}},
    )

    # Finalize the turn in the session manager
    updated_state = get_phase_b_manager().get_state(session_id)
    current_turn = updated_state.get("current_turn")
    if current_turn:
        critique = current_turn.get("critique") or ""
        merged = current_turn.get("merged_summary") or {}
        get_phase_b_manager().finish_turn(session_id, critique, merged)

    return {"status": "turn_complete"}


@app.post("/api/phase-b/sessions/{session_id}/end")
async def phase_b_end_session(session_id: str) -> dict[str, object]:
    """Finalize the session and return summary."""

    try:
        state = get_phase_b_manager().get_state(session_id)
    except RuntimeError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    await end_graph.ainvoke(
        state,
        config={"configurable": {"session_id": session_id}},
    )

    final = get_phase_b_manager().get_state(session_id)
    return {
        "status": final["status"],
        "total_turns": len(final["turns"]),
        "turns": [
            {
                "turn_index": t["turn_index"],
                "prompt": t["prompt_text"],
                "critique": t.get("critique"),
            }
            for t in final["turns"]
        ],
    }


@app.get("/api/phase-b/sessions/{session_id}/turns/{turn_index}/chunks/{chunk_index}/{media_kind}")
async def download_phase_b_chunk_media(
    session_id: str,
    turn_index: int,
    chunk_index: int,
    media_kind: str,
) -> StreamingResponse:
    """Download one persisted Phase B chunk media artifact."""

    if media_kind not in PHASE_B_MEDIA_KINDS:
        raise HTTPException(status_code=404, detail="Phase B media type was not found.")
    session = await get_session_repository().get_session(session_id)
    media_ref = _find_phase_b_chunk_media_ref(session, turn_index, chunk_index, media_kind)
    return await _build_media_response(media_ref)


@app.get("/api/phase-b/sessions/{session_id}/turns/{turn_index}/transcript-audio")
async def download_phase_b_transcript_audio(session_id: str, turn_index: int) -> StreamingResponse:
    """Download the full-turn transcript audio capture for Phase B."""

    session = await get_session_repository().get_session(session_id)
    media_ref = _find_phase_b_transcript_media_ref(session, turn_index)
    return await _build_media_response(media_ref)


async def _process_phase_b_chunk(
    session_id: str,
    chunk_index: int,
    video_upload: dict[str, object],
    audio_upload: dict[str, object],
) -> None:
    """Background task: upload to Imentiv, poll for results, update chunk."""

    from backend.shared.ai import get_settings
    from backend.sprint.phase_b.imentiv import analyze_video

    manager = get_phase_b_manager()
    settings = get_settings()

    try:
        manager.update_chunk(session_id, chunk_index, {"status": "processing"})
        analysis = await analyze_video(
            settings,
            video_upload,
            title=f"phase-b-{session_id}-chunk-{chunk_index}",
            description="Phase B conversation chunk analysis.",
        )

        manager.update_chunk(session_id, chunk_index, {
            "imentiv_analysis": analysis,
            "video_emotions": analysis.get("video_emotions") if isinstance(analysis.get("video_emotions"), list) else [],
            "audio_emotions": analysis.get("audio_emotions") if isinstance(analysis.get("audio_emotions"), list) else [],
            "status": "done",
        })
    except Exception as error:
        manager.update_chunk(session_id, chunk_index, {"status": "failed", "error": str(error)})


async def _soft_result(awaitable):
    """Swallow errors from external services so other tasks continue."""

    try:
        return await awaitable
    except Exception:
        return []


# ======================================================================
# Phase C — Speak Freely
# ======================================================================

@app.post("/api/phase-c/sessions", response_model=StartPhaseCSessionResponse)
async def start_phase_c_session(request: StartPhaseCSessionRequest) -> StartPhaseCSessionResponse:
    session = get_phase_c_manager().create_session(request.difficulty)
    return StartPhaseCSessionResponse(session_id=session.session_id)


@app.get("/api/phase-c/sessions/{session_id}", response_model=PhaseCSessionStateResponse)
async def get_phase_c_session(session_id: str) -> PhaseCSessionStateResponse:
    try:
        state = get_phase_c_manager().get_state(session_id)
    except RuntimeError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    return PhaseCSessionStateResponse(
        session_id=state["session_id"],
        difficulty=state["difficulty"],
        status=state["status"],
        current_recording=state.get("current_recording"),
        completed_recording=state.get("completed_recording"),
    )


@app.websocket("/api/phase-c/ws/{session_id}")
async def phase_c_websocket(websocket: WebSocket, session_id: str) -> None:
    try:
        await get_phase_c_manager().bind_websocket(session_id, websocket)
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        get_phase_c_manager().unbind_websocket(session_id)
    except RuntimeError:
        await websocket.close(code=1008)


@app.post("/api/phase-c/sessions/{session_id}/recording/start")
async def phase_c_start_recording(session_id: str) -> dict[str, str]:
    try:
        get_phase_c_manager().start_recording(session_id)
        await get_phase_c_manager().send_event(
            session_id,
            "recording_ready",
            {"max_seconds": PHASE_C_MAX_SECONDS},
        )
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return {"status": "recording_ready"}


@app.post("/api/phase-c/sessions/{session_id}/chunks")
async def phase_c_upload_chunk(
    session_id: str,
    video_file: UploadFile = File(...),
    audio_file: UploadFile = File(...),
    chunk_index: int = Form(...),
    start_ms: int = Form(...),
    end_ms: int = Form(...),
    mediapipe_metrics: str = Form(default="{}"),
) -> dict[str, str]:
    import json as _json

    try:
        get_phase_c_manager().get_state(session_id)
    except RuntimeError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    if chunk_index < 0:
        raise HTTPException(status_code=400, detail="Chunk index must be non-negative.")
    if start_ms < 0:
        raise HTTPException(status_code=400, detail="Chunk start_ms must be non-negative.")
    if end_ms <= start_ms:
        raise HTTPException(status_code=400, detail="Chunk end_ms must be greater than start_ms.")
    if get_phase_c_manager().has_chunk(session_id, chunk_index):
        raise HTTPException(status_code=409, detail=f"Chunk {chunk_index} has already been uploaded.")

    video_path = await _save_upload(video_file, suffix=".webm")
    audio_path = await _save_upload(audio_file, suffix=".webm")
    if Path(video_path).stat().st_size == 0 or Path(audio_path).stat().st_size == 0:
        raise HTTPException(status_code=400, detail="Chunk uploads must contain non-empty audio and video.")

    try:
        mp_metrics = _json.loads(mediapipe_metrics)
    except _json.JSONDecodeError:
        mp_metrics = {}

    get_phase_c_manager().add_chunk(
        session_id,
        {
            "chunk_index": chunk_index,
            "start_ms": start_ms,
            "end_ms": end_ms,
            "mediapipe_metrics": mp_metrics,
            "video_emotions": None,
            "audio_emotions": None,
            "status": "pending",
        },
    )
    asyncio.create_task(_process_phase_c_chunk(session_id, chunk_index, video_path, audio_path))
    return {"status": "accepted", "chunk_index": str(chunk_index)}


@app.post("/api/phase-c/sessions/{session_id}/transcribe")
async def phase_c_transcribe(session_id: str, audio_file: UploadFile = File(...)) -> dict[str, object]:
    try:
        get_phase_c_manager().get_state(session_id)
    except RuntimeError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    audio_path = await _save_upload(audio_file, suffix=".webm")
    if Path(audio_path).stat().st_size == 0:
        await get_phase_c_manager().send_event(
            session_id,
            "retry_recording",
            {"message": PHASE_C_RETRY_EMPTY_MESSAGE},
        )
        raise HTTPException(status_code=409, detail=PHASE_C_RETRY_EMPTY_MESSAGE)

    from backend.shared.ai import get_ai_service
    from backend.sprint.phase_c.elevenlabs import transcribe_audio

    try:
        transcript, words = await transcribe_audio(ai_service=get_ai_service(), audio_path=audio_path)
    finally:
        Path(audio_path).unlink(missing_ok=True)
    get_phase_c_manager().store_transcript(session_id, transcript, words)
    return {"transcript": transcript, "word_count": len(words)}


@app.post("/api/phase-c/sessions/{session_id}/complete")
async def phase_c_complete(session_id: str) -> dict[str, str]:
    try:
        state = get_phase_c_manager().get_state(session_id)
    except RuntimeError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    is_valid, validation_error, recording_window = get_phase_c_manager().validate_recording(
        session_id,
        min_seconds=PHASE_C_MIN_SECONDS,
        max_seconds=PHASE_C_MAX_SECONDS,
    )
    if not is_valid:
        await get_phase_c_manager().send_event(
            session_id,
            "retry_recording",
            {"message": validation_error or PHASE_C_RETRY_INVALID_CHUNKS_MESSAGE},
        )
        raise HTTPException(status_code=409, detail=validation_error or PHASE_C_RETRY_INVALID_CHUNKS_MESSAGE)
    if recording_window is None:
        raise HTTPException(status_code=500, detail="Recording window could not be determined.")

    get_phase_c_manager().set_recording_window(
        session_id,
        recording_window["recording_start_ms"],
        recording_window["recording_end_ms"],
    )
    await phase_c_graph.ainvoke(state, config={"configurable": {"session_id": session_id}})
    return {"status": "complete"}


async def _process_phase_c_chunk(
    session_id: str,
    chunk_index: int,
    video_path: str,
    audio_path: str,
) -> None:
    from backend.shared.ai import get_settings
    from backend.sprint.phase_c.imentiv import analyze_video

    manager = get_phase_c_manager()
    settings = get_settings()

    try:
        manager.update_chunk(session_id, chunk_index, {"status": "processing"})
        analysis = await analyze_video(
            settings,
            video_path,
            title=f"phase-c-{session_id}-chunk-{chunk_index}",
            description="Phase C freeform speaking chunk analysis.",
        )
        manager.update_chunk(
            session_id,
            chunk_index,
            {
                "imentiv_analysis": analysis,
                "video_emotions": analysis.get("video_emotions") if isinstance(analysis.get("video_emotions"), list) else [],
                "audio_emotions": analysis.get("audio_emotions") if isinstance(analysis.get("audio_emotions"), list) else [],
                "status": "done",
            },
        )
    except Exception as error:
        manager.update_chunk(session_id, chunk_index, {"status": "failed", "error": str(error)})
    finally:
        Path(video_path).unlink(missing_ok=True)
        Path(audio_path).unlink(missing_ok=True)
