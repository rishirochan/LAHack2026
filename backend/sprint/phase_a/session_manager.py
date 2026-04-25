"""In-memory session coordination for Phase A graph runs."""

import asyncio
from collections import Counter
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from fastapi import WebSocket

from backend.shared.db import get_session_repository
from backend.shared.db.tasks import schedule_repository_write
from .schemas import RoundSummary, SessionSummaryResponse

@dataclass
class ActiveSession:
    """Mutable state for one active browser session."""

    session_id: str
    initial_state: dict[str, Any]
    websocket: WebSocket | None = None
    pending_events: list[dict[str, Any]] = field(default_factory=list)
    recording_future: asyncio.Future[tuple[dict[str, Any], dict[str, Any]]] | None = None
    continue_future: asyncio.Future[bool] | None = None
    task: asyncio.Task | None = None
    latest_state: dict[str, Any] = field(default_factory=dict)
    rounds: list[RoundSummary] = field(default_factory=list)
    media_refs: list[dict[str, Any]] = field(default_factory=list)


class PhaseASessionManager:
    """Small in-memory registry for websocket and human wait points."""

    def __init__(self) -> None:
        self._sessions: dict[str, ActiveSession] = {}

    def create_session(self, initial_state: dict[str, Any]) -> ActiveSession:
        session_id = str(uuid4())
        session = ActiveSession(session_id=session_id, initial_state=initial_state)
        self._sessions[session_id] = session
        schedule_repository_write(
            get_session_repository().create_phase_a_session(
                session_id=session_id,
                initial_state=initial_state,
            )
        )
        return session

    def get_session(self, session_id: str) -> ActiveSession:
        try:
            return self._sessions[session_id]
        except KeyError as error:
            raise RuntimeError("Phase A session was not found.") from error

    async def bind_websocket(self, session_id: str, websocket: WebSocket) -> None:
        session = self.get_session(session_id)
        await websocket.accept()
        session.websocket = websocket
        for event in session.pending_events:
            await websocket.send_json(event)
        session.pending_events.clear()

    def unbind_websocket(self, session_id: str) -> None:
        if session_id in self._sessions:
            self._sessions[session_id].websocket = None

    async def send_event(self, session_id: str, event_type: str, payload: dict[str, Any]) -> None:
        session = self.get_session(session_id)
        event = {"type": event_type, "payload": payload}
        if session.websocket is None:
            session.pending_events.append(event)
            return
        try:
            await session.websocket.send_json(event)
        except RuntimeError:
            session.pending_events.append(event)

    async def wait_for_recording(self, session_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
        session = self.get_session(session_id)
        loop = asyncio.get_running_loop()
        session.recording_future = loop.create_future()
        return await session.recording_future

    def submit_recording(
        self,
        session_id: str,
        video_upload: dict[str, Any],
        audio_upload: dict[str, Any],
    ) -> None:
        session = self.get_session(session_id)
        if session.recording_future is None:
            raise RuntimeError("The session is not waiting for a recording.")
        if session.recording_future.done():
            raise RuntimeError("The recording has already been submitted.")
        session.recording_future.set_result((video_upload, audio_upload))

    def get_next_round_index(self, session_id: str) -> int:
        return len(self.get_session(session_id).rounds)

    async def wait_for_continue(self, session_id: str) -> bool:
        session = self.get_session(session_id)
        loop = asyncio.get_running_loop()
        session.continue_future = loop.create_future()
        return await session.continue_future

    def submit_continue(self, session_id: str, continue_session: bool) -> None:
        session = self.get_session(session_id)
        if session.continue_future is None:
            raise RuntimeError("The session is not waiting for a continue decision.")
        if session.continue_future.done():
            raise RuntimeError("The continue decision has already been submitted.")
        session.continue_future.set_result(continue_session)

    def set_task(self, session_id: str, task: asyncio.Task) -> None:
        self.get_session(session_id).task = task

    def store_state(self, session_id: str, state: dict[str, Any]) -> None:
        session = self.get_session(session_id)
        session.latest_state = state
        schedule_repository_write(
            get_session_repository().update_phase_a_session(
                session_id=session_id,
                raw_state=state,
                media_refs=session.media_refs,
            )
        )

    def add_round(self, session_id: str, state: dict[str, Any]) -> None:
        merged_analysis = state.get("merged_analysis") or {}
        summary = RoundSummary(
            scenario_prompt=state.get("scenario_prompt") or "",
            critique=state.get("critique") or "",
            match_score=float(state.get("match_score") or 0),
            filler_words_found=list(merged_analysis.get("filler_words_found") or []),
            filler_word_count=int(merged_analysis.get("filler_word_count") or 0),
        )
        session = self.get_session(session_id)
        round_index = len(session.rounds)
        session.rounds.append(summary)
        session.media_refs.extend(_build_round_media_refs(session_id, round_index, state))
        session_summary = self.get_summary(session_id).model_dump()
        schedule_repository_write(
            get_session_repository().update_phase_a_session(
                session_id=session_id,
                rounds=[round_summary.model_dump() for round_summary in session.rounds],
                summary=session_summary,
                raw_state=state,
                media_refs=session.media_refs,
            )
        )

    def get_summary(self, session_id: str) -> SessionSummaryResponse:
        session = self.get_session(session_id)
        filler_counter: Counter[str] = Counter()
        for round_summary in session.rounds:
            filler_counter.update(round_summary.filler_words_found)

        return SessionSummaryResponse(
            session_id=session_id,
            critiques=[round_summary.critique for round_summary in session.rounds],
            match_scores=[round_summary.match_score for round_summary in session.rounds],
            filler_words=dict(filler_counter),
            rounds=session.rounds,
        )


_SESSION_MANAGER = PhaseASessionManager()


def get_session_manager() -> PhaseASessionManager:
    """Return the process-local Phase A session registry."""

    return _SESSION_MANAGER


def _build_round_media_refs(session_id: str, round_index: int, state: dict[str, Any]) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for media_kind in ("video", "audio"):
        upload = state.get(f"{media_kind}_upload")
        if not isinstance(upload, dict):
            continue
        refs.append(
            {
                "round_index": round_index,
                "kind": media_kind,
                "download_url": f"/api/phase-a/sessions/{session_id}/rounds/{round_index}/{media_kind}",
                "upload": _public_upload_ref(upload),
            }
        )
    return refs


def _public_upload_ref(upload: dict[str, Any]) -> dict[str, Any]:
    return {
        "file_id": upload.get("file_id"),
        "storage_key": upload.get("storage_key"),
        "filename": upload.get("filename"),
        "original_filename": upload.get("original_filename"),
        "mime_type": upload.get("mime_type"),
        "size_bytes": upload.get("size_bytes"),
        "uploaded_at": upload.get("uploaded_at"),
    }

