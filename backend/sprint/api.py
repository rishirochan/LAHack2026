"""FastAPI app for sprint backend features."""

import asyncio
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from backend.shared.db import close_database, get_session_repository, init_database
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
        label = str(setup.get("theme") or "Emotion Drill")
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
        theme=request.theme,
        target_emotion=request.target_emotion,
        difficulty=request.difficulty,
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

        video_path = await _save_upload(video_file, suffix=".webm")
        audio_path = await _save_upload(audio_file, suffix=".webm")
        if Path(video_path).stat().st_size == 0 or Path(audio_path).stat().st_size == 0:
            await get_session_manager().send_event(
                session_id,
                "retry_recording",
                {"message": "The recording was empty. Check camera and microphone access."},
            )
            return {"status": "retry"}

        get_session_manager().submit_recording(session_id, video_path, audio_path)
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


async def _save_upload(upload: UploadFile, suffix: str) -> str:
    data = await upload.read()
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as output:
        output.write(data)
        return output.name


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
        current_turn=state.get("current_turn"),
        turns=state["turns"],
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

    video_path = await _save_upload(video_file, suffix=".webm")
    audio_path = await _save_upload(audio_file, suffix=".webm")
    if Path(video_path).stat().st_size == 0 or Path(audio_path).stat().st_size == 0:
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
    }
    get_phase_b_manager().add_chunk(session_id, chunk_record)

    # Launch background Imentiv processing
    asyncio.create_task(
        _process_phase_b_chunk(session_id, chunk_index, video_path, audio_path)
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

    audio_path = await _save_upload(audio_file, suffix=".webm")
    if Path(audio_path).stat().st_size == 0:
        await get_phase_b_manager().send_event(
            session_id,
            "retry_recording",
            {"message": RETRY_EMPTY_MESSAGE},
        )
        raise HTTPException(status_code=409, detail=RETRY_EMPTY_MESSAGE)

    from backend.sprint.phase_b.elevenlabs import transcribe_audio
    from backend.shared.ai import get_ai_service

    transcript, words = await transcribe_audio(
        ai_service=get_ai_service(),
        audio_path=audio_path,
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


async def _process_phase_b_chunk(
    session_id: str,
    chunk_index: int,
    video_path: str,
    audio_path: str,
) -> None:
    """Background task: upload to Imentiv, poll for results, update chunk."""

    from backend.shared.ai import get_settings
    from backend.sprint.phase_b.imentiv import (
        get_audio_emotions,
        get_video_emotions,
        upload_audio,
        upload_video,
    )

    manager = get_phase_b_manager()
    settings = get_settings()

    try:
        manager.update_chunk(session_id, chunk_index, {"status": "processing"})
        video_id, audio_id = await asyncio.gather(
            upload_video(settings, video_path),
            upload_audio(settings, audio_path),
        )

        video_emotions, audio_emotions = await asyncio.gather(
            _soft_result(get_video_emotions(settings, video_id)),
            _soft_result(get_audio_emotions(settings, audio_id)),
        )

        manager.update_chunk(session_id, chunk_index, {
            "video_emotions": video_emotions if isinstance(video_emotions, list) else [],
            "audio_emotions": audio_emotions if isinstance(audio_emotions, list) else [],
            "status": "done",
        })
    except Exception:
        manager.update_chunk(session_id, chunk_index, {"status": "failed"})


async def _soft_result(awaitable):
    """Swallow errors from external services so other tasks continue."""

    try:
        return await awaitable
    except Exception:
        return []
