"""Database client lifecycle and repository access."""

from typing import Any

import certifi

from backend.shared.db.media_store import InMemoryMediaStore, MediaStore, MongoGridFSMediaStore
from backend.shared.db.repository import InMemorySessionRepository, MongoSessionRepository, SessionRepository
from backend.shared.db.settings import DatabaseSettings, get_database_settings

_repository: SessionRepository = InMemorySessionRepository()
_media_store: MediaStore = InMemoryMediaStore()


async def init_database(settings: DatabaseSettings | None = None) -> SessionRepository:
    """Initialize the process-wide session repository."""

    global _repository, _media_store
    settings = settings or get_database_settings()
    if not settings.mongodb_enabled:
        _repository = InMemorySessionRepository()
        _media_store = InMemoryMediaStore()
        return _repository

    if not settings.mongodb_uri:
        raise RuntimeError("MONGODB_URI is required when MONGODB_ENABLED=true.")

    try:
        from motor.motor_asyncio import AsyncIOMotorClient
    except ImportError as error:
        raise RuntimeError("Install the 'motor' package to enable MongoDB persistence.") from error

    client: Any = AsyncIOMotorClient(
        settings.mongodb_uri,
        tlsCAFile=certifi.where(),
    )
    repository = MongoSessionRepository(client, settings.mongodb_db_name)
    media_store = MongoGridFSMediaStore(client[settings.mongodb_db_name])
    await repository.ensure_indexes()
    _repository = repository
    _media_store = media_store
    return _repository


def get_session_repository() -> SessionRepository:
    """Return the process-wide session repository."""

    return _repository


def get_media_store() -> MediaStore:
    """Return the process-wide media store."""

    return _media_store


def reset_session_repository(repository: SessionRepository | None = None) -> SessionRepository:
    """Replace the repository, primarily for tests."""

    global _repository, _media_store
    _repository = repository or InMemorySessionRepository()
    _media_store = InMemoryMediaStore()
    return _repository


def reset_media_store(media_store: MediaStore | None = None) -> MediaStore:
    """Replace the media store, primarily for tests."""

    global _media_store
    _media_store = media_store or InMemoryMediaStore()
    return _media_store


async def close_database() -> None:
    """Close database resources held by the process-wide repository."""

    await _media_store.close()
    await _repository.close()
