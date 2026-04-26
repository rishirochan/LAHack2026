"""In-memory session coordination for Phase B conversation sessions."""

from asyncio import Task
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
    Scenario,
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
    next_turn_task: Task[Any] | None = None
    turn_post_processing_tasks: dict[int, Task[Any]] = field(default_factory=dict)


class PhaseBSessionManager:
    """In-memory registry for Phase B conversation sessions."""

    def __init__(self) -> None:
        self._sessions: dict[str, ActiveConversation] = {}

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def create_session(
        self,
        scenario_preference: str | None = None,
        max_turns: int = 6,
        minimum_turns: int = 3,
        voice_id: str | None = None,
        practice_prompt: str | None = None,
    ) -> ActiveConversation:
        session_id = str(uuid4())
        state = build_initial_state(
            session_id=session_id,
            scenario_preference=scenario_preference,
            voice_id=voice_id,
            max_turns=max_turns,
            minimum_turns=minimum_turns,
            practice_prompt=practice_prompt,
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

    def is_active(self, session_id: str) -> bool:
        return self.get_state(session_id).get("status") == "active"

    def has_active_turn(self, session_id: str) -> bool:
        return self.get_state(session_id).get("current_turn") is not None

    def has_pending_next_turn(self, session_id: str) -> bool:
        task = self.get_session(session_id).next_turn_task
        return task is not None and not task.done()

    def set_next_turn_task(self, session_id: str, task: Task[Any]) -> None:
        self.get_session(session_id).next_turn_task = task

    def clear_next_turn_task(self, session_id: str, task: Task[Any] | None = None) -> None:
        session = self.get_session(session_id)
        if task is not None and session.next_turn_task is not task:
            return
        session.next_turn_task = None

    def set_turn_post_processing_task(self, session_id: str, turn_index: int, task: Task[Any]) -> None:
        self.get_session(session_id).turn_post_processing_tasks[turn_index] = task

    def get_turn_post_processing_task(self, session_id: str, turn_index: int) -> Task[Any] | None:
        return self.get_session(session_id).turn_post_processing_tasks.get(turn_index)

    def get_turn_post_processing_tasks(self, session_id: str) -> dict[int, Task[Any]]:
        return dict(self.get_session(session_id).turn_post_processing_tasks)

    def clear_turn_post_processing_task(
        self,
        session_id: str,
        turn_index: int,
        task: Task[Any] | None = None,
    ) -> None:
        session = self.get_session(session_id)
        existing = session.turn_post_processing_tasks.get(turn_index)
        if existing is None:
            return
        if task is not None and existing is not task:
            return
        session.turn_post_processing_tasks.pop(turn_index, None)

    def cancel_turn_post_processing_tasks(self, session_id: str) -> None:
        session = self.get_session(session_id)
        for task in session.turn_post_processing_tasks.values():
            if not task.done():
                task.cancel()
        session.turn_post_processing_tasks.clear()

    # ------------------------------------------------------------------
    # Turn management
    # ------------------------------------------------------------------

    def start_turn(self, session_id: str, prompt_text: str) -> TurnState:
        """Initialize a new turn after prompt generation."""

        state = self.get_state(session_id)
        if state["status"] != "active":
            raise RuntimeError("Session is not active.")
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

    def set_recording_window(
        self,
        session_id: str,
        turn_index_or_start_ms: int,
        start_ms_or_end_ms: int,
        end_ms: int | None = None,
    ) -> None:
        if end_ms is None:
            turn_index = self._current_turn_index(session_id)
            start_ms = turn_index_or_start_ms
            recording_end_ms = start_ms_or_end_ms
        else:
            turn_index = turn_index_or_start_ms
            start_ms = start_ms_or_end_ms
            recording_end_ms = end_ms
        turn = self.get_turn(session_id, turn_index)
        turn["recording_start_ms"] = start_ms
        turn["recording_end_ms"] = recording_end_ms
        self.persist_state(session_id)

    def validate_turn_chunks(
        self,
        session_id: str,
        *,
        turn_index: int | None = None,
        min_seconds: int,
        max_seconds: int,
    ) -> tuple[bool, str | None, dict[str, int] | None]:
        resolved_turn_index = turn_index if turn_index is not None else self._current_turn_index(session_id)
        chunks = self.get_sorted_chunks(session_id, resolved_turn_index)
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

    def _current_turn_index(self, session_id: str) -> int:
        state = self.get_state(session_id)
        current_turn = state.get("current_turn")
        if current_turn is not None:
            return int(current_turn["turn_index"])
        if state["turns"]:
            return int(state["turns"][-1]["turn_index"])
        raise RuntimeError("No turn is available for this session.")

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

    def store_imentiv_analysis(
        self,
        session_id: str,
        turn_index: int,
        analysis: dict[str, Any] | None,
    ) -> None:
        turn = self.get_turn(session_id, turn_index)
        turn["imentiv_analysis"] = analysis
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
        existing = state.get("momentum_decision")
        if existing is not None and decision is not None:
            existing_turn_index = int(existing.get("based_on_turn_index", -1))
            incoming_turn_index = int(decision.get("based_on_turn_index", -1))
            if incoming_turn_index < existing_turn_index:
                return
        state["momentum_decision"] = decision
        self.persist_state(session_id)

    def store_final_report(self, session_id: str, report: FinalReport) -> None:
        state = self.get_state(session_id)
        state["final_report"] = report
        self.persist_state(session_id)

    def discard_active_turn(self, session_id: str) -> bool:
        state = self.get_state(session_id)
        current = state.get("current_turn")
        if current is None:
            return False

        prompt_text = str(current.get("prompt_text") or "")
        state["current_turn"] = None
        if prompt_text and state["conversation_history"]:
            last_entry = state["conversation_history"][-1]
            if last_entry.get("role") == "assistant" and last_entry.get("content") == prompt_text:
                state["conversation_history"].pop()
        self.persist_state(session_id)
        return True

    def begin_session_shutdown(self, session_id: str) -> PhaseBState:
        state = self.get_state(session_id)
        self._cancel_next_turn_task(session_id)
        self.discard_active_turn(session_id)
        state["status"] = "complete"
        self.persist_state(session_id)
        return state

    def end_session(self, session_id: str) -> PhaseBState:
        state = self.get_state(session_id)
        self._cancel_next_turn_task(session_id)
        state["status"] = "complete"
        self.persist_state(session_id)
        return state

    def _cancel_next_turn_task(self, session_id: str) -> None:
        session = self.get_session(session_id)
        task = session.next_turn_task
        if task is not None and not task.done():
            task.cancel()
        session.next_turn_task = None

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
