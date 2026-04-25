"""
Response model classes for API responses.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class VideoInfo:
    """Information about an uploaded video."""

    video_id: str
    status: str
    created_at: Optional[str] = None
    duration: Optional[float] = None
    size: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VideoInfo":
        """Create a VideoInfo instance from a dictionary."""
        return cls(
            video_id=data.get("video_id", ""),
            status=data.get("status", ""),
            created_at=data.get("created_at"),
            duration=data.get("duration"),
            size=data.get("size"),
            metadata=data.get("metadata"),
        )


@dataclass
class Emotion:
    """Detected emotion with confidence score."""

    emotion_type: str
    confidence: float
    timestamp: Optional[float] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Emotion":
        """Create an Emotion instance from a dictionary."""
        return cls(
            emotion_type=data.get("emotion_type", data.get("type", "")),
            confidence=data.get("confidence", 0.0),
            timestamp=data.get("timestamp"),
        )


@dataclass
class Face:
    """Detected face with bounding box and attributes."""

    x: int
    y: int
    width: int
    height: int
    confidence: float
    attributes: Optional[Dict[str, Any]] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Face":
        """Create a Face instance from a dictionary."""
        return cls(
            x=data.get("x", 0),
            y=data.get("y", 0),
            width=data.get("width", 0),
            height=data.get("height", 0),
            confidence=data.get("confidence", 0.0),
            attributes=data.get("attributes"),
        )


@dataclass
class AnalysisResult:
    """Complete analysis result for a video."""

    video_id: str
    status: str
    emotions: List[Emotion]
    faces: List[Face]
    summary: Optional[Dict[str, Any]] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AnalysisResult":
        """Create an AnalysisResult instance from a dictionary."""
        emotions_data = data.get("emotions", [])
        faces_data = data.get("faces", [])

        return cls(
            video_id=data.get("video_id", ""),
            status=data.get("status", ""),
            emotions=[Emotion.from_dict(e) for e in emotions_data],
            faces=[Face.from_dict(f) for f in faces_data],
            summary=data.get("summary"),
        )
