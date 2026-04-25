"""Imentiv analysis helpers for Phase C freeform speaking."""

import asyncio
from contextlib import asynccontextmanager
import random
from pathlib import Path
from typing import Any
from uuid import uuid4

from backend.shared.ai.settings import AISettings
from backend.shared.db import get_media_store
from backend.shared.imentiv import analyze_video_file, dominant_emotion


MOCK_EMOTIONS = [
    "happiness", "sadness", "anger", "fear", "surprise",
    "disgust", "contempt", "nervousness", "confidence", "neutral",
]


async def analyze_video(
    settings: AISettings,
    video_source: str | dict[str, Any],
    *,
    title: str,
    description: str,
) -> dict[str, Any]:
    """Upload a local video, poll Imentiv, and return normalized analysis."""

    if settings.imentiv_mock:
        video_emotions = await _mock_emotions()
        audio_emotions = await _mock_emotions()
        return {
            "video_id": f"mock-video-{uuid4().hex[:8]}",
            "status": "completed",
            "summary": "Mock Imentiv analysis.",
            "dominant_emotion": dominant_emotion(video_emotions + audio_emotions),
            "confidence_score": 75.0,
            "clarity_score": 75.0,
            "resilience_score": 75.0,
            "engagement_score": 75.0,
            "video_emotions": video_emotions,
            "audio_emotions": audio_emotions,
            "text_emotions": [],
            "transcript": "",
            "transcript_segments": [],
            "raw": {},
        }
    async with _materialized_media_path(video_source) as video_path:
        return await analyze_video_file(settings, video_path, title=title, description=description)


async def _mock_emotions() -> list[dict[str, Any]]:
    await asyncio.sleep(random.uniform(0.05, 0.2))
    dominant = random.choice(MOCK_EMOTIONS)
    secondaries = random.sample([emotion for emotion in MOCK_EMOTIONS if emotion != dominant], k=2)
    return [
        {"emotion_type": dominant, "confidence": 0.8, "timestamp": 0},
        {"emotion_type": secondaries[0], "confidence": 0.25, "timestamp": 0},
        {"emotion_type": secondaries[1], "confidence": 0.2, "timestamp": 0},
    ]


@asynccontextmanager
async def _materialized_media_path(media_source: str | dict[str, Any]):
    if isinstance(media_source, str):
        yield media_source
        return

    if not isinstance(media_source, dict):
        raise RuntimeError("Media upload metadata was missing.")

    file_id = media_source.get("file_id")
    if not file_id:
        raise RuntimeError("Media file identifier was missing.")

    async with get_media_store().materialize_temp_file(
        file_id=str(file_id),
        suffix=_upload_suffix(media_source),
    ) as media_path:
        yield media_path


def _upload_suffix(upload: dict[str, Any]) -> str:
    filename = str(upload.get("filename") or upload.get("original_filename") or "")
    return Path(filename).suffix or ".webm"
