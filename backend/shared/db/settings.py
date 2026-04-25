"""Database configuration loaded from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """MongoDB settings for durable practice-session history."""

    mongodb_enabled: bool = False
    mongodb_uri: str = ""
    mongodb_db_name: str = "voxcoach"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_database_settings() -> DatabaseSettings:
    """Load database settings once per process."""

    return DatabaseSettings()
