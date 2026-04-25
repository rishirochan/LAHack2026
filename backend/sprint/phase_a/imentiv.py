"""Imentiv upload and polling helpers."""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx

from backend.shared.db import get_media_store
from backend.shared.ai.settings import AISettings


POLL_TIMEOUT_SECONDS = 60


async def upload_video(settings: AISettings, video_source: str | dict[str, Any]) -> str:
    """Upload video and return the Imentiv video id."""

    async with _materialized_media_path(video_source) as video_path:
        client = _create_sdk_client(settings)
        if client is not None:
            result = await asyncio.to_thread(client.video.upload, video_path)
            return _extract_id(result)

        return await _upload_with_http(
            settings=settings,
            path=video_path,
            endpoint="videos",
            file_field="video_file",
        )


async def upload_audio(settings: AISettings, audio_source: str | dict[str, Any]) -> str:
    """Upload audio and return the Imentiv audio id."""

    async with _materialized_media_path(audio_source) as audio_path:
        client = _create_sdk_client(settings)
        if client is not None:
            result = await asyncio.to_thread(client.audio.upload, audio_path)
            return _extract_id(result)

        return await _upload_with_http(
            settings=settings,
            path=audio_path,
            endpoint="audios",
            file_field="audio_file",
        )


async def get_video_emotions(settings: AISettings, video_id: str) -> list[dict[str, Any]]:
    """Poll Imentiv until video analysis completes or times out."""

    client = _create_sdk_client(settings)
    if client is not None:
        result = await asyncio.wait_for(
            asyncio.to_thread(
                client.video.get_results,
                video_id,
                wait=True,
                poll_interval=2,
            ),
            timeout=POLL_TIMEOUT_SECONDS,
        )
        return extract_emotions(result)

    result = await _poll_with_http(settings=settings, endpoint="videos", item_id=video_id)
    return extract_emotions(result)


async def get_audio_emotions(settings: AISettings, audio_id: str) -> list[dict[str, Any]]:
    """Poll Imentiv until audio analysis completes or times out."""

    client = _create_sdk_client(settings)
    if client is not None:
        result = await asyncio.wait_for(
            asyncio.to_thread(
                client.audio.get_results,
                audio_id,
                wait=True,
                poll_interval=2,
            ),
            timeout=POLL_TIMEOUT_SECONDS,
        )
        return extract_emotions(result)

    result = await _poll_with_http(settings=settings, endpoint="audios", item_id=audio_id)
    return extract_emotions(result)


def extract_emotions(response: Any) -> list[dict[str, Any]]:
    """Normalize emotion events from common SDK/API response shapes."""

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
            return [_normalize_emotion_event(event) for event in candidate if isinstance(event, dict)]
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


def _create_sdk_client(settings: AISettings) -> Any | None:
    try:
        from imentiv import ImentivClient  # type: ignore
    except ImportError:
        try:
            from imentiv import Imentiv  # type: ignore
        except ImportError:
            return None
        return Imentiv(api_key=settings.imentiv_api_key)

    return ImentivClient(api_key=settings.imentiv_api_key)


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

