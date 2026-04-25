"""In-memory session coordination for Phase B conversation sessions."""

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from fastapi import WebSocket

from backend.sprint.phase_b.schemas import (
    ChunkRecord,
    PhaseBState,
    Scenario,
    TurnState,
    build_initial_state,
    build_turn_state,
)


@dataclass
class ActiveConversation:
    """Mutable state for one active Phase B session."""

    session_id: str
    state: PhaseBState
    websocket: WebSocket | None = None
    pending_events: list[dict[str, Any]] = field(default_factory=list)


class PhaseBSessionManager:
    """In-memory registry for Phase B conversation sessions."""

    def __init__(self) -> None:
        self._sessions: dict[str, ActiveConversation] = {}

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def create_session(
        self,
        scenario: Scenario,
        difficulty: int,
        max_turns: int = 4,
    ) -> ActiveConversation:
        session_id = str(uuid4())
        state = build_initial_state(session_id, scenario, difficulty, max_turns)
        session = ActiveConversation(session_id=session_id, state=state)
        self._sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> ActiveConversation:
        try:
            return self._sessions[session_id]
        except KeyError as error:
            raise RuntimeError(f"Phase B session {session_id!r} not found.") from error

    def get_state(self, session_id: str) -> PhaseBState:
        return self.get_session(session_id).state

    # ------------------------------------------------------------------
    # Turn management
    # ------------------------------------------------------------------

    def start_turn(self, session_id: str, prompt_text: str) -> TurnState:
        """Initialize a new turn after prompt generation."""

        state = self.get_state(session_id)
        turn = build_turn_state(state["turn_index"], prompt_text)
        state["current_turn"] = turn
        state["conversation_history"].append({"role": "assistant", "content": prompt_text})
        return turn

    def add_chunk(self, session_id: str, chunk: ChunkRecord) -> None:
        """Append a chunk record to the current turn."""

        state = self.get_state(session_id)
        current = state.get("current_turn")
        if current is None:
            raise RuntimeError("No active turn to attach a chunk to.")
        current["chunks"].append(chunk)

    def has_chunk(self, session_id: str, chunk_index: int) -> bool:
        """Return whether the current turn already contains the chunk index."""

        state = self.get_state(session_id)
        current = state.get("current_turn")
        if current is None:
            raise RuntimeError("No active turn.")
        return any(chunk["chunk_index"] == chunk_index for chunk in current["chunks"])

    def get_chunk(self, session_id: str, chunk_index: int) -> ChunkRecord:
        """Retrieve a specific chunk from the current turn."""

        state = self.get_state(session_id)
        current = state.get("current_turn")
        if current is None:
            raise RuntimeError("No active turn.")
        for chunk in current["chunks"]:
            if chunk["chunk_index"] == chunk_index:
                return chunk
        raise RuntimeError(f"Chunk {chunk_index} not found in current turn.")

    def update_chunk(self, session_id: str, chunk_index: int, updates: dict[str, Any]) -> None:
        """Merge updates into an existing chunk record."""

        chunk = self.get_chunk(session_id, chunk_index)
        chunk.update(updates)  # type: ignore[typeddict-item]

    def get_sorted_chunks(self, session_id: str) -> list[ChunkRecord]:
        """Return current-turn chunks ordered by start timestamp."""

        state = self.get_state(session_id)
        current = state.get("current_turn")
        if current is None:
            raise RuntimeError("No active turn.")
        return sorted(current["chunks"], key=lambda chunk: (chunk["start_ms"], chunk["chunk_index"]))

    def set_recording_window(self, session_id: str, start_ms: int, end_ms: int) -> None:
        """Persist the inferred recording window on the current turn."""

        state = self.get_state(session_id)
        current = state.get("current_turn")
        if current is None:
            raise RuntimeError("No active turn.")
        current["recording_start_ms"] = start_ms
        current["recording_end_ms"] = end_ms

    def validate_turn_chunks(
        self,
        session_id: str,
        *,
        min_seconds: int,
        max_seconds: int,
    ) -> tuple[bool, str | None, dict[str, int] | None]:
        """Validate the current turn's chunk coverage and inferred duration."""

        chunks = self.get_sorted_chunks(session_id)
        if not chunks:
            return False, "The recording was empty. Check camera and microphone access.", None

        seen_indexes: set[int] = set()
        previous_end_ms: int | None = None

        for chunk in chunks:
            chunk_index = chunk["chunk_index"]
            start_ms = chunk["start_ms"]
            end_ms = chunk["end_ms"]

            if chunk_index in seen_indexes:
                return (
                    False,
                    "Some recording chunks were duplicated. Please record that turn again.",
                    None,
                )
            seen_indexes.add(chunk_index)

            if chunk_index < 0 or start_ms < 0 or end_ms <= start_ms:
                return (
                    False,
                    "Some recording chunks were invalid. Please record that turn again.",
                    None,
                )

            if previous_end_ms is not None:
                if start_ms < previous_end_ms:
                    return (
                        False,
                        "Some recording chunks were missing or overlapped. Please record that turn again.",
                        None,
                    )
                if start_ms > previous_end_ms:
                    return (
                        False,
                        "Some recording chunks were missing or overlapped. Please record that turn again.",
                        None,
                    )
            previous_end_ms = end_ms

        recording_start_ms = chunks[0]["start_ms"]
        recording_end_ms = chunks[-1]["end_ms"]
        duration_ms = recording_end_ms - recording_start_ms

        if duration_ms < min_seconds * 1000:
            return False, "That recording was too short. Try again with a full response.", None
        if duration_ms > max_seconds * 1000:
            return False, f"That response ran too long. Keep it under {max_seconds} seconds.", None

        return True, None, {
            "recording_start_ms": recording_start_ms,
            "recording_end_ms": recording_end_ms,
        }

    def store_transcript(
        self,
        session_id: str,
        transcript: str,
        words: list[dict[str, Any]],
    ) -> None:
        """Store STT results on the current turn."""

        state = self.get_state(session_id)
        current = state.get("current_turn")
        if current is None:
            raise RuntimeError("No active turn.")
        current["transcript"] = transcript
        current["transcript_words"] = words

    def finish_turn(self, session_id: str, critique: str, merged_summary: dict[str, Any]) -> None:
        """Archive the current turn and advance the index."""

        state = self.get_state(session_id)
        current = state.get("current_turn")
        if current is None:
            raise RuntimeError("No active turn to finish.")

        current["critique"] = critique
        current["merged_summary"] = merged_summary
        state["conversation_history"].append({"role": "user", "content": current["transcript"] or ""})
        state["turns"].append(current)
        state["current_turn"] = None
        state["turn_index"] += 1

    def end_session(self, session_id: str) -> PhaseBState:
        """Mark the session as complete and return final state."""

        state = self.get_state(session_id)
        state["status"] = "complete"
        return state

    # ------------------------------------------------------------------
    # WebSocket binding  (mirrors Phase A pattern)
    # ------------------------------------------------------------------

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


_SESSION_MANAGER = PhaseBSessionManager()


def get_phase_b_manager() -> PhaseBSessionManager:
    """Return the process-local Phase B session registry."""

    return _SESSION_MANAGER
