"""Shared persistence entrypoints."""

from backend.shared.db.client import (
    close_database,
    get_media_store,
    get_session_repository,
    init_database,
    reset_media_store,
    reset_session_repository,
)
from backend.shared.db.media_store import InMemoryMediaStore, MediaStore, MongoGridFSMediaStore
from backend.shared.db.repository import (
    InMemorySessionRepository,
    MongoSessionRepository,
    SessionRepository,
)
from backend.shared.db.schemas import PracticeSessionDocument, SessionChunkDocument, TrendSnapshotDocument
from backend.shared.db.settings import DatabaseSettings, get_database_settings

__all__ = [
    "DatabaseSettings",
    "InMemoryMediaStore",
    "InMemorySessionRepository",
    "MediaStore",
    "MongoGridFSMediaStore",
    "MongoSessionRepository",
    "PracticeSessionDocument",
    "SessionRepository",
    "SessionChunkDocument",
    "TrendSnapshotDocument",
    "close_database",
    "get_database_settings",
    "get_media_store",
    "get_session_repository",
    "init_database",
    "reset_media_store",
    "reset_session_repository",
]
