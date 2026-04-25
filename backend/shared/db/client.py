"""Database client lifecycle and repository access."""

from typing import Any

from backend.shared.db.repository import InMemorySessionRepository, MongoSessionRepository, SessionRepository
from backend.shared.db.settings import DatabaseSettings, get_database_settings

_repository: SessionRepository = InMemorySessionRepository()


async def init_database(settings: DatabaseSettings | None = None) -> SessionRepository:
    """Initialize the process-wide session repository."""

    global _repository
    settings = settings or get_database_settings()
    if not settings.mongodb_enabled:
        _repository = InMemorySessionRepository()
        return _repository

    if not settings.mongodb_uri:
        raise RuntimeError("MONGODB_URI is required when MONGODB_ENABLED=true.")

    try:
        from motor.motor_asyncio import AsyncIOMotorClient
    except ImportError as error:
        raise RuntimeError("Install the 'motor' package to enable MongoDB persistence.") from error

    client: Any = AsyncIOMotorClient(settings.mongodb_uri)
    repository = MongoSessionRepository(client, settings.mongodb_db_name)
    await repository.ensure_indexes()
    _repository = repository
    return _repository


def get_session_repository() -> SessionRepository:
    """Return the process-wide session repository."""

    return _repository


def reset_session_repository(repository: SessionRepository | None = None) -> SessionRepository:
    """Replace the repository, primarily for tests."""

    global _repository
    _repository = repository or InMemorySessionRepository()
    return _repository


async def close_database() -> None:
    """Close database resources held by the process-wide repository."""

    await _repository.close()
