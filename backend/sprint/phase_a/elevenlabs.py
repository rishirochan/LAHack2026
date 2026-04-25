"""ElevenLabs helpers for TTS streaming and speech transcription."""

import asyncio
import base64
from pathlib import Path
from typing import Any, AsyncIterator

from backend.shared.ai.service import AIServiceFacade


async def stream_tts_chunks(
    *,
    ai_service: AIServiceFacade,
    text: str,
) -> AsyncIterator[str]:
    """Yield base64-encoded audio chunks for websocket transport."""

    chunks = await asyncio.to_thread(_collect_tts_chunks, ai_service, text)
    for chunk in chunks:
        yield base64.b64encode(chunk).decode("ascii")


async def transcribe_audio(
    *,
    ai_service: AIServiceFacade,
    audio_path: str,
) -> tuple[str, list[dict[str, Any]]]:
    """Transcribe audio with word-level timestamps."""

    response = await asyncio.to_thread(_transcribe_audio_sync, ai_service, audio_path)
    return _extract_transcript(response), _extract_words(response)


def _collect_tts_chunks(ai_service: AIServiceFacade, text: str) -> list[bytes]:
    client = ai_service.elevenlabs_client
    settings = ai_service.settings

    if hasattr(client, "text_to_speech") and hasattr(client.text_to_speech, "stream"):
        stream = client.text_to_speech.stream(
            voice_id=settings.elevenlabs_default_voice_id,
            model_id=settings.elevenlabs_tts_model,
            text=text,
        )
    elif hasattr(client, "generate"):
        stream = client.generate(
            text=text,
            voice=settings.elevenlabs_default_voice_id,
            model=settings.elevenlabs_tts_model,
            stream=True,
        )
    else:
        raise RuntimeError("ElevenLabs client does not expose a TTS streaming method.")

    return [chunk for chunk in stream if isinstance(chunk, bytes)]


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

