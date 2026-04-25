"""In-memory session coordination for Phase B conversation sessions."""

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from fastapi import WebSocket

from backend.shared.db import get_session_repository
from backend.shared.db.tasks import schedule_repository_write
from backend.sprint.phase_b.schemas import (
    ChunkRecord,
    FinalReport,
    MomentumDecision,
    PeerProfile,
    PhaseBState,
    TurnAnalysis,
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
        *,
        difficulty: int,
        scenario_preference: str | None,
        max_turns: int = 6,
        minimum_turns: int = 3,
        voice_id: str | None = None,
    ) -> ActiveConversation:
        session_id = str(uuid4())
        state = build_initial_state(
            session_id=session_id,
            difficulty=difficulty,
            scenario_preference=scenario_preference,
            voice_id=voice_id,
            max_turns=max_turns,
            minimum_turns=minimum_turns,
        )
        session = ActiveConversation(session_id=session_id, state=state)
        self._sessions[session_id] = session
        schedule_repository_write(
            get_session_repository().create_phase_b_session(
                session_id=session_id,
                state=dict(state),
            )
        )
        return session

    def get_session(self, session_id: str) -> ActiveConversation:
        try:
            return self._sessions[session_id]
        except KeyError as error:
            raise RuntimeError(f"Phase B session {session_id!r} not found.") from error

    def get_state(self, session_id: str) -> PhaseBState:
        return self.get_session(session_id).state

    def initialize_context(
        self,
        session_id: str,
        *,
        scenario: str,
        peer_profile: PeerProfile,
        starter_topic: str,
        opening_line: str,
    ) -> None:
        state = self.get_state(session_id)
        state["scenario"] = scenario
        state["peer_profile"] = peer_profile
        state["starter_topic"] = starter_topic
        state["opening_line"] = opening_line
        self.persist_state(session_id)

    def set_voice_id(self, session_id: str, voice_id: str | None) -> None:
        state = self.get_state(session_id)
        state["voice_id"] = voice_id
        self.persist_state(session_id)

    def has_active_turn(self, session_id: str) -> bool:
        return self.get_state(session_id).get("current_turn") is not None

    # ------------------------------------------------------------------
    # Turn management
    # ------------------------------------------------------------------

    def start_turn(self, session_id: str, prompt_text: str) -> TurnState:
        """Initialize a new turn after prompt generation."""

        state = self.get_state(session_id)
        turn = build_turn_state(state["turn_index"], prompt_text)
        state["current_turn"] = turn
        state["conversation_history"].append({"role": "assistant", "content": prompt_text})
        self.persist_state(session_id)
        return turn

    def get_turn(self, session_id: str, turn_index: int) -> TurnState:
        state = self.get_state(session_id)
        current = state.get("current_turn")
        if isinstance(current, dict) and current["turn_index"] == turn_index:
            return current
        for turn in state["turns"]:
            if turn["turn_index"] == turn_index:
                return turn
        raise RuntimeError(f"Turn {turn_index} was not found.")

    def add_chunk(self, session_id: str, chunk: ChunkRecord) -> None:
        state = self.get_state(session_id)
        current = state.get("current_turn")
        if current is None:
            raise RuntimeError("No active turn to attach a chunk to.")
        current["chunks"].append(chunk)
        self.persist_state(session_id)

    def has_chunk(self, session_id: str, turn_index: int, chunk_index: int) -> bool:
        turn = self.get_turn(session_id, turn_index)
        return any(chunk["chunk_index"] == chunk_index for chunk in turn["chunks"])

    def get_chunk(self, session_id: str, turn_index: int, chunk_index: int) -> ChunkRecord:
        turn = self.get_turn(session_id, turn_index)
        for chunk in turn["chunks"]:
            if chunk["chunk_index"] == chunk_index:
                return chunk
        raise RuntimeError(f"Chunk {chunk_index} not found in turn {turn_index}.")

    def update_chunk(
        self,
        session_id: str,
        turn_index: int,
        chunk_index: int,
        updates: dict[str, Any],
    ) -> None:
        chunk = self.get_chunk(session_id, turn_index, chunk_index)
        chunk.update(updates)  # type: ignore[typeddict-item]
        self.persist_state(session_id)

    def get_sorted_chunks(self, session_id: str, turn_index: int) -> list[ChunkRecord]:
        turn = self.get_turn(session_id, turn_index)
        return sorted(turn["chunks"], key=lambda chunk: (chunk["start_ms"], chunk["chunk_index"]))

    def set_recording_window(self, session_id: str, turn_index: int, start_ms: int, end_ms: int) -> None:
        turn = self.get_turn(session_id, turn_index)
        turn["recording_start_ms"] = start_ms
        turn["recording_end_ms"] = end_ms
        self.persist_state(session_id)

    def validate_turn_chunks(
        self,
        session_id: str,
        *,
        turn_index: int,
        min_seconds: int,
        max_seconds: int,
    ) -> tuple[bool, str | None, dict[str, int] | None]:
        chunks = self.get_sorted_chunks(session_id, turn_index)
        if not chunks:
            return False, "The recording was empty. Check camera and microphone access.", None

        seen_indexes: set[int] = set()
        previous_end_ms: int | None = None

        for chunk in chunks:
            chunk_index = chunk["chunk_index"]
            start_ms = chunk["start_ms"]
            end_ms = chunk["end_ms"]

            if chunk_index in seen_indexes:
                return False, "Some recording chunks were duplicated. Please record that turn again.", None
            seen_indexes.add(chunk_index)

            if chunk_index < 0 or start_ms < 0 or end_ms <= start_ms:
                return False, "Some recording chunks were invalid. Please record that turn again.", None

            if previous_end_ms is not None and start_ms != previous_end_ms:
                return False, "Some recording chunks were missing or overlapped. Please record that turn again.", None
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
        turn_index: int,
        transcript: str,
        words: list[dict[str, Any]],
    ) -> None:
        turn = self.get_turn(session_id, turn_index)
        turn["transcript"] = transcript
        turn["transcript_words"] = words
        self.persist_state(session_id)

    def store_transcript_upload(
        self,
        session_id: str,
        turn_index: int,
        upload_ref: dict[str, Any],
    ) -> None:
        turn = self.get_turn(session_id, turn_index)
        turn["transcript_audio_upload"] = upload_ref
        self.persist_state(session_id)

    def store_turn_analysis(
        self,
        session_id: str,
        turn_index: int,
        *,
        merged_summary: dict[str, Any],
        turn_analysis: TurnAnalysis,
        analysis_status: str,
    ) -> None:
        turn = self.get_turn(session_id, turn_index)
        turn["merged_summary"] = merged_summary
        turn["turn_analysis"] = turn_analysis
        turn["analysis_status"] = analysis_status  # type: ignore[typeddict-item]
        turn["critique"] = turn_analysis.get("summary")
        self.persist_state(session_id)

    def finish_turn(self, session_id: str, turn_index: int) -> TurnState:
        state = self.get_state(session_id)
        current = state.get("current_turn")
        if current is None or current["turn_index"] != turn_index:
            raise RuntimeError("No active turn to finish.")

        state["conversation_history"].append({"role": "user", "content": current["transcript"] or ""})
        state["turns"].append(current)
        state["current_turn"] = None
        state["turn_index"] += 1
        self.persist_state(session_id)
        return current

    def store_momentum_decision(self, session_id: str, decision: MomentumDecision | None) -> None:
        state = self.get_state(session_id)
        state["momentum_decision"] = decision
        self.persist_state(session_id)

    def store_final_report(self, session_id: str, report: FinalReport) -> None:
        state = self.get_state(session_id)
        state["final_report"] = report
        self.persist_state(session_id)

    def end_session(self, session_id: str) -> PhaseBState:
        state = self.get_state(session_id)
        state["status"] = "complete"
        self.persist_state(session_id)
        return state

    def persist_state(self, session_id: str) -> None:
        state = self.get_state(session_id)
        schedule_repository_write(
            get_session_repository().update_phase_b_state(
                session_id=session_id,
                state=dict(state),
            )
        )

    # ------------------------------------------------------------------
    # WebSocket binding
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
