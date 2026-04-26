"""Typed environment configuration for AI integrations."""

from functools import lru_cache

from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class AISettings(BaseSettings):
    """Centralized environment settings used by AI providers."""

    app_env: str = "development"
    log_level: str = "INFO"

    google_api_key: str
    google_gemma_model: str = "gemma-4-31b-it"

    elevenlabs_api_key: str
    elevenlabs_default_voice_id: str = "voice-placeholder"
    elevenlabs_stt_model: str = "scribe_v1"
    elevenlabs_tts_model: str = "eleven_multilingual_v2"

    imentiv_api_key: str
    imentiv_base_url: str = "https://api.imentiv.ai/"
    imentiv_user_consent_version: str = "2.0.0"
    imentiv_mock: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> AISettings:
    """Load settings once and reuse them across the backend."""
    return AISettings()


def validate_settings() -> AISettings:
    """Provide a thin wrapper for startup validation."""
    try:
        return get_settings()
    except ValidationError as error:
        raise RuntimeError("Missing or invalid AI environment configuration.") from error
