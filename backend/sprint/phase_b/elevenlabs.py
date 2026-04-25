"""ElevenLabs TTS streaming and STT helpers for Phase B conversations."""

import asyncio
import base64
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator

from backend.shared.db import get_media_store
from backend.shared.ai.service import AIServiceFacade


async def stream_tts_chunks(
    *,
    ai_service: AIServiceFacade,
    text: str,
    voice_id: str | None = None,
) -> AsyncIterator[str]:
    """Yield base64-encoded MP3 audio chunks for websocket transport.

    If *voice_id* is ``None`` the configured default voice is used.
    """

    effective_voice = voice_id or ai_service.settings.elevenlabs_default_voice_id
    chunks = await asyncio.to_thread(_collect_tts_chunks, ai_service, text, effective_voice)
    for chunk in chunks:
        yield base64.b64encode(chunk).decode("ascii")


async def transcribe_audio(
    *,
    ai_service: AIServiceFacade,
    audio_source: str | dict[str, Any],
) -> tuple[str, list[dict[str, Any]]]:
    """Transcribe audio with word-level timestamps via ElevenLabs STT."""

    async with _materialized_audio_path(audio_source) as audio_path:
        response = await asyncio.to_thread(_transcribe_audio_sync, ai_service, audio_path)
        return _extract_transcript(response), _extract_words(response)


# ------------------------------------------------------------------
# TTS internals
# ------------------------------------------------------------------

def _collect_tts_chunks(
    ai_service: AIServiceFacade,
    text: str,
    voice_id: str,
) -> list[bytes]:
    client = ai_service.elevenlabs_client
    settings = ai_service.settings

    if hasattr(client, "text_to_speech") and hasattr(client.text_to_speech, "stream"):
        stream = client.text_to_speech.stream(
            voice_id=voice_id,
            model_id=settings.elevenlabs_tts_model,
            text=text,
        )
    elif hasattr(client, "generate"):
        stream = client.generate(
            text=text,
            voice=voice_id,
            model=settings.elevenlabs_tts_model,
            stream=True,
        )
    else:
        raise RuntimeError("ElevenLabs client does not expose a TTS streaming method.")

    return [chunk for chunk in stream if isinstance(chunk, bytes)]


# ------------------------------------------------------------------
# STT internals
# ------------------------------------------------------------------

def _transcribe_audio_sync(ai_service: AIServiceFacade, audio_path: str) -> Any:
    client = ai_service.elevenlabs_client
    settings = ai_service.settings

    if not hasattr(client, "speech_to_text"):
        raise RuntimeError("ElevenLabs client does not expose speech_to_text.")

    with Path(audio_path).open("rb") as audio_file:
        return client.speech_to_text.convert(
            file=audio_file,
            model_id=settings.elevenlabs_stt_model,
            timestamps_granularity="word",
        )


@asynccontextmanager
async def _materialized_audio_path(audio_source: str | dict[str, Any]):
    if isinstance(audio_source, str):
        yield audio_source
        return

    if not isinstance(audio_source, dict):
        raise RuntimeError("Audio upload metadata was missing.")

    file_id = audio_source.get("file_id")
    if not file_id:
        raise RuntimeError("Audio file identifier was missing.")

    async with get_media_store().materialize_temp_file(
        file_id=str(file_id),
        suffix=_upload_suffix(audio_source),
    ) as audio_path:
        yield audio_path


def _upload_suffix(upload: dict[str, Any]) -> str:
    filename = str(upload.get("filename") or upload.get("original_filename") or "")
    return Path(filename).suffix or ".webm"


def _extract_transcript(response: Any) -> str:
    data = _to_mapping(response)
    return str(data.get("text") or data.get("transcript") or "").strip()


def _extract_words(response: Any) -> list[dict[str, Any]]:
    data = _to_mapping(response)
    words = data.get("words") or data.get("word_timestamps") or []
    normalized: list[dict[str, Any]] = []

    for word in words:
        item = _to_mapping(word)
        text = item.get("word") or item.get("text")
        if not text:
            continue
        normalized.append(
            {
                "word": str(text),
                "start": float(item.get("start") or item.get("start_time") or 0),
                "end": float(item.get("end") or item.get("end_time") or 0),
            }
        )

    return normalized


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
