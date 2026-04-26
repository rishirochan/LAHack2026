"""HTTP request/response schemas and LangGraph state for Phase B conversations."""

from typing import Any, Literal, NotRequired, TypedDict

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Literal types
# ---------------------------------------------------------------------------

Scenario = Literal[
    "interview",
    "negotiation",
    "casual",
    "networking",
    "roommate",
]

ChunkStatus = Literal["pending", "processing", "done", "failed", "timed_out"]
TurnAnalysisStatus = Literal["pending", "partial", "ready"]

SessionStatus = Literal[
    "active",
    "complete",
    "error",
]

PRACTICE_PROMPT_WORD_LIMIT = 60


def _count_words(value: str) -> int:
    normalized = " ".join(value.split()).strip()
    if not normalized:
        return 0
    return len(normalized.split(" "))


class PeerProfile(TypedDict):
    """Generated profile for the simulated conversation partner."""

    name: str
    role: str
    vibe: str
    energy: str
    conversation_goal: str
    scenario: str


class MomentumDecision(TypedDict):
    """Decision returned after the minimum turn count is met."""

    continue_conversation: bool
    reason: str
    based_on_turn_index: int


class TurnAnalysis(TypedDict):
    """Per-turn analysis using local conversational context."""

    analysis_status: TurnAnalysisStatus
    summary: str
    momentum_score: int
    content_quality_score: int
    emotional_delivery_score: int
    energy_match_score: int
    authenticity_score: int
    follow_up_invitation_score: int
    strengths: list[str]
    growth_edges: list[str]


class FinalReport(TypedDict):
    """Full-session report built from transcripts and Imentiv outputs."""

    summary: str
    natural_ending_reason: str
    conversation_momentum_score: int
    content_quality_score: int
    emotional_delivery_score: int
    energy_match_score: int
    authenticity_score: int
    follow_up_invitation_score: int
    strengths: list[str]
    growth_edges: list[str]
    next_focus: str


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
    text_emotions: NotRequired[list[dict[str, Any]] | None]
    status: ChunkStatus
    video_upload: NotRequired[dict[str, Any] | None]
    audio_upload: NotRequired[dict[str, Any] | None]
    imentiv_analysis: NotRequired[dict[str, Any] | None]
    error: NotRequired[str | None]


class TurnState(TypedDict):
    """Accumulated data for a single conversation turn."""

    turn_index: int
    prompt_text: str
    recording_start_ms: int | None
    recording_end_ms: int | None
    chunks: list[ChunkRecord]
    transcript: str | None
    transcript_words: list[dict[str, Any]] | None
    transcript_audio_upload: dict[str, Any] | None
    imentiv_analysis: dict[str, Any] | None
    merged_summary: dict[str, Any] | None
    turn_analysis: TurnAnalysis | None
    analysis_status: TurnAnalysisStatus
    critique: str | None


class PhaseBState(TypedDict):
    """Full session state carried through LangGraph and the session store."""

    session_id: str
    practice_prompt: str | None
    scenario: str | None
    scenario_preference: Scenario | None
    voice_id: str | None
    peer_profile: PeerProfile | None
    starter_topic: str | None
    opening_line: str | None
    turn_index: int
    max_turns: int
    minimum_turns: int
    conversation_history: list[dict[str, str]]
    current_turn: TurnState | None
    turns: list[TurnState]
    momentum_decision: MomentumDecision | None
    final_report: FinalReport | None
    status: SessionStatus
    error: NotRequired[str | None]


def build_initial_state(
    session_id: str,
    scenario_preference: Scenario | None = None,
    max_turns: int = 6,
    minimum_turns: int = 3,
    voice_id: str | None = None,
    practice_prompt: str | None = None,
) -> PhaseBState:
    """Create the default state for a new Phase B session."""

    return {
        "session_id": session_id,
        "practice_prompt": practice_prompt,
        "scenario": None,
        "scenario_preference": scenario_preference,
        "voice_id": voice_id,
        "peer_profile": None,
        "starter_topic": None,
        "opening_line": None,
        "turn_index": 0,
        "max_turns": max_turns,
        "minimum_turns": minimum_turns,
        "conversation_history": [],
        "current_turn": None,
        "turns": [],
        "momentum_decision": None,
        "final_report": None,
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
        "transcript_audio_upload": None,
        "imentiv_analysis": None,
        "merged_summary": None,
        "turn_analysis": None,
        "analysis_status": "pending",
        "critique": None,
    }


# ---------------------------------------------------------------------------
# API request / response models  (Pydantic)
# ---------------------------------------------------------------------------

class StartConversationRequest(BaseModel):
    """Body for POST /api/phase-b/sessions."""

    practice_prompt: str | None = None
    scenario_preference: Scenario | None = None
    voice_id: str | None = None
    speak_peer_message: bool = True
    max_turns: int = Field(default=6, ge=3, le=8)
    minimum_turns: int = Field(default=3, ge=3, le=5)

    @field_validator("practice_prompt")
    @classmethod
    def validate_practice_prompt(cls, value: str | None) -> str | None:
        if value is None:
            return None

        normalized = " ".join(value.split()).strip()
        if not normalized:
            return None
        if _count_words(normalized) > PRACTICE_PROMPT_WORD_LIMIT:
            raise ValueError(
                f"Practice prompt must be {PRACTICE_PROMPT_WORD_LIMIT} words or fewer."
            )
        return normalized


class NextTurnRequest(BaseModel):
    """Optional per-turn overrides for the next peer reply."""

    voice_id: str | None = None
    speak_peer_message: bool = True


class StartConversationResponse(BaseModel):
    """Identifier returned after session creation."""

    session_id: str
    status: SessionStatus = "active"


class SessionStateResponse(BaseModel):
    """Full session state returned by GET /api/phase-b/sessions/{id}."""

    session_id: str
    practice_prompt: str | None
    scenario: str | None
    scenario_preference: Scenario | None
    voice_id: str | None
    peer_profile: dict[str, Any] | None
    starter_topic: str | None
    opening_line: str | None
    turn_index: int
    max_turns: int
    minimum_turns: int
    conversation_history: list[dict[str, str]]
    current_turn: dict[str, Any] | None
    turns: list[dict[str, Any]]
    momentum_decision: dict[str, Any] | None
    final_report: dict[str, Any] | None
    status: SessionStatus


class ChunkUploadMeta(BaseModel):
    """JSON metadata sent alongside a chunk file upload."""

    chunk_index: int
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    mediapipe_metrics: dict[str, Any] = Field(default_factory=dict)
