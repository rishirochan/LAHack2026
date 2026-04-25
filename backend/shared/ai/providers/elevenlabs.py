"""ElevenLabs client constructors for TTS/STT support."""

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
