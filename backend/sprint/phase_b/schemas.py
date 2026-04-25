"""HTTP request/response schemas and LangGraph state for Phase B conversations."""

from typing import Any, Literal, NotRequired, TypedDict

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Literal types
# ---------------------------------------------------------------------------

Scenario = Literal[
    "interview",
    "negotiation",
    "casual",
    "public_speaking",
]

Persona = Literal[
    "interviewer",
    "negotiator",
    "friend",
    "audience",
]

SCENARIO_TO_PERSONA: dict[str, Persona] = {
    "interview": "interviewer",
    "negotiation": "negotiator",
    "casual": "friend",
    "public_speaking": "audience",
}

ChunkStatus = Literal["pending", "processing", "done", "failed", "timed_out"]

SessionStatus = Literal[
    "active",
    "complete",
    "error",
]


# ---------------------------------------------------------------------------
# LangGraph state  (TypedDict)
# ---------------------------------------------------------------------------

class ChunkRecord(TypedDict):
    """One 5-second analysis window."""

    chunk_index: int
    start_ms: int
    end_ms: int
    mediapipe_metrics: dict[str, Any]
    video_emotions: list[dict[str, Any]] | None
    audio_emotions: list[dict[str, Any]] | None
    status: ChunkStatus


class TurnState(TypedDict):
    """Accumulated data for a single conversation turn."""

    turn_index: int
    prompt_text: str
    recording_start_ms: int | None
    recording_end_ms: int | None
    chunks: list[ChunkRecord]
    transcript: str | None
    transcript_words: list[dict[str, Any]] | None
    merged_summary: dict[str, Any] | None
    critique: str | None


class PhaseBState(TypedDict):
    """Full session state carried through LangGraph and the session store."""

    session_id: str
    scenario: Scenario
    difficulty: int
    persona: Persona
    turn_index: int
    max_turns: int
    conversation_history: list[dict[str, str]]
    current_turn: TurnState | None
    turns: list[TurnState]
    status: SessionStatus
    error: NotRequired[str | None]


def build_initial_state(
    session_id: str,
    scenario: Scenario,
    difficulty: int,
    max_turns: int = 4,
) -> PhaseBState:
    """Create the default state for a new Phase B session."""

    return {
        "session_id": session_id,
        "scenario": scenario,
        "difficulty": difficulty,
        "persona": SCENARIO_TO_PERSONA[scenario],
        "turn_index": 0,
        "max_turns": max_turns,
        "conversation_history": [],
        "current_turn": None,
        "turns": [],
        "status": "active",
    }


def build_turn_state(turn_index: int, prompt_text: str) -> TurnState:
    """Create a blank turn record after prompt generation."""

    return {
        "turn_index": turn_index,
        "prompt_text": prompt_text,
        "recording_start_ms": None,
        "recording_end_ms": None,
        "chunks": [],
        "transcript": None,
        "transcript_words": None,
        "merged_summary": None,
        "critique": None,
    }


# ---------------------------------------------------------------------------
# API request / response models  (Pydantic)
# ---------------------------------------------------------------------------

class StartConversationRequest(BaseModel):
    """Body for POST /api/phase-b/sessions."""

    scenario: Scenario
    difficulty: int = Field(ge=1, le=10)
    max_turns: int = Field(default=4, ge=2, le=5)


class StartConversationResponse(BaseModel):
    """Identifier returned after session creation."""

    session_id: str
    status: SessionStatus = "active"


class SessionStateResponse(BaseModel):
    """Full session state returned by GET /api/phase-b/sessions/{id}."""

    session_id: str
    scenario: Scenario
    difficulty: int
    persona: Persona
    turn_index: int
    max_turns: int
    conversation_history: list[dict[str, str]]
    current_turn: dict[str, Any] | None
    turns: list[dict[str, Any]]
    status: SessionStatus


class ChunkUploadMeta(BaseModel):
    """JSON metadata sent alongside a chunk file upload."""

    chunk_index: int
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    mediapipe_metrics: dict[str, Any] = Field(default_factory=dict)
