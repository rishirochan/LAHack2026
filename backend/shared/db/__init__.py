"""Shared persistence entrypoints."""

from backend.shared.db.client import (
    close_database,
    get_session_repository,
    init_database,
    reset_session_repository,
)
from backend.shared.db.repository import (
    InMemorySessionRepository,
    MongoSessionRepository,
    SessionRepository,
)
from backend.shared.db.schemas import PracticeSessionDocument, SessionChunkDocument, TrendSnapshotDocument
from backend.shared.db.settings import DatabaseSettings, get_database_settings

__all__ = [
    "DatabaseSettings",
    "InMemorySessionRepository",
    "MongoSessionRepository",
    "PracticeSessionDocument",
    "SessionRepository",
    "SessionChunkDocument",
    "TrendSnapshotDocument",
    "close_database",
    "get_database_settings",
    "get_session_repository",
    "init_database",
    "reset_session_repository",
]
