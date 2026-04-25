"""Session manager for Phase C freeform speaking sessions."""

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from fastapi import WebSocket

from backend.sprint.phase_c.constants import (
    RETRY_EMPTY_MESSAGE,
    RETRY_INVALID_CHUNKS_MESSAGE,
    RETRY_TOO_LONG_MESSAGE,
    RETRY_TOO_SHORT_MESSAGE,
)
from backend.sprint.phase_c.schemas import ChunkRecord, PhaseCState, RecordingState, build_initial_state, build_recording_state


@dataclass
class ActivePhaseCSession:
    session_id: str
    state: PhaseCState
    websocket: WebSocket | None = None
    pending_events: list[dict[str, Any]] = field(default_factory=list)


class PhaseCSessionManager:
    def __init__(self) -> None:
        self._sessions: dict[str, ActivePhaseCSession] = {}

    def create_session(self, difficulty: int) -> ActivePhaseCSession:
        session_id = str(uuid4())
        session = ActivePhaseCSession(session_id=session_id, state=build_initial_state(session_id, difficulty))
        self._sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> ActivePhaseCSession:
        try:
            return self._sessions[session_id]
        except KeyError as error:
            raise RuntimeError(f"Phase C session {session_id!r} not found.") from error

    def get_state(self, session_id: str) -> PhaseCState:
        return self.get_session(session_id).state

    def start_recording(self, session_id: str) -> RecordingState:
        state = self.get_state(session_id)
        if state["status"] != "active":
            raise RuntimeError("Session is not active.")
        recording = build_recording_state()
        state["current_recording"] = recording
        return recording

    def _current_recording(self, session_id: str) -> RecordingState:
        state = self.get_state(session_id)
        recording = state.get("current_recording")
        if recording is None:
            raise RuntimeError("No active recording.")
        return recording

    def add_chunk(self, session_id: str, chunk: ChunkRecord) -> None:
        self._current_recording(session_id)["chunks"].append(chunk)

    def has_chunk(self, session_id: str, chunk_index: int) -> bool:
        return any(chunk["chunk_index"] == chunk_index for chunk in self._current_recording(session_id)["chunks"])

    def get_chunk(self, session_id: str, chunk_index: int) -> ChunkRecord:
        for chunk in self._current_recording(session_id)["chunks"]:
            if chunk["chunk_index"] == chunk_index:
                return chunk
        raise RuntimeError(f"Chunk {chunk_index} not found in current recording.")

    def update_chunk(self, session_id: str, chunk_index: int, updates: dict[str, Any]) -> None:
        self.get_chunk(session_id, chunk_index).update(updates)  # type: ignore[typeddict-item]

    def get_sorted_chunks(self, session_id: str) -> list[ChunkRecord]:
        return sorted(
            self._current_recording(session_id)["chunks"],
            key=lambda chunk: (chunk["start_ms"], chunk["chunk_index"]),
        )

    def store_transcript(self, session_id: str, transcript: str, words: list[dict[str, Any]]) -> None:
        recording = self._current_recording(session_id)
        recording["transcript"] = transcript
        recording["transcript_words"] = words

    def set_recording_window(self, session_id: str, start_ms: int, end_ms: int) -> None:
        recording = self._current_recording(session_id)
        recording["recording_start_ms"] = start_ms
        recording["recording_end_ms"] = end_ms

    def set_merged_analysis(self, session_id: str, merged_analysis: dict[str, Any]) -> None:
        self._current_recording(session_id)["merged_analysis"] = merged_analysis

    def validate_recording(
        self,
        session_id: str,
        *,
        min_seconds: int,
        max_seconds: int,
    ) -> tuple[bool, str | None, dict[str, int] | None]:
        chunks = self.get_sorted_chunks(session_id)
        if not chunks:
            return False, RETRY_EMPTY_MESSAGE, None

        seen_indexes: set[int] = set()
        previous_end_ms: int | None = None
        for chunk in chunks:
            chunk_index = chunk["chunk_index"]
            start_ms = chunk["start_ms"]
            end_ms = chunk["end_ms"]

            if chunk_index in seen_indexes:
                return False, RETRY_INVALID_CHUNKS_MESSAGE, None
            seen_indexes.add(chunk_index)

            if chunk_index < 0 or start_ms < 0 or end_ms <= start_ms:
                return False, RETRY_INVALID_CHUNKS_MESSAGE, None

            if previous_end_ms is not None and start_ms != previous_end_ms:
                return False, RETRY_INVALID_CHUNKS_MESSAGE, None
            previous_end_ms = end_ms

        recording_start_ms = chunks[0]["start_ms"]
        recording_end_ms = chunks[-1]["end_ms"]
        duration_ms = recording_end_ms - recording_start_ms

        if duration_ms < min_seconds * 1000:
            return False, RETRY_TOO_SHORT_MESSAGE, None
        if duration_ms > max_seconds * 1000:
            return False, RETRY_TOO_LONG_MESSAGE, None

        return True, None, {
            "recording_start_ms": recording_start_ms,
            "recording_end_ms": recording_end_ms,
        }

    def finalize_recording(self, session_id: str, scorecard: dict[str, Any], written_summary: str) -> PhaseCState:
        state = self.get_state(session_id)
        recording = self._current_recording(session_id)
        recording["scorecard"] = scorecard
        recording["written_summary"] = written_summary
        state["completed_recording"] = recording
        state["current_recording"] = None
        state["status"] = "complete"
        return state

    async def bind_websocket(self, session_id: str, websocket: WebSocket) -> None:
        session = self.get_session(session_id)
        session.websocket = websocket
        await websocket.accept()
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
        await session.websocket.send_json(event)


_SESSION_MANAGER = PhaseCSessionManager()


def get_phase_c_manager() -> PhaseCSessionManager:
    return _SESSION_MANAGER
