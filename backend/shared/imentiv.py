"""Backend-only Imentiv client helpers and result normalization."""

from __future__ import annotations

import asyncio
import logging
import os
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import requests

from imentiv import ImentivAuthenticationError, ImentivClient

from backend.shared.ai.settings import AISettings

logger = logging.getLogger(__name__)

_client: ImentivClient | None = None


def get_imentiv_client() -> ImentivClient:
    """Return the process-wide Imentiv SDK client."""

    global _client
    if _client is None:
        api_key = os.getenv("IMENTIV_API_KEY")
        if not api_key:
            raise ValueError("IMENTIV_API_KEY environment variable is not set")
        _client = ImentivClient(
            api_key=api_key,
            timeout=120,
            max_retries=3,
        )
    return _client


async def analyze_video_file(
    settings: AISettings,
    file_path: str,
    *,
    title: str,
    description: str,
) -> dict[str, Any]:
    """Upload a local video file, wait for Imentiv analysis, and normalize it."""

    os.environ.setdefault("IMENTIV_API_KEY", settings.imentiv_api_key)
    client = get_imentiv_client()
    try:
        upload_result = await asyncio.to_thread(
            client.video.upload,
            file_path,
            title=title,
            description=description,
            user_consent_version=settings.imentiv_user_consent_version,
        )
    except ImentivAuthenticationError:
        logger.exception("Imentiv authentication failed while uploading %s.", Path(file_path).name)
        raise RuntimeError("Imentiv authentication failed. Check IMENTIV_API_KEY.") from None

    logger.debug("Imentiv upload response keys=%s", sorted(upload_result.keys()))
    video_id = extract_video_id(upload_result)
    await asyncio.sleep(0.75)

    try:
        results = await asyncio.to_thread(
            client.video.get_results,
            video_id,
            wait=True,
            poll_interval=1.5,
        )
    except ImentivAuthenticationError:
        logger.exception("Imentiv authentication failed while polling video %s.", video_id)
        raise RuntimeError("Imentiv authentication failed. Check IMENTIV_API_KEY.") from None

    logger.debug(
        "Imentiv analysis response keys=%s status=%s",
        sorted(results.keys()),
        results.get("status"),
    )
    if str(results.get("status") or "").lower() == "failed":
        raise RuntimeError(f"Imentiv analysis failed for video {video_id}.")

    audio_segments: list[dict[str, Any]] = []
    audio_id = results.get("audio_id")
    if audio_id:
        audio_segments = await asyncio.to_thread(fetch_audio_segments, settings, str(audio_id))

    normalized = normalize_imentiv_results(results, transcript_segments=audio_segments)
    normalized["video_id"] = video_id
    if audio_id:
        normalized["audio_id"] = str(audio_id)
    return normalized


def extract_video_id(upload_result: Any) -> str:
    """Read a video id from either new or legacy Imentiv upload responses."""

    data = _to_mapping(upload_result)
    video_id = data.get("video_id") or data.get("id")
    if not video_id:
        raise RuntimeError("Imentiv upload response did not include a video_id.")
    return str(video_id)


def fetch_audio_segments(settings: AISettings, audio_id: str) -> list[dict[str, Any]]:
    """Fetch text-emotion transcript segments produced for a video's audio track."""

    url = f"https://api.imentiv.ai/v1/audios/{audio_id}"
    headers = {"X-API-Key": settings.imentiv_api_key}
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            response = requests.get(url, headers=headers, timeout=120)
            if response.status_code in (404, 500, 502, 503, 504):
                logger.debug("Imentiv audio %s segments processing: status=%s", audio_id, response.status_code)
                time.sleep(1.5 * (attempt + 1))
                continue
            response.raise_for_status()
            logger.debug("Imentiv audio %s response keys=%s", audio_id, sorted(response.json().keys()))
            return extract_transcript_segments(response.json())
        except requests.RequestException as error:
            last_error = error
            logger.debug("Imentiv audio %s segment fetch retry %s: %s", audio_id, attempt + 1, error)
            time.sleep(1.5 * (attempt + 1))
    if last_error:
        logger.warning("Imentiv audio %s segment fetch failed: %s", audio_id, last_error)
    return []

def extract_transcript_segments(audio_result: Any) -> list[dict[str, Any]]:
    """Normalize Imentiv segment_text_emotions into app transcript segments."""

    data = _to_mapping(audio_result)
    segments = data.get("segment_text_emotions")
    if not isinstance(segments, list):
        segments = _nested_get(data, ("results", "segment_text_emotions"))
    if not isinstance(segments, list):
        return []

    normalized: list[dict[str, Any]] = []
    for segment in segments:
        if not isinstance(segment, dict):
            continue
        dominant = _to_mapping(segment.get("dominant_emotion"))
        normalized.append(
            {
                "start": float(segment.get("start_millis") or 0) / 1000,
                "end": float(segment.get("end_millis") or 0) / 1000,
                "text": str(segment.get("sentence") or ""),
                "emotion": dominant.get("label") or dominant.get("name") or segment.get("emotion"),
                "raw_emotions": segment.get("emotions") or [],
            }
        )
    return normalized


def normalize_imentiv_results(
    results: Any,
    *,
    transcript_segments: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Convert Imentiv's multimodal response into the app's analysis shape."""

    data = _to_mapping(results)
    transcript_segments = transcript_segments or _extract_segments_from_results(data)
    transcript = data.get("transcript")
    if not isinstance(transcript, str) or not transcript.strip():
        transcript = " ".join(
            str(segment.get("text") or segment.get("sentence") or "").strip()
            for segment in transcript_segments
            if isinstance(segment, dict)
        ).strip()

    dominant_emotion = _normalize_dominant_emotion(data.get("dominant_emotion"))
    video_emotions = extract_emotion_events(data, preferred_keys=("video_emotions", "emotion_analysis", "emotions"))
    audio_emotions = extract_emotion_events(data, preferred_keys=("audio", "audio_emotions"))
    text_emotions = extract_emotion_events(data, preferred_keys=("text", "text_emotions"))
    scores = _extract_or_derive_scores(data, video_emotions + audio_emotions + text_emotions)

    return {
        "status": data.get("status"),
        "transcript": transcript,
        "transcript_segments": transcript_segments,
        "summary": data.get("summary"),
        "dominant_emotion": dominant_emotion,
        "confidence_score": scores["confidence_score"],
        "clarity_score": scores["clarity_score"],
        "resilience_score": scores["resilience_score"],
        "engagement_score": scores["engagement_score"],
        "video_emotions": video_emotions,
        "audio_emotions": audio_emotions,
        "text_emotions": text_emotions,
        "raw": data,
    }


def extract_emotion_events(data: Any, *, preferred_keys: tuple[str, ...] = ()) -> list[dict[str, Any]]:
    """Flatten common Imentiv emotion blobs into app emotion events."""

    root = _to_mapping(data)
    candidates: list[Any] = []
    for key in preferred_keys:
        value = root.get(key)
        candidates.append(value)
        if isinstance(value, dict):
            candidates.extend([value.get("overall"), value.get("emotions"), value.get("timeline")])
    candidates.extend(
        [
            root.get("video_emotions"),
            root.get("emotions"),
            _nested_get(root, ("emotion_analysis", "overall")),
            _nested_get(root, ("multimodal_analytics", "emotions")),
            _nested_get(root, ("results", "emotions")),
        ]
    )

    events: list[dict[str, Any]] = []
    for candidate in candidates:
        events.extend(_flatten_emotion_blob(candidate))
    return events


def _extract_or_derive_scores(data: dict[str, Any], emotions: list[dict[str, Any]]) -> dict[str, float]:
    score_keys = ("confidence_score", "clarity_score", "resilience_score", "engagement_score")
    scores: dict[str, float] = {}
    for key in score_keys:
        value = data.get(key)
        if isinstance(value, int | float):
            scores[key] = float(value)
    if len(scores) == len(score_keys):
        return scores

    derived = _derive_scores_from_emotions(emotions)
    for key in score_keys:
        scores.setdefault(key, derived[key])
    return scores


def _derive_scores_from_emotions(emotions: list[dict[str, Any]]) -> dict[str, float]:
    totals: defaultdict[str, float] = defaultdict(float)
    for event in emotions:
        label = str(event.get("emotion_type") or "").lower()
        totals[label] += float(event.get("confidence") or 0)

    total = sum(totals.values()) or 1.0

    def ratio(*labels: str) -> float:
        return max(0.0, min(100.0, 100.0 * sum(totals[label] for label in labels) / total))

    return {
        "confidence_score": ratio("confidence", "confident", "happiness", "happy", "neutral"),
        "clarity_score": ratio("neutral", "confidence", "confident", "calm"),
        "resilience_score": ratio("neutral", "confidence", "confident", "happiness", "happy", "calm"),
        "engagement_score": ratio("happiness", "happy", "surprise", "confidence", "confident"),
    }


def _flatten_emotion_blob(blob: Any) -> list[dict[str, Any]]:
    if isinstance(blob, list):
        return [_normalize_emotion_event(item) for item in blob if isinstance(item, dict)]
    if isinstance(blob, dict):
        if any(key in blob for key in ("emotion_type", "emotion", "label", "name")):
            return [_normalize_emotion_event(blob)]
        if all(isinstance(value, int | float) for value in blob.values()):
            return [
                {"emotion_type": str(label), "confidence": float(score), "timestamp": 0}
                for label, score in blob.items()
            ]
        events: list[dict[str, Any]] = []
        for value in blob.values():
            events.extend(_flatten_emotion_blob(value))
        return events
    return []


def _normalize_emotion_event(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "emotion_type": event.get("emotion_type") or event.get("emotion") or event.get("label") or event.get("name"),
        "confidence": float(event.get("confidence") or event.get("score") or event.get("probability") or 0),
        "timestamp": int(event.get("timestamp") or event.get("time_ms") or event.get("start_millis") or 0),
    }


def _extract_segments_from_results(data: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("transcript_segments", "segments"):
        value = data.get(key)
        if isinstance(value, list):
            return [segment for segment in value if isinstance(segment, dict)]
    return extract_transcript_segments(data)


def _normalize_dominant_emotion(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    data = _to_mapping(value)
    if data:
        label = data.get("name") or data.get("label") or data.get("emotion_type")
        return str(label) if label else None
    return None


def _to_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    return {}


def _nested_get(data: dict[str, Any], keys: tuple[str, ...]) -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def dominant_emotion(events: list[dict[str, Any]]) -> str | None:
    """Return the highest-confidence emotion label from normalized events."""

    totals = Counter()
    for event in events:
        label = event.get("emotion_type")
        if label:
            totals[str(label)] += float(event.get("confidence") or 0)
    if not totals:
        return None
    return totals.most_common(1)[0][0]
