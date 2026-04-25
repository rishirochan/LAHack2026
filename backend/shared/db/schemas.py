"""Persisted MongoDB document shapes for practice analytics."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


SessionMode = Literal["phase_a", "phase_b"]
SessionStatus = Literal["active", "complete", "error"]


class MediaUploadDocument(BaseModel):
    """Metadata for one persisted media file."""

    file_id: str | None = None
    storage_key: str
    filename: str
    original_filename: str
    mime_type: str
    size_bytes: int
    uploaded_at: str
    download_url: str | None = None


class MediaReferenceDocument(BaseModel):
    """Durable session-linked reference to one upload."""

    kind: str
    upload: MediaUploadDocument
    round_index: int | None = None
    turn_index: int | None = None
    chunk_index: int | None = None
    download_url: str | None = None


class PracticeSessionDocument(BaseModel):
    """Top-level practice session document stored in MongoDB."""

    session_id: str
    user_id: str = "demo-user"
    mode: SessionMode
    mode_label: str
    status: str = "active"
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    setup: dict[str, Any] = Field(default_factory=dict)
    rounds: list[dict[str, Any]] = Field(default_factory=list)
    summary: dict[str, Any] | None = None
    media_refs: list[MediaReferenceDocument] = Field(default_factory=list)
    raw_state: dict[str, Any] = Field(default_factory=dict)


class SessionChunkDocument(BaseModel):
    """Normalized per-chunk analytics document for trend queries."""

    session_id: str
    user_id: str = "demo-user"
    mode: Literal["phase_b"] = "phase_b"
    scenario: str | None = None
    turn_index: int
    chunk_index: int
    start_ms: int
    end_ms: int
    status: str
    mediapipe_metrics: dict[str, Any] = Field(default_factory=dict)
    video_emotions: list[dict[str, Any]] = Field(default_factory=list)
    audio_emotions: list[dict[str, Any]] = Field(default_factory=list)
    transcript_segment: str = ""
    merged_summary: dict[str, Any] | None = None
    video_upload: MediaUploadDocument | None = None
    audio_upload: MediaUploadDocument | None = None
    dominant_video_emotion: str | None = None
    video_confidence: float | None = None
    dominant_audio_emotion: str | None = None
    audio_confidence: float | None = None
    eye_contact_pct: float | None = None
    created_at: datetime
    updated_at: datetime


class TrendSnapshotDocument(BaseModel):
    """Computed trend response across a user's historical chunks."""

    user_id: str
    session_count: int = 0
    chunk_count: int = 0
    average_eye_contact_pct: float | None = None
    dominant_video_emotions: dict[str, int] = Field(default_factory=dict)
    dominant_audio_emotions: dict[str, int] = Field(default_factory=dict)
    chunks_failed: int = 0
    chunks_timed_out: int = 0
    score_history: list[dict[str, Any]] = Field(default_factory=list)
