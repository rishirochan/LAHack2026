"""HTTP and websocket schemas for Phase A emotion drills."""

from typing import Any, Literal

from pydantic import BaseModel, Field


TargetEmotion = Literal[
    "Anger",
    "Contempt",
    "Disgust",
    "Fear",
    "Happiness",
    "Neutrality (Neutral)",
    "Sadness",
    "Surprise",
]
SessionStatus = Literal[
    "setup",
    "scenario",
    "recording",
    "processing",
    "critique",
    "summary",
    "error",
]


class StartSessionRequest(BaseModel):
    """Initial state supplied by the frontend."""

    target_emotion: TargetEmotion


class StartSessionResponse(BaseModel):
    """Identifier used for websocket and follow-up requests."""

    session_id: str
    status: SessionStatus = "scenario"


class ContinueSessionRequest(BaseModel):
    """Frontend decision after a critique finishes playing."""

    continue_session: bool


class ContinueSessionResponse(BaseModel):
    """Acknowledges the user decision for the active graph run."""

    session_id: str
    continue_session: bool


class DisplayMetric(BaseModel):
    """Compact deterministic metric rendered directly in the UI."""

    key: str
    label: str
    value: float | int | str | None = None
    display_value: str
    description: str


class RoundSummary(BaseModel):
    """Summary data kept in memory for one completed round."""

    scenario_prompt: str
    critique: str
    match_score: float
    filler_words_found: list[str]
    filler_word_count: int
    derived_metrics: dict[str, Any] = Field(default_factory=dict)
    display_metrics: list[DisplayMetric] = Field(default_factory=list)


class SessionSummaryResponse(BaseModel):
    """Summary payload rendered by the frontend after ending a session."""

    session_id: str
    critiques: list[str]
    match_scores: list[float]
    filler_words: dict[str, int]
    rounds: list[RoundSummary]


class WebsocketEvent(BaseModel):
    """Small JSON envelope for all realtime UI messages."""

    type: str
    payload: dict[str, Any] = Field(default_factory=dict)

