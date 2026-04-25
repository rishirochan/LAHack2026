"""Imentiv analysis helpers for Phase C freeform speaking."""

import asyncio
import random
from typing import Any
from uuid import uuid4

from backend.shared.ai.settings import AISettings
from backend.shared.imentiv import analyze_video_file, dominant_emotion


MOCK_EMOTIONS = [
    "happiness", "sadness", "anger", "fear", "surprise",
    "disgust", "contempt", "nervousness", "confidence", "neutral",
]


async def analyze_video(settings: AISettings, video_path: str, *, title: str, description: str) -> dict[str, Any]:
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
