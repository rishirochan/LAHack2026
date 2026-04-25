"""Schemas and state types for Phase C freeform speaking."""

from typing import Any, Literal, NotRequired, TypedDict

from pydantic import BaseModel, Field


ChunkStatus = Literal["pending", "processing", "done", "failed", "timed_out"]
SessionStatus = Literal["active", "complete", "error"]


class ChunkRecord(TypedDict):
    chunk_index: int
    start_ms: int
    end_ms: int
    mediapipe_metrics: dict[str, Any]
    video_emotions: list[dict[str, Any]] | None
    audio_emotions: list[dict[str, Any]] | None
    status: ChunkStatus


class RecordingState(TypedDict):
    recording_start_ms: int | None
    recording_end_ms: int | None
    chunks: list[ChunkRecord]
    transcript: str | None
    transcript_words: list[dict[str, Any]] | None
    merged_analysis: dict[str, Any] | None
    scorecard: dict[str, Any] | None
    written_summary: str | None


class PhaseCState(TypedDict):
    session_id: str
    difficulty: int
    status: SessionStatus
    current_recording: RecordingState | None
    completed_recording: RecordingState | None
    error: NotRequired[str | None]


def build_recording_state() -> RecordingState:
    return {
        "recording_start_ms": None,
        "recording_end_ms": None,
        "chunks": [],
        "transcript": None,
        "transcript_words": None,
        "merged_analysis": None,
        "scorecard": None,
        "written_summary": None,
    }


def build_initial_state(session_id: str, difficulty: int) -> PhaseCState:
    return {
        "session_id": session_id,
        "difficulty": difficulty,
        "status": "active",
        "current_recording": None,
        "completed_recording": None,
        "error": None,
    }


class StartPhaseCSessionRequest(BaseModel):
    difficulty: int = Field(ge=1, le=10)


class StartPhaseCSessionResponse(BaseModel):
    session_id: str
    status: SessionStatus = "active"


class PhaseCSessionStateResponse(BaseModel):
    session_id: str
    difficulty: int
    status: SessionStatus
    current_recording: dict[str, Any] | None
    completed_recording: dict[str, Any] | None
