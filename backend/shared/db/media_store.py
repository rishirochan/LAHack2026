"""Blob storage helpers for practice-session media."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, AsyncIterator, Protocol
from uuid import uuid4


MEDIA_BUCKET_NAME = "practice_media"
DEFAULT_CHUNK_SIZE = 1024 * 256


class MediaStore(Protocol):
    """Storage operations used by API upload/download flows."""

    async def save_media(
        self,
        *,
        data: bytes,
        storage_key: str,
        original_filename: str,
        mime_type: str,
    ) -> dict[str, Any]:
        ...

    async def iter_media(self, *, file_id: str, chunk_size: int = DEFAULT_CHUNK_SIZE) -> AsyncIterator[bytes]:
        ...

    @asynccontextmanager
    async def materialize_temp_file(
        self,
        *,
        file_id: str,
        suffix: str,
    ) -> AsyncIterator[str]:
        ...

    async def close(self) -> None:
        ...


class InMemoryMediaStore:
    """Process-local media store used in tests or when MongoDB is disabled."""

    def __init__(self) -> None:
        self._files: dict[str, dict[str, Any]] = {}

    async def save_media(
        self,
        *,
        data: bytes,
        storage_key: str,
        original_filename: str,
        mime_type: str,
    ) -> dict[str, Any]:
        file_id = uuid4().hex
        uploaded_at = datetime.now(UTC).isoformat()
        document = {
            "file_id": file_id,
            "storage_key": storage_key,
            "filename": Path(storage_key).name,
            "original_filename": original_filename,
            "mime_type": mime_type,
            "size_bytes": len(data),
            "uploaded_at": uploaded_at,
            "data": data,
        }
        self._files[file_id] = document
        return _public_media_document(document)

    async def iter_media(self, *, file_id: str, chunk_size: int = DEFAULT_CHUNK_SIZE) -> AsyncIterator[bytes]:
        document = self._require_file(file_id)
        data = document["data"]
        for index in range(0, len(data), chunk_size):
            yield data[index : index + chunk_size]

    @asynccontextmanager
    async def materialize_temp_file(
        self,
        *,
        file_id: str,
        suffix: str,
    ) -> AsyncIterator[str]:
        document = self._require_file(file_id)
        with NamedTemporaryFile(delete=False, suffix=suffix) as output:
            output.write(document["data"])
            temp_path = output.name
        try:
            yield temp_path
        finally:
            Path(temp_path).unlink(missing_ok=True)

    async def close(self) -> None:
        return None

    def _require_file(self, file_id: str) -> dict[str, Any]:
        try:
            return self._files[file_id]
        except KeyError as error:
            raise FileNotFoundError(f"Media file {file_id!r} was not found.") from error


class MongoGridFSMediaStore:
    """GridFS-backed media store built on the shared Motor database."""

    def __init__(self, database: Any) -> None:
        try:
            from motor.motor_asyncio import AsyncIOMotorGridFSBucket
        except ImportError as error:
            raise RuntimeError("Install the 'motor' package to enable MongoDB GridFS media.") from error

        self._bucket = AsyncIOMotorGridFSBucket(database, bucket_name=MEDIA_BUCKET_NAME)

    async def save_media(
        self,
        *,
        data: bytes,
        storage_key: str,
        original_filename: str,
        mime_type: str,
    ) -> dict[str, Any]:
        uploaded_at = datetime.now(UTC).isoformat()
        metadata = {
            "storage_key": storage_key,
            "original_filename": original_filename,
            "mime_type": mime_type,
            "size_bytes": len(data),
            "uploaded_at": uploaded_at,
        }
        file_id = await self._bucket.upload_from_stream(
            storage_key,
            data,
            metadata=metadata,
        )
        return {
            "file_id": str(file_id),
            "storage_key": storage_key,
            "filename": Path(storage_key).name,
            "original_filename": original_filename,
            "mime_type": mime_type,
            "size_bytes": len(data),
            "uploaded_at": uploaded_at,
        }

    async def iter_media(self, *, file_id: str, chunk_size: int = DEFAULT_CHUNK_SIZE) -> AsyncIterator[bytes]:
        stream = await self._open_download_stream(file_id)
        while True:
            chunk = await stream.readchunk()
            if not chunk:
                break
            yield chunk

    @asynccontextmanager
    async def materialize_temp_file(
        self,
        *,
        file_id: str,
        suffix: str,
    ) -> AsyncIterator[str]:
        with NamedTemporaryFile(delete=False, suffix=suffix) as output:
            async for chunk in self.iter_media(file_id=file_id):
                output.write(chunk)
            temp_path = output.name
        try:
            yield temp_path
        finally:
            Path(temp_path).unlink(missing_ok=True)

    async def close(self) -> None:
        return None

    async def _open_download_stream(self, file_id: str) -> Any:
        try:
            from bson import ObjectId
            from gridfs.errors import NoFile
        except ImportError as error:
            raise RuntimeError("GridFS dependencies are unavailable.") from error

        try:
            return await self._bucket.open_download_stream(ObjectId(file_id))
        except NoFile as error:
            raise FileNotFoundError(f"Media file {file_id!r} was not found.") from error

def _public_media_document(document: dict[str, Any]) -> dict[str, Any]:
    return {
        "file_id": document["file_id"],
        "storage_key": document["storage_key"],
        "filename": document["filename"],
        "original_filename": document["original_filename"],
        "mime_type": document["mime_type"],
        "size_bytes": document["size_bytes"],
        "uploaded_at": document["uploaded_at"],
    }
