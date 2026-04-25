"""ElevenLabs client constructors for TTS/STT support."""

from typing import Any

from elevenlabs.client import ElevenLabs

from backend.shared.ai.settings import AISettings


def create_elevenlabs_client(settings: AISettings) -> ElevenLabs:
    """Build a shared ElevenLabs SDK client."""
    return ElevenLabs(api_key=settings.elevenlabs_api_key)


def get_default_voice_id(settings: AISettings) -> str:
    """Expose configured default voice for TTS calls."""
    return settings.elevenlabs_default_voice_id


def get_stt_model_name(settings: AISettings) -> str:
    """Expose configured speech-to-text model name."""
    return settings.elevenlabs_stt_model


def list_voice_options(client: ElevenLabs, settings: AISettings) -> list[dict[str, Any]]:
    """Return normalized voice metadata for settings screens.

    If the upstream API is unavailable, fall back to the configured default voice
    so the UI still has a stable option to render.
    """

    try:
        response = client.voices.get_all(show_legacy=True)
        payload = response.model_dump() if hasattr(response, "model_dump") else {}
        voices = payload.get("voices") if isinstance(payload, dict) else None
    except Exception:
        voices = None

    normalized: list[dict[str, Any]] = []
    for voice in voices or []:
        if not isinstance(voice, dict):
            continue
        voice_id = str(voice.get("voice_id") or "").strip()
        if not voice_id:
            continue
        normalized.append(
            {
                "voice_id": voice_id,
                "name": str(voice.get("name") or "Unnamed voice").strip() or "Unnamed voice",
                "category": str(voice.get("category") or "").strip() or None,
                "description": str(voice.get("description") or "").strip() or None,
                "preview_url": str(voice.get("preview_url") or "").strip() or None,
                "is_default": voice_id == settings.elevenlabs_default_voice_id,
            }
        )

    if not normalized:
        return [
            {
                "voice_id": settings.elevenlabs_default_voice_id,
                "name": "Default voice",
                "category": "configured",
                "description": "Fallback voice from the current ElevenLabs configuration.",
                "preview_url": None,
                "is_default": True,
            }
        ]

    normalized.sort(
        key=lambda voice: (
            0 if voice["is_default"] else 1,
            str(voice["name"]).lower(),
        )
    )
    return normalized
