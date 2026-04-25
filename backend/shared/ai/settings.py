"""Typed environment configuration for AI integrations."""

from functools import lru_cache

from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class AISettings(BaseSettings):
    """Centralized environment settings used by AI providers."""

    app_env: str = "development"
    log_level: str = "INFO"

    openrouter_api_key: str
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model_gemma: str = "openrouter/gemma-placeholder"
    openrouter_model_haiku: str = "openrouter/haiku-placeholder"

    elevenlabs_api_key: str
    elevenlabs_default_voice_id: str = "voice-placeholder"
    elevenlabs_stt_model: str = "scribe_v1"

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
