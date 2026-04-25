"""Imentiv upload and polling helpers for Phase B conversations.

When ``IMENTIV_MOCK=true`` (the default for development), all calls return
realistic fake emotion data with a short simulated delay instead of hitting
the real API.  Set ``IMENTIV_MOCK=false`` and supply a valid
``IMENTIV_API_KEY`` to use the real Imentiv service.
"""

import asyncio
from contextlib import asynccontextmanager
import os
import random
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx

from backend.shared.db import get_media_store
from backend.shared.ai.settings import AISettings


POLL_TIMEOUT_SECONDS = 60

MOCK_EMOTIONS = [
    "happiness", "sadness", "anger", "fear", "surprise",
    "disgust", "contempt", "nervousness", "confidence", "neutral",
]


def _is_mock_mode() -> bool:
    return os.environ.get("IMENTIV_MOCK", "true").lower() in ("true", "1", "yes")


# ------------------------------------------------------------------
# Public API  — each checks mock mode first
# ------------------------------------------------------------------

async def upload_video(settings: AISettings, video_source: str | dict[str, Any]) -> str:
    """Upload video and return the Imentiv video id."""

    if _is_mock_mode():
        return f"mock-video-{uuid4().hex[:8]}"

    async with _materialized_media_path(video_source) as video_path:
        return await _upload_with_http(
            settings=settings,
            path=video_path,
            endpoint="videos",
            file_field="video_file",
        )


async def upload_audio(settings: AISettings, audio_source: str | dict[str, Any]) -> str:
    """Upload audio and return the Imentiv audio id."""

    if _is_mock_mode():
        return f"mock-audio-{uuid4().hex[:8]}"

    async with _materialized_media_path(audio_source) as audio_path:
        return await _upload_with_http(
            settings=settings,
            path=audio_path,
            endpoint="audios",
            file_field="audio_file",
        )


async def get_video_emotions(settings: AISettings, video_id: str) -> list[dict[str, Any]]:
    """Poll Imentiv until video analysis completes or times out."""

    if _is_mock_mode():
        return await _mock_emotions()

    result = await _poll_with_http(settings=settings, endpoint="videos", item_id=video_id)
    return extract_emotions(result)


async def get_audio_emotions(settings: AISettings, audio_id: str) -> list[dict[str, Any]]:
    """Poll Imentiv until audio analysis completes or times out."""

    if _is_mock_mode():
        return await _mock_emotions()

    result = await _poll_with_http(settings=settings, endpoint="audios", item_id=audio_id)
    return extract_emotions(result)


# ------------------------------------------------------------------
# Mock helpers
# ------------------------------------------------------------------

async def _mock_emotions() -> list[dict[str, Any]]:
    """Return realistic fake emotion data after a short delay."""

    await asyncio.sleep(random.uniform(0.3, 1.0))

    # Pick a dominant emotion and 2-3 secondary emotions
    dominant = random.choice(MOCK_EMOTIONS)
    secondaries = random.sample(
        [e for e in MOCK_EMOTIONS if e != dominant],
        k=random.randint(2, 3),
    )

    events: list[dict[str, Any]] = [
        {
            "emotion_type": dominant,
            "confidence": round(random.uniform(0.55, 0.95), 2),
            "timestamp": 0,
        }
    ]
    for emotion in secondaries:
        events.append({
            "emotion_type": emotion,
            "confidence": round(random.uniform(0.10, 0.45), 2),
            "timestamp": 0,
        })

    return events


# ------------------------------------------------------------------
# Real API helpers
# ------------------------------------------------------------------

def extract_emotions(response: Any) -> list[dict[str, Any]]:
    """Normalize emotion events from common API response shapes."""

    data = _to_mapping(response)
    candidates = [
        data.get("emotions"),
        data.get("emotion_timeline"),
        data.get("multimodal_analytics", {}).get("emotions")
        if isinstance(data.get("multimodal_analytics"), dict)
        else None,
        data.get("results", {}).get("emotions")
        if isinstance(data.get("results"), dict)
        else None,
    ]

    for candidate in candidates:
        if isinstance(candidate, list):
            return [_normalize_emotion_event(e) for e in candidate if isinstance(e, dict)]
    return []


async def _upload_with_http(
    *,
    settings: AISettings,
    path: str,
    endpoint: str,
    file_field: str,
) -> str:
    headers = {"Authorization": f"Bearer {settings.imentiv_api_key}"}
    url = f"{settings.imentiv_base_url.rstrip('/')}/{endpoint}"

    with Path(path).open("rb") as file_handle:
        files = {file_field: (Path(path).name, file_handle)}
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(url, headers=headers, files=files)
            response.raise_for_status()
            return _extract_id(response.json())


async def _poll_with_http(
    *,
    settings: AISettings,
    endpoint: str,
    item_id: str,
) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {settings.imentiv_api_key}"}
    url = (
        f"{settings.imentiv_base_url.rstrip('/')}/{endpoint}/"
        f"{item_id}/multimodal-analytics"
    )
    deadline = asyncio.get_running_loop().time() + POLL_TIMEOUT_SECONDS

    async with httpx.AsyncClient(timeout=30) as client:
        latest: dict[str, Any] = {}
        while asyncio.get_running_loop().time() < deadline:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            latest = response.json()
            if str(latest.get("status", "")).lower() == "completed":
                return latest
            await asyncio.sleep(2)
        return latest


def _extract_id(response: Any) -> str:
    data = _to_mapping(response)
    item_id = data.get("id") or data.get("video_id") or data.get("audio_id")
    if not item_id:
        raise RuntimeError("Imentiv upload response did not include an id.")
    return str(item_id)


def _to_mapping(response: Any) -> dict[str, Any]:
    if isinstance(response, dict):
        return response
    if hasattr(response, "model_dump"):
        return response.model_dump()
    if hasattr(response, "dict"):
        return response.dict()
    if hasattr(response, "__dict__"):
        return vars(response)
    return {}


def _normalize_emotion_event(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "emotion_type": event.get("emotion_type") or event.get("emotion") or event.get("label"),
        "confidence": float(event.get("confidence") or event.get("score") or 0),
        "timestamp": int(event.get("timestamp") or event.get("time_ms") or 0),
    }


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
