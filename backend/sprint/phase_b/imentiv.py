"""Imentiv analysis helpers for Phase B conversations."""

import asyncio
from contextlib import asynccontextmanager
import random
from pathlib import Path
from typing import Any
from uuid import uuid4

from backend.shared.ai.settings import AISettings
from backend.shared.db import get_media_store
from backend.shared.imentiv import analyze_audio_file, dominant_emotion


MOCK_EMOTIONS = [
    "happiness", "sadness", "anger", "fear", "surprise",
    "disgust", "contempt", "nervousness", "confidence", "neutral",
]


async def analyze_audio(
    settings: AISettings,
    audio_source: str | dict[str, Any],
    *,
    title: str,
    description: str,
) -> dict[str, Any]:
    """Upload chunk audio, poll Imentiv, and return tone + transcript analysis."""

    if settings.imentiv_mock:
        audio_emotions = await _mock_emotions()
        text_emotions = await _mock_emotions()
        return {
            "audio_id": f"mock-audio-{uuid4().hex[:8]}",
            "status": "completed",
            "summary": "Mock Imentiv audio analysis.",
            "dominant_emotion": dominant_emotion(audio_emotions + text_emotions),
            "confidence_score": 75.0,
            "clarity_score": 75.0,
            "resilience_score": 75.0,
            "engagement_score": 75.0,
            "video_emotions": [],
            "audio_emotions": audio_emotions,
            "text_emotions": text_emotions,
            "transcript": "",
            "transcript_segments": [],
            "is_mock": True,
            "raw": {},
        }

    async with _materialized_media_path(audio_source) as audio_path:
        return await analyze_audio_file(settings, audio_path, title=title, description=description)


async def analyze_video(
    settings: AISettings,
    video_source: str | dict[str, Any],
    *,
    title: str,
    description: str,
) -> dict[str, Any]:
    """Backward-compatible alias while Phase B switches to audio-led analysis."""

    return await analyze_audio(settings, video_source, title=title, description=description)


async def _mock_emotions() -> list[dict[str, Any]]:
    """Return realistic fake emotion data after a short delay."""

    await asyncio.sleep(random.uniform(0.3, 1.0))
    dominant = random.choice(MOCK_EMOTIONS)
    secondaries = random.sample([emotion for emotion in MOCK_EMOTIONS if emotion != dominant], k=random.randint(2, 3))

    events: list[dict[str, Any]] = [
        {
            "emotion_type": dominant,
            "confidence": round(random.uniform(0.55, 0.95), 2),
            "timestamp": 0,
        }
    ]
    for emotion in secondaries:
        events.append(
            {
                "emotion_type": emotion,
                "confidence": round(random.uniform(0.10, 0.45), 2),
                "timestamp": 0,
            }
        )
    return events


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
