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

    async def create_phase_c_session(
        self,
        *,
        session_id: str,
        state: dict[str, Any],
        user_id: str = DEFAULT_USER_ID,
    ) -> None:
        ...

    async def update_phase_c_state(
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

    async def get_profile_summary(self, *, user_id: str | None = DEFAULT_USER_ID) -> dict[str, Any]:
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
                    "scenario_preference": state.get("scenario_preference"),
                    "voice_id": state.get("voice_id"),
                    "max_turns": state.get("max_turns"),
                    "minimum_turns": state.get("minimum_turns"),
                    "peer_profile": state.get("peer_profile"),
                    "starter_topic": state.get("starter_topic"),
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
                        "scenario_preference": state.get("scenario_preference"),
                        "voice_id": state.get("voice_id"),
                        "max_turns": state.get("max_turns"),
                        "minimum_turns": state.get("minimum_turns"),
                        "peer_profile": state.get("peer_profile"),
                        "starter_topic": state.get("starter_topic"),
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

    async def create_phase_c_session(
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
                "mode": "phase_c",
                "mode_label": "Free Speaking",
                "status": state.get("status", "active"),
                "created_at": now,
                "updated_at": now,
                "completed_at": now if state.get("status") == "complete" else None,
                "setup": {},
                "summary": _phase_c_summary(state),
                "media_refs": _phase_c_media_refs(state),
                "raw_state": _json_safe(_sanitize_phase_c_state(state)),
            }
        )

    async def update_phase_c_state(
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
                "mode": "phase_c",
                "mode_label": "Free Speaking",
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
                    "setup": {},
                    "summary": _phase_c_summary(state),
                    "media_refs": _phase_c_media_refs(state),
                    "raw_state": _json_safe(_sanitize_phase_c_state(state)),
                }
            )
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

    async def get_profile_summary(self, *, user_id: str | None = DEFAULT_USER_ID) -> dict[str, Any]:
        sessions = [
            deepcopy(document)
            for document in self._documents.values()
            if user_id is None or document.get("user_id") == user_id
        ]
        chunks = [
            chunk for chunk in self._chunks.values()
            if user_id is None or chunk.get("user_id") == user_id
        ]
        return _build_profile_summary(user_id=user_id or "all", sessions=sessions, chunks=chunks)

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
                        "scenario_preference": state.get("scenario_preference"),
                        "voice_id": state.get("voice_id"),
                        "max_turns": state.get("max_turns"),
                        "minimum_turns": state.get("minimum_turns"),
                        "peer_profile": state.get("peer_profile"),
                        "starter_topic": state.get("starter_topic"),
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
                    "scenario_preference": state.get("scenario_preference"),
                    "voice_id": state.get("voice_id"),
                    "max_turns": state.get("max_turns"),
                    "minimum_turns": state.get("minimum_turns"),
                    "peer_profile": state.get("peer_profile"),
                    "starter_topic": state.get("starter_topic"),
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

    async def create_phase_c_session(
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
                    "mode": "phase_c",
                    "mode_label": "Free Speaking",
                    "created_at": now,
                },
                "$set": {
                    "status": state.get("status", "active"),
                    "updated_at": now,
                    "setup": {},
                    "summary": _phase_c_summary(state),
                    "media_refs": _phase_c_media_refs(state),
                    "raw_state": _json_safe(_sanitize_phase_c_state(state)),
                },
            },
            upsert=True,
        )

    async def update_phase_c_state(
        self,
        *,
        session_id: str,
        state: dict[str, Any],
    ) -> None:
        status = str(state.get("status", "active"))
        set_doc = _without_none(
            {
                "status": status,
                "updated_at": _now(),
                "completed_at": _now() if status == "complete" else None,
                "setup": {},
                "summary": _phase_c_summary(state),
                "media_refs": _phase_c_media_refs(state),
                "raw_state": _json_safe(_sanitize_phase_c_state(state)),
            }
        )
        await self._collection.update_one(
            {"session_id": session_id},
            {
                "$set": set_doc,
                "$setOnInsert": {
                    "created_at": _now(),
                    "user_id": DEFAULT_USER_ID,
                    "mode": "phase_c",
                    "mode_label": "Free Speaking",
                },
            },
            upsert=True,
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

    async def get_profile_summary(self, *, user_id: str | None = DEFAULT_USER_ID) -> dict[str, Any]:
        session_filter = {} if user_id is None else {"user_id": user_id}
        chunk_filter = {} if user_id is None else {"user_id": user_id}
        sessions = [
            _strip_mongo_id(document)
            async for document in self._collection.find(session_filter)
        ]
        chunks = [
            _strip_mongo_id(document)
            async for document in self._chunks_collection.find(chunk_filter)
        ]
        return _build_profile_summary(user_id=user_id or "all", sessions=sessions, chunks=chunks)

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
        "scenario_preference": state.get("scenario_preference"),
        "voice_id": state.get("voice_id"),
        "status": state.get("status"),
        "starter_topic": state.get("starter_topic"),
        "peer_profile": _json_safe(state.get("peer_profile")),
        "minimum_turns": state.get("minimum_turns"),
        "total_turns": len(turns),
        "avg_eye_contact_pct": round(sum(eye_contacts) / len(eye_contacts), 1) if eye_contacts else None,
        "dominant_video_emotion": dominant_video,
        "dominant_audio_emotion": dominant_audio,
        "momentum_decision": _json_safe(state.get("momentum_decision")),
        "final_report": _json_safe(state.get("final_report")),
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
                "analysis_status": turn.get("analysis_status"),
                "turn_analysis": _json_safe(turn.get("turn_analysis")),
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
        elif summary.get("overall_score") is not None:
            average_score = int(round(float(summary.get("overall_score") or 0)))
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


def _sanitize_phase_c_state(state: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(state, dict):
        return state
    sanitized = _scrub_media_paths(state)
    sanitized["video_path"] = None
    sanitized["audio_path"] = None
    return sanitized


def _phase_c_summary(state: dict[str, Any]) -> dict[str, Any] | None:
    completed_recording = state.get("completed_recording")
    if not isinstance(completed_recording, dict):
        return None

    scorecard = completed_recording.get("scorecard")
    if not isinstance(scorecard, dict):
        return None

    written_summary = completed_recording.get("written_summary")
    return {
        "session_id": state.get("session_id"),
        "overall_score": scorecard.get("overall_score"),
        "average_wpm": scorecard.get("average_wpm"),
        "filler_word_count": scorecard.get("filler_word_count"),
        "duration_seconds": scorecard.get("duration_seconds"),
        "strengths": scorecard.get("strengths") or [],
        "improvement_areas": scorecard.get("improvement_areas") or [],
        "written_summary": written_summary if isinstance(written_summary, str) else "",
    }


def _phase_c_media_refs(state: dict[str, Any]) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    recording = state.get("current_recording")
    if not isinstance(recording, dict):
        recording = state.get("completed_recording")
    if not isinstance(recording, dict):
        return refs

    session_id = str(state.get("session_id") or "")
    transcript_audio_upload = recording.get("transcript_audio_upload")
    if isinstance(transcript_audio_upload, dict):
        refs.append(
            {
                "kind": "transcript_audio_upload",
                "download_url": f"/api/phase-c/sessions/{session_id}/transcript-audio",
                "upload": _public_upload_ref(transcript_audio_upload),
            }
        )

    for chunk in recording.get("chunks") or []:
        if not isinstance(chunk, dict):
            continue
        chunk_index = int(chunk.get("chunk_index") or 0)
        for kind in ("video_upload", "audio_upload"):
            upload = chunk.get(kind)
            if not isinstance(upload, dict):
                continue
            media_kind = _phase_c_kind_to_media_name(kind)
            refs.append(
                {
                    "chunk_index": chunk_index,
                    "kind": kind,
                    "download_url": (
                        f"/api/phase-c/sessions/{session_id}/chunks/{chunk_index}/{media_kind}"
                    ),
                    "upload": _public_upload_ref(upload),
                }
            )

    return refs


def _phase_c_kind_to_media_name(kind: str) -> str:
    return "video" if kind == "video_upload" else "audio"


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


def _build_profile_summary(
    *,
    user_id: str,
    sessions: list[dict[str, Any]],
    chunks: list[dict[str, Any]],
) -> dict[str, Any]:
    phase_a_sessions = [s for s in sessions if s.get("mode") == "phase_a"]
    phase_b_sessions = [s for s in sessions if s.get("mode") == "phase_b"]

    total_practice_minutes = _estimate_practice_minutes(phase_a_sessions, chunks)

    phase_a_stats = _build_phase_a_stats(phase_a_sessions)
    phase_b_stats = _build_phase_b_stats(phase_b_sessions, chunks)

    score_history = _score_history(sessions)

    recent = sorted(sessions, key=lambda s: s.get("updated_at") or s.get("created_at") or "", reverse=True)[:10]
    recent_previews = [_profile_session_preview(s) for s in recent]

    completed_sessions = [s for s in sessions if s.get("status") == "complete"]

    return {
        "user_id": user_id,
        "total_sessions": len(sessions),
        "completed_sessions": len(completed_sessions),
        "completion_rate": round(len(completed_sessions) / len(sessions) * 100) if sessions else 0,
        "total_practice_minutes": total_practice_minutes,
        "phase_a": phase_a_stats,
        "phase_b": phase_b_stats,
        "score_history": score_history,
        "recent_sessions": recent_previews,
    }


def _build_phase_a_stats(sessions: list[dict[str, Any]]) -> dict[str, Any]:
    all_scores: list[float] = []
    scores_by_emotion: dict[str, list[float]] = {}
    filler_rates: list[float] = []
    score_over_time: list[dict[str, Any]] = []

    for session in sessions:
        summary = session.get("summary") if isinstance(session.get("summary"), dict) else {}
        setup = session.get("setup") if isinstance(session.get("setup"), dict) else {}
        target_emotion = str(setup.get("target_emotion") or "Unknown")
        match_scores = summary.get("match_scores") if isinstance(summary, dict) else None

        if isinstance(match_scores, list) and match_scores:
            avg = sum(match_scores) / len(match_scores)
            all_scores.append(avg)
            scores_by_emotion.setdefault(target_emotion, []).append(avg)
            score_over_time.append({
                "session_id": session.get("session_id"),
                "date": (session.get("completed_at") or session.get("updated_at") or ""),
                "score": round(avg * 100),
                "target_emotion": target_emotion,
            })

        rounds = summary.get("rounds") if isinstance(summary, dict) else None
        if isinstance(rounds, list):
            for rnd in rounds:
                if isinstance(rnd, dict):
                    fr = rnd.get("filler_rate")
                    if isinstance(fr, (int, float)):
                        filler_rates.append(float(fr))

    avg_by_emotion = {
        emotion: round(sum(s) / len(s) * 100)
        for emotion, s in scores_by_emotion.items()
        if s
    }

    best_emotion = max(avg_by_emotion, key=lambda e: avg_by_emotion[e]) if avg_by_emotion else None
    worst_emotion = min(avg_by_emotion, key=lambda e: avg_by_emotion[e]) if avg_by_emotion else None

    score_over_time.sort(key=lambda x: x.get("date") or "")

    return {
        "session_count": len(sessions),
        "average_match_score": round(sum(all_scores) / len(all_scores) * 100) if all_scores else None,
        "average_filler_rate": round(sum(filler_rates) / len(filler_rates), 3) if filler_rates else None,
        "average_score_by_emotion": avg_by_emotion,
        "best_emotion": best_emotion,
        "worst_emotion": worst_emotion,
        "score_over_time": score_over_time,
    }


def _build_phase_b_stats(
    sessions: list[dict[str, Any]],
    chunks: list[dict[str, Any]],
) -> dict[str, Any]:
    b_session_ids = {s.get("session_id") for s in sessions}
    b_chunks = [c for c in chunks if c.get("session_id") in b_session_ids]

    eye_contacts = [
        float(c["eye_contact_pct"])
        for c in b_chunks
        if c.get("eye_contact_pct") is not None
    ]
    video_counter = Counter(
        str(c.get("dominant_video_emotion"))
        for c in b_chunks
        if c.get("dominant_video_emotion")
    )
    audio_counter = Counter(
        str(c.get("dominant_audio_emotion"))
        for c in b_chunks
        if c.get("dominant_audio_emotion")
    )
    chunks_failed = sum(1 for c in b_chunks if c.get("status") == "failed")
    chunks_timed_out = sum(1 for c in b_chunks if c.get("status") == "timed_out")

    eye_contact_over_time: list[dict[str, Any]] = []
    for session in sorted(sessions, key=lambda s: s.get("updated_at") or s.get("created_at") or ""):
        summary = session.get("summary") if isinstance(session.get("summary"), dict) else {}
        ec = summary.get("avg_eye_contact_pct") if isinstance(summary, dict) else None
        if ec is not None:
            eye_contact_over_time.append({
                "session_id": session.get("session_id"),
                "date": session.get("completed_at") or session.get("updated_at") or "",
                "eye_contact_pct": ec,
            })

    avg_turns = None
    if sessions:
        turn_counts = [
            int((s.get("summary") or {}).get("total_turns") or 0)
            for s in sessions
            if isinstance(s.get("summary"), dict)
        ]
        if turn_counts:
            avg_turns = round(sum(turn_counts) / len(turn_counts), 1)

    return {
        "session_count": len(sessions),
        "average_eye_contact_pct": round(sum(eye_contacts) / len(eye_contacts), 1) if eye_contacts else None,
        "dominant_video_emotions": dict(video_counter.most_common(5)),
        "dominant_audio_emotions": dict(audio_counter.most_common(5)),
        "chunks_failed": chunks_failed,
        "chunks_timed_out": chunks_timed_out,
        "chunk_count": len(b_chunks),
        "avg_turns_per_session": avg_turns,
        "eye_contact_over_time": eye_contact_over_time,
    }


def _estimate_practice_minutes(
    phase_a_sessions: list[dict[str, Any]],
    chunks: list[dict[str, Any]],
) -> int:
    minutes = len(phase_a_sessions) * 3
    for chunk in chunks:
        start_ms = chunk.get("start_ms") or 0
        end_ms = chunk.get("end_ms") or 0
        if end_ms > start_ms:
            minutes += (end_ms - start_ms) / 60000
    return round(minutes)


def _profile_session_preview(session: dict[str, Any]) -> dict[str, Any]:
    summary = session.get("summary") if isinstance(session.get("summary"), dict) else {}
    setup = session.get("setup") if isinstance(session.get("setup"), dict) else {}
    mode = str(session.get("mode") or "")
    label = "Practice Session"
    score = None

    if mode == "phase_a":
        label = str(setup.get("target_emotion") or "Emotion Drill")
        scores = summary.get("match_scores") if isinstance(summary, dict) else None
        if isinstance(scores, list) and scores:
            score = round(float(sum(scores) / len(scores)) * 100)
    elif mode == "phase_b":
        label = str(setup.get("scenario") or "Conversation").replace("_", " ").title()
        ec = summary.get("avg_eye_contact_pct") if isinstance(summary, dict) else None
        if ec is not None:
            score = round(float(ec))

    return {
        "session_id": session.get("session_id"),
        "mode": mode,
        "mode_label": session.get("mode_label"),
        "label": label,
        "status": session.get("status"),
        "score": score,
        "date": session.get("completed_at") or session.get("updated_at"),
    }
