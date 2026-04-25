"""Repositories for durable practice-session history."""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any, Protocol


DEFAULT_USER_ID = "demo-user"
PRACTICE_SESSIONS_COLLECTION = "practice_sessions"
SESSION_CHUNKS_COLLECTION = "session_chunks"


class SessionRepository(Protocol):
    """Persistence operations used by sprint session managers and APIs."""

    async def create_phase_a_session(
        self,
        *,
        session_id: str,
        initial_state: dict[str, Any],
        user_id: str = DEFAULT_USER_ID,
    ) -> None:
        ...

    async def update_phase_a_session(
        self,
        *,
        session_id: str,
        rounds: list[dict[str, Any]] | None = None,
        summary: dict[str, Any] | None = None,
        media_refs: list[dict[str, Any]] | None = None,
        raw_state: dict[str, Any] | None = None,
        status: str | None = None,
    ) -> None:
        ...

    async def create_phase_b_session(
        self,
        *,
        session_id: str,
        state: dict[str, Any],
        user_id: str = DEFAULT_USER_ID,
    ) -> None:
        ...

    async def update_phase_b_state(
        self,
        *,
        session_id: str,
        state: dict[str, Any],
    ) -> None:
        ...

    async def list_recent_sessions(
        self,
        *,
        user_id: str = DEFAULT_USER_ID,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        ...

    async def get_session(self, session_id: str) -> dict[str, Any] | None:
        ...

    async def list_session_chunks(self, session_id: str) -> list[dict[str, Any]]:
        ...

    async def get_user_trends(self, *, user_id: str = DEFAULT_USER_ID) -> dict[str, Any]:
        ...

    async def close(self) -> None:
        ...


class InMemorySessionRepository:
    """Process-local repository used when MongoDB is disabled or in tests."""

    def __init__(self) -> None:
        self._documents: dict[str, dict[str, Any]] = {}
        self._chunks: dict[tuple[str, int, int], dict[str, Any]] = {}

    async def create_phase_a_session(
        self,
        *,
        session_id: str,
        initial_state: dict[str, Any],
        user_id: str = DEFAULT_USER_ID,
    ) -> None:
        now = _now()
        self._documents[session_id] = _without_none(
            {
                "session_id": session_id,
                "user_id": user_id,
                "mode": "phase_a",
                "mode_label": "Emotion Drills",
                "status": "active",
                "created_at": now,
                "updated_at": now,
                "setup": {
                    "target_emotion": initial_state.get("target_emotion"),
                },
                "rounds": [],
                "summary": None,
                "media_refs": [],
                "raw_state": _json_safe(_sanitize_phase_a_state(initial_state)),
            }
        )

    async def update_phase_a_session(
        self,
        *,
        session_id: str,
        rounds: list[dict[str, Any]] | None = None,
        summary: dict[str, Any] | None = None,
        media_refs: list[dict[str, Any]] | None = None,
        raw_state: dict[str, Any] | None = None,
        status: str | None = None,
    ) -> None:
        document = self._documents.setdefault(
            session_id,
            {
                "session_id": session_id,
                "user_id": DEFAULT_USER_ID,
                "mode": "phase_a",
                "mode_label": "Emotion Drills",
                "created_at": _now(),
            },
        )
        _apply_session_update(
            document,
            rounds=rounds,
            summary=summary,
            media_refs=media_refs,
            raw_state=raw_state,
            status=status,
        )

    async def create_phase_b_session(
        self,
        *,
        session_id: str,
        state: dict[str, Any],
        user_id: str = DEFAULT_USER_ID,
    ) -> None:
        now = _now()
        self._documents[session_id] = _without_none(
            {
                "session_id": session_id,
                "user_id": user_id,
                "mode": "phase_b",
                "mode_label": "Conversations",
                "status": state.get("status", "active"),
                "created_at": now,
                "updated_at": now,
                "completed_at": now if state.get("status") == "complete" else None,
                "setup": {
                    "scenario": state.get("scenario"),
                    "difficulty": state.get("difficulty"),
                    "max_turns": state.get("max_turns"),
                    "persona": state.get("persona"),
                },
                "summary": _phase_b_summary(state),
                "media_refs": _phase_b_media_refs(state),
                "raw_state": _json_safe(_sanitize_phase_b_state(state)),
            }
        )
        self._sync_phase_b_chunks(session_id=session_id, state=state, user_id=user_id)

    async def update_phase_b_state(
        self,
        *,
        session_id: str,
        state: dict[str, Any],
    ) -> None:
        document = self._documents.setdefault(
            session_id,
            {
                "session_id": session_id,
                "user_id": DEFAULT_USER_ID,
                "mode": "phase_b",
                "mode_label": "Conversations",
                "created_at": _now(),
            },
        )
        status = str(state.get("status", "active"))
        document.update(
            _without_none(
                {
                    "status": status,
                    "updated_at": _now(),
                    "completed_at": _now() if status == "complete" else document.get("completed_at"),
                    "setup": {
                        "scenario": state.get("scenario"),
                        "difficulty": state.get("difficulty"),
                        "max_turns": state.get("max_turns"),
                        "persona": state.get("persona"),
                    },
                    "summary": _phase_b_summary(state),
                    "media_refs": _phase_b_media_refs(state),
                    "raw_state": _json_safe(_sanitize_phase_b_state(state)),
                }
            )
        )
        self._sync_phase_b_chunks(
            session_id=session_id,
            state=state,
            user_id=str(document.get("user_id") or DEFAULT_USER_ID),
        )

    async def list_recent_sessions(
        self,
        *,
        user_id: str = DEFAULT_USER_ID,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        documents = [
            deepcopy(document)
            for document in self._documents.values()
            if document.get("user_id") == user_id
        ]
        documents.sort(key=lambda document: document.get("updated_at") or document.get("created_at"), reverse=True)
        return [_strip_mongo_id(document) for document in documents[:limit]]

    async def get_session(self, session_id: str) -> dict[str, Any] | None:
        document = self._documents.get(session_id)
        return _strip_mongo_id(deepcopy(document)) if document else None

    async def list_session_chunks(self, session_id: str) -> list[dict[str, Any]]:
        chunks = [
            deepcopy(chunk)
            for (chunk_session_id, _turn_index, _chunk_index), chunk in self._chunks.items()
            if chunk_session_id == session_id
        ]
        chunks.sort(key=lambda chunk: (chunk["turn_index"], chunk["chunk_index"]))
        return chunks

    async def get_user_trends(self, *, user_id: str = DEFAULT_USER_ID) -> dict[str, Any]:
        chunks = [chunk for chunk in self._chunks.values() if chunk.get("user_id") == user_id]
        sessions = {
            document["session_id"]
            for document in self._documents.values()
            if document.get("user_id") == user_id
        }
        return _build_trend_snapshot(
            user_id=user_id,
            session_count=len(sessions),
            chunks=chunks,
            sessions=list(self._documents.values()),
        )

    async def close(self) -> None:
        return None

    def clear(self) -> None:
        self._documents.clear()
        self._chunks.clear()

    def _sync_phase_b_chunks(
        self,
        *,
        session_id: str,
        state: dict[str, Any],
        user_id: str,
    ) -> None:
        for chunk_document in _phase_b_chunk_documents(session_id=session_id, state=state, user_id=user_id):
            key = (
                chunk_document["session_id"],
                int(chunk_document["turn_index"]),
                int(chunk_document["chunk_index"]),
            )
            existing = self._chunks.get(key, {})
            created_at = existing.get("created_at") or chunk_document["created_at"]
            self._chunks[key] = {**existing, **chunk_document, "created_at": created_at}


class MongoSessionRepository:
    """MongoDB-backed repository using Motor."""

    def __init__(self, client: Any, db_name: str) -> None:
        self._client = client
        self._database = client[db_name]
        self._collection = self._database[PRACTICE_SESSIONS_COLLECTION]
        self._chunks_collection = self._database[SESSION_CHUNKS_COLLECTION]

    async def ensure_indexes(self) -> None:
        await self._collection.create_index("session_id", unique=True)
        await self._collection.create_index([("user_id", 1), ("updated_at", -1)])
        await self._collection.create_index("mode")
        await self._chunks_collection.create_index(
            [("session_id", 1), ("turn_index", 1), ("chunk_index", 1)],
            unique=True,
        )
        await self._chunks_collection.create_index([("user_id", 1), ("updated_at", -1)])
        await self._chunks_collection.create_index([("user_id", 1), ("dominant_video_emotion", 1)])
        await self._chunks_collection.create_index([("user_id", 1), ("dominant_audio_emotion", 1)])

    async def create_phase_a_session(
        self,
        *,
        session_id: str,
        initial_state: dict[str, Any],
        user_id: str = DEFAULT_USER_ID,
    ) -> None:
        now = _now()
        await self._collection.update_one(
            {"session_id": session_id},
            {
                "$setOnInsert": {
                    "session_id": session_id,
                    "user_id": user_id,
                    "mode": "phase_a",
                    "mode_label": "Emotion Drills",
                    "created_at": now,
                },
                "$set": {
                    "status": "active",
                    "updated_at": now,
                    "setup": {
                        "target_emotion": initial_state.get("target_emotion"),
                    },
                    "rounds": [],
                    "summary": None,
                    "media_refs": [],
                    "raw_state": _json_safe(_sanitize_phase_a_state(initial_state)),
                },
            },
            upsert=True,
        )

    async def update_phase_a_session(
        self,
        *,
        session_id: str,
        rounds: list[dict[str, Any]] | None = None,
        summary: dict[str, Any] | None = None,
        media_refs: list[dict[str, Any]] | None = None,
        raw_state: dict[str, Any] | None = None,
        status: str | None = None,
    ) -> None:
        update = _session_update_doc(
            rounds=rounds,
            summary=summary,
            media_refs=media_refs,
            raw_state=raw_state,
            status=status,
        )
        await self._collection.update_one({"session_id": session_id}, update, upsert=True)

    async def create_phase_b_session(
        self,
        *,
        session_id: str,
        state: dict[str, Any],
        user_id: str = DEFAULT_USER_ID,
    ) -> None:
        now = _now()
        await self._collection.update_one(
            {"session_id": session_id},
            {
                "$setOnInsert": {
                    "session_id": session_id,
                    "user_id": user_id,
                    "mode": "phase_b",
                    "mode_label": "Conversations",
                    "created_at": now,
                },
                "$set": {
                    "status": state.get("status", "active"),
                    "updated_at": now,
                    "setup": {
                        "scenario": state.get("scenario"),
                        "difficulty": state.get("difficulty"),
                        "max_turns": state.get("max_turns"),
                        "persona": state.get("persona"),
                    },
                    "summary": _phase_b_summary(state),
                    "media_refs": _phase_b_media_refs(state),
                    "raw_state": _json_safe(_sanitize_phase_b_state(state)),
                },
            },
            upsert=True,
        )

    async def update_phase_b_state(
        self,
        *,
        session_id: str,
        state: dict[str, Any],
    ) -> None:
        owner_user_id = await self._resolve_phase_b_user_id(session_id)
        status = str(state.get("status", "active"))
        set_doc = _without_none(
            {
                "status": status,
                "updated_at": _now(),
                "completed_at": _now() if status == "complete" else None,
                "setup": {
                    "scenario": state.get("scenario"),
                    "difficulty": state.get("difficulty"),
                    "max_turns": state.get("max_turns"),
                    "persona": state.get("persona"),
                },
                "summary": _phase_b_summary(state),
                "media_refs": _phase_b_media_refs(state),
                "raw_state": _json_safe(_sanitize_phase_b_state(state)),
            }
        )
        await self._collection.update_one(
            {"session_id": session_id},
            {
                "$set": set_doc,
                "$setOnInsert": {
                    "created_at": _now(),
                    "user_id": owner_user_id,
                    "mode": "phase_b",
                    "mode_label": "Conversations",
                },
            },
            upsert=True,
        )
        await self._upsert_phase_b_chunks(
            session_id=session_id,
            state=state,
            user_id=owner_user_id,
        )

    async def list_recent_sessions(
        self,
        *,
        user_id: str = DEFAULT_USER_ID,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        cursor = (
            self._collection.find({"user_id": user_id})
            .sort("updated_at", -1)
            .limit(max(1, min(limit, 50)))
        )
        return [_strip_mongo_id(document) async for document in cursor]

    async def get_session(self, session_id: str) -> dict[str, Any] | None:
        document = await self._collection.find_one({"session_id": session_id})
        return _strip_mongo_id(document) if document else None

    async def list_session_chunks(self, session_id: str) -> list[dict[str, Any]]:
        cursor = self._chunks_collection.find({"session_id": session_id}).sort(
            [("turn_index", 1), ("chunk_index", 1)]
        )
        return [_strip_mongo_id(document) async for document in cursor]

    async def get_user_trends(self, *, user_id: str = DEFAULT_USER_ID) -> dict[str, Any]:
        chunks = [
            _strip_mongo_id(document)
            async for document in self._chunks_collection.find({"user_id": user_id})
        ]
        session_count = await self._collection.count_documents({"user_id": user_id})
        sessions = [
            _strip_mongo_id(document)
            async for document in self._collection.find({"user_id": user_id})
        ]
        return _build_trend_snapshot(
            user_id=user_id,
            session_count=session_count,
            chunks=chunks,
            sessions=sessions,
        )

    async def close(self) -> None:
        self._client.close()

    async def _upsert_phase_b_chunks(
        self,
        *,
        session_id: str,
        state: dict[str, Any],
        user_id: str,
    ) -> None:
        for chunk_document in _phase_b_chunk_documents(session_id=session_id, state=state, user_id=user_id):
            update_document = {key: value for key, value in chunk_document.items() if key != "created_at"}
            await self._chunks_collection.update_one(
                {
                    "session_id": chunk_document["session_id"],
                    "turn_index": chunk_document["turn_index"],
                    "chunk_index": chunk_document["chunk_index"],
                },
                {
                    "$set": update_document,
                    "$setOnInsert": {"created_at": chunk_document["created_at"]},
                },
                upsert=True,
            )

    async def _resolve_phase_b_user_id(self, session_id: str) -> str:
        document = await self._collection.find_one({"session_id": session_id}, {"user_id": 1})
        if not document:
            return DEFAULT_USER_ID
        return str(document.get("user_id") or DEFAULT_USER_ID)


def _session_update_doc(
    *,
    rounds: list[dict[str, Any]] | None,
    summary: dict[str, Any] | None,
    media_refs: list[dict[str, Any]] | None,
    raw_state: dict[str, Any] | None,
    status: str | None,
) -> dict[str, Any]:
    set_doc = _without_none(
        {
            "rounds": _json_safe(rounds) if rounds is not None else None,
            "summary": _json_safe(summary) if summary is not None else None,
            "media_refs": _json_safe(media_refs) if media_refs is not None else None,
            "raw_state": _json_safe(_sanitize_phase_a_state(raw_state)) if raw_state is not None else None,
            "status": status,
            "completed_at": _now() if status == "complete" else None,
            "updated_at": _now(),
        }
    )
    return {
        "$set": set_doc,
        "$setOnInsert": {
            "created_at": _now(),
            "user_id": DEFAULT_USER_ID,
            "mode": "phase_a",
            "mode_label": "Emotion Drills",
        },
    }


def _apply_session_update(
    document: dict[str, Any],
    *,
    rounds: list[dict[str, Any]] | None,
    summary: dict[str, Any] | None,
    media_refs: list[dict[str, Any]] | None,
    raw_state: dict[str, Any] | None,
    status: str | None,
) -> None:
    document["updated_at"] = _now()
    if rounds is not None:
        document["rounds"] = _json_safe(rounds)
    if summary is not None:
        document["summary"] = _json_safe(summary)
    if media_refs is not None:
        document["media_refs"] = _json_safe(media_refs)
    if raw_state is not None:
        document["raw_state"] = _json_safe(_sanitize_phase_a_state(raw_state))
    if status is not None:
        document["status"] = status
        if status == "complete":
            document["completed_at"] = _now()


def _phase_b_summary(state: dict[str, Any]) -> dict[str, Any]:
    turns = state.get("turns") or []
    merged_summaries = [
        turn.get("merged_summary") or {}
        for turn in turns
        if isinstance(turn, dict)
    ]
    eye_contacts = [
        summary.get("overall", {}).get("avg_eye_contact_pct")
        for summary in merged_summaries
        if isinstance(summary.get("overall"), dict)
        and summary.get("overall", {}).get("avg_eye_contact_pct") is not None
    ]
    dominant_video = _most_common(
        [
            summary.get("overall", {}).get("dominant_video_emotion")
            for summary in merged_summaries
            if isinstance(summary.get("overall"), dict)
        ]
    )
    dominant_audio = _most_common(
        [
            summary.get("overall", {}).get("dominant_audio_emotion")
            for summary in merged_summaries
            if isinstance(summary.get("overall"), dict)
        ]
    )
    return {
        "session_id": state.get("session_id"),
        "scenario": state.get("scenario"),
        "difficulty": state.get("difficulty"),
        "status": state.get("status"),
        "total_turns": len(turns),
        "avg_eye_contact_pct": round(sum(eye_contacts) / len(eye_contacts), 1) if eye_contacts else None,
        "dominant_video_emotion": dominant_video,
        "dominant_audio_emotion": dominant_audio,
        "chunks_failed": sum(
            int((summary.get("overall") or {}).get("chunks_failed") or 0)
            for summary in merged_summaries
            if isinstance(summary, dict)
        ),
        "chunks_timed_out": sum(
            int((summary.get("overall") or {}).get("chunks_timed_out") or 0)
            for summary in merged_summaries
            if isinstance(summary, dict)
        ),
        "turns": [
            {
                "turn_index": turn.get("turn_index"),
                "prompt": turn.get("prompt_text"),
                "critique": turn.get("critique"),
            }
            for turn in turns
        ],
    }


def _phase_b_chunk_documents(
    *,
    session_id: str,
    state: dict[str, Any],
    user_id: str,
) -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []
    turns = [turn for turn in state.get("turns", []) if isinstance(turn, dict)]
    current_turn = state.get("current_turn")
    if isinstance(current_turn, dict):
        turns.append(current_turn)

    for turn in turns:
        turn_index = int(turn.get("turn_index") or 0)
        merged_by_window = _merged_chunks_by_window(turn.get("merged_summary"))
        for chunk in turn.get("chunks") or []:
            if not isinstance(chunk, dict):
                continue
            start_ms = int(chunk.get("start_ms") or 0)
            end_ms = int(chunk.get("end_ms") or 0)
            merged_chunk = merged_by_window.get((start_ms, end_ms), {})
            document = _without_none(
                {
                    "session_id": session_id,
                    "user_id": user_id,
                    "mode": "phase_b",
                    "scenario": state.get("scenario"),
                    "turn_index": turn_index,
                    "chunk_index": int(chunk.get("chunk_index") or 0),
                    "start_ms": start_ms,
                    "end_ms": end_ms,
                    "status": chunk.get("status") or "pending",
                    "mediapipe_metrics": _json_safe(chunk.get("mediapipe_metrics") or {}),
                    "video_emotions": _json_safe(chunk.get("video_emotions") or []),
                    "audio_emotions": _json_safe(chunk.get("audio_emotions") or []),
                    "video_upload": _phase_b_chunk_upload_ref(
                        session_id=session_id,
                        turn_index=turn_index,
                        chunk_index=int(chunk.get("chunk_index") or 0),
                        media_kind="video",
                        upload=chunk.get("video_upload"),
                    ),
                    "audio_upload": _phase_b_chunk_upload_ref(
                        session_id=session_id,
                        turn_index=turn_index,
                        chunk_index=int(chunk.get("chunk_index") or 0),
                        media_kind="audio",
                        upload=chunk.get("audio_upload"),
                    ),
                    "transcript_segment": merged_chunk.get("transcript_segment") or "",
                    "merged_summary": _json_safe(merged_chunk) if merged_chunk else None,
                    "dominant_video_emotion": merged_chunk.get("dominant_video_emotion"),
                    "video_confidence": merged_chunk.get("video_confidence"),
                    "dominant_audio_emotion": merged_chunk.get("dominant_audio_emotion"),
                    "audio_confidence": merged_chunk.get("audio_confidence"),
                    "eye_contact_pct": merged_chunk.get("eye_contact_pct"),
                    "created_at": _now(),
                    "updated_at": _now(),
                }
            )
            documents.append(document)

    return documents


def _phase_b_media_refs(state: dict[str, Any]) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    session_id = str(state.get("session_id") or "")
    turns = [turn for turn in state.get("turns", []) if isinstance(turn, dict)]
    current_turn = state.get("current_turn")
    if isinstance(current_turn, dict):
        turns.append(current_turn)

    for turn in turns:
        turn_index = int(turn.get("turn_index") or 0)
        transcript_audio_upload = turn.get("transcript_audio_upload")
        if isinstance(transcript_audio_upload, dict):
            refs.append(
                {
                    "turn_index": turn_index,
                    "kind": "turn_transcript_audio",
                    "download_url": (
                        f"/api/phase-b/sessions/{state.get('session_id') or session_id}"
                        f"/turns/{turn_index}/transcript-audio"
                    ),
                    "upload": _public_upload_ref(transcript_audio_upload),
                }
            )

        for chunk in turn.get("chunks") or []:
            if not isinstance(chunk, dict):
                continue
            chunk_index = int(chunk.get("chunk_index") or 0)
            for kind in ("video_upload", "audio_upload"):
                upload = chunk.get(kind)
                if not isinstance(upload, dict):
                    continue
                refs.append(
                    {
                        "turn_index": turn_index,
                        "chunk_index": chunk_index,
                        "kind": kind,
                        "download_url": (
                            f"/api/phase-b/sessions/{state.get('session_id') or session_id}"
                            f"/turns/{turn_index}/chunks/{chunk_index}/{_phase_b_kind_to_media_name(kind)}"
                        ),
                        "upload": _public_upload_ref(upload),
                    }
                )

    return refs


def _phase_b_chunk_upload_ref(
    *,
    session_id: str,
    turn_index: int,
    chunk_index: int,
    media_kind: str,
    upload: Any,
) -> dict[str, Any] | None:
    if not isinstance(upload, dict):
        return None
    ref = _public_upload_ref(upload)
    ref["download_url"] = (
        f"/api/phase-b/sessions/{session_id}/turns/{turn_index}/chunks/{chunk_index}/{media_kind}"
    )
    return ref


def _phase_b_kind_to_media_name(kind: str) -> str:
    return "video" if kind == "video_upload" else "audio"


def _public_upload_ref(upload: dict[str, Any]) -> dict[str, Any]:
    return {
        "file_id": upload.get("file_id"),
        "storage_key": upload.get("storage_key"),
        "filename": upload.get("filename"),
        "original_filename": upload.get("original_filename"),
        "mime_type": upload.get("mime_type"),
        "size_bytes": upload.get("size_bytes"),
        "uploaded_at": upload.get("uploaded_at"),
    }


def _merged_chunks_by_window(merged_summary: Any) -> dict[tuple[int, int], dict[str, Any]]:
    if not isinstance(merged_summary, dict):
        return {}
    chunks = merged_summary.get("chunks")
    if not isinstance(chunks, list):
        return {}
    result: dict[tuple[int, int], dict[str, Any]] = {}
    for chunk in chunks:
        if not isinstance(chunk, dict):
            continue
        result[(int(chunk.get("t_start") or 0), int(chunk.get("t_end") or 0))] = chunk
    return result


def _build_trend_snapshot(
    *,
    user_id: str,
    session_count: int,
    chunks: list[dict[str, Any]],
    sessions: list[dict[str, Any]],
) -> dict[str, Any]:
    eye_contacts = [
        float(chunk["eye_contact_pct"])
        for chunk in chunks
        if chunk.get("eye_contact_pct") is not None
    ]
    video_counter = Counter(
        str(chunk.get("dominant_video_emotion"))
        for chunk in chunks
        if chunk.get("dominant_video_emotion")
    )
    audio_counter = Counter(
        str(chunk.get("dominant_audio_emotion"))
        for chunk in chunks
        if chunk.get("dominant_audio_emotion")
    )
    return {
        "user_id": user_id,
        "session_count": session_count,
        "chunk_count": len(chunks),
        "average_eye_contact_pct": round(sum(eye_contacts) / len(eye_contacts), 1) if eye_contacts else None,
        "dominant_video_emotions": dict(video_counter),
        "dominant_audio_emotions": dict(audio_counter),
        "chunks_failed": sum(1 for chunk in chunks if chunk.get("status") == "failed"),
        "chunks_timed_out": sum(1 for chunk in chunks if chunk.get("status") == "timed_out"),
        "score_history": _score_history(sessions),
    }


def _score_history(sessions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    history: list[dict[str, Any]] = []
    for session in sessions:
        summary = session.get("summary") if isinstance(session.get("summary"), dict) else {}
        scores = summary.get("match_scores") if isinstance(summary, dict) else None
        average_score = None
        if isinstance(scores, list) and scores:
            average_score = round(float(sum(scores) / len(scores)) * 100)
        elif summary.get("avg_eye_contact_pct") is not None:
            average_score = summary.get("avg_eye_contact_pct")
        if average_score is None:
            continue
        history.append(
            {
                "session_id": session.get("session_id"),
                "mode": session.get("mode"),
                "score": average_score,
                "completed_at": session.get("completed_at"),
                "updated_at": session.get("updated_at"),
            }
        )
    history.sort(key=lambda item: item.get("completed_at") or item.get("updated_at") or "")
    return history


def _most_common(values: list[Any]) -> str | None:
    filtered = [str(value) for value in values if value]
    if not filtered:
        return None
    return Counter(filtered).most_common(1)[0][0]


def _sanitize_phase_a_state(state: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(state, dict):
        return state
    sanitized = _scrub_media_paths(state)
    sanitized["video_path"] = None
    sanitized["audio_path"] = None
    return sanitized


def _sanitize_phase_b_state(state: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(state, dict):
        return state
    return _scrub_media_paths(state)


def _scrub_media_paths(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): _scrub_media_paths(item)
            for key, item in value.items()
            if key != "path"
        }
    if isinstance(value, list):
        return [_scrub_media_paths(item) for item in value]
    if isinstance(value, tuple):
        return [_scrub_media_paths(item) for item in value]
    return value


def _json_safe(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return _json_safe(value.model_dump())
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, datetime):
        return value
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _strip_mongo_id(document: dict[str, Any]) -> dict[str, Any]:
    document.pop("_id", None)
    return document


def _without_none(document: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in document.items() if value is not None}


def _now() -> datetime:
    return datetime.now(UTC)
