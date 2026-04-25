"""FastAPI app for sprint backend features."""

import asyncio
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from backend.sprint.phase_a.graph import build_initial_state, phase_a_graph
from backend.sprint.phase_a.schemas import (
    ContinueSessionRequest,
    ContinueSessionResponse,
    SessionSummaryResponse,
    StartSessionRequest,
    StartSessionResponse,
)
from backend.sprint.phase_a.session_manager import get_session_manager


app = FastAPI(title="LAHacks 2026 Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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

