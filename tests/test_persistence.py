import asyncio
import unittest
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

import backend.sprint.api as sprint_api
from backend.shared.db import InMemorySessionRepository, get_media_store, reset_session_repository
from backend.shared.db.repository import MongoSessionRepository
from backend.shared.db.tasks import schedule_repository_write
from backend.sprint.phase_b.schemas import build_initial_state


class PersistenceRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = reset_session_repository(InMemorySessionRepository())

    def tearDown(self) -> None:
        reset_session_repository()

    def test_in_memory_repository_serializes_phase_a_summary(self) -> None:
        async def scenario() -> None:
            await self.repository.create_phase_a_session(
                session_id="phase-a-1",
                initial_state={
                    "target_emotion": "Happiness",
                },
            )
            await self.repository.update_phase_a_session(
                session_id="phase-a-1",
                rounds=[
                    {
                        "scenario_prompt": "Tell me about yourself.",
                        "critique": "Strong opener.",
                        "match_score": 0.82,
                        "filler_words_found": ["um"],
                        "filler_word_count": 1,
                    }
                ],
                summary={
                    "session_id": "phase-a-1",
                    "critiques": ["Strong opener."],
                    "match_scores": [0.82],
                    "filler_words": {"um": 1},
                    "rounds": [],
                },
                status="complete",
            )

        asyncio.run(scenario())

        document = asyncio.run(self.repository.get_session("phase-a-1"))
        self.assertIsNotNone(document)
        self.assertEqual(document["mode"], "phase_a")
        self.assertEqual(document["status"], "complete")
        self.assertEqual(document["summary"]["match_scores"], [0.82])

    def test_in_memory_repository_serializes_phase_a_media_refs_without_raw_paths(self) -> None:
        async def scenario() -> None:
            await self.repository.create_phase_a_session(
                session_id="phase-a-media",
                initial_state={"target_emotion": "Happiness"},
            )
            await self.repository.update_phase_a_session(
                session_id="phase-a-media",
                media_refs=[
                    {
                        "round_index": 0,
                        "kind": "video",
                        "download_url": "/api/phase-a/sessions/phase-a-media/rounds/0/video",
                        "upload": {
                            "file_id": "file-123",
                            "storage_key": "phase_a/phase-a-media/round_0/video.webm",
                            "filename": "video.webm",
                            "original_filename": "phase-a-video.webm",
                            "mime_type": "video/webm",
                            "size_bytes": 2048,
                            "uploaded_at": "2026-04-25T00:00:00+00:00",
                        },
                    }
                ],
                raw_state={
                    "target_emotion": "Happiness",
                    "video_path": "/tmp/phase-a-video.webm",
                    "audio_path": "/tmp/phase-a-audio.webm",
                    "video_upload": {
                        "path": "/tmp/phase-a-video.webm",
                        "file_id": "file-123",
                        "storage_key": "phase_a/phase-a-media/round_0/video.webm",
                        "filename": "video.webm",
                        "original_filename": "phase-a-video.webm",
                        "mime_type": "video/webm",
                        "size_bytes": 2048,
                        "uploaded_at": "2026-04-25T00:00:00+00:00",
                    },
                },
            )

        asyncio.run(scenario())

        document = asyncio.run(self.repository.get_session("phase-a-media"))
        self.assertEqual(document["media_refs"][0]["upload"]["file_id"], "file-123")
        self.assertEqual(document["media_refs"][0]["upload"]["storage_key"], "phase_a/phase-a-media/round_0/video.webm")
        self.assertNotIn("path", document["raw_state"]["video_upload"])
        self.assertIsNone(document["raw_state"]["video_path"])
        self.assertIsNone(document["raw_state"]["audio_path"])

    def test_in_memory_repository_serializes_phase_b_state(self) -> None:
        state = build_initial_state("phase-b-1", "interview", 4)
        state["status"] = "complete"
        state["turns"].append(
            {
                "turn_index": 0,
                "prompt_text": "Tell me about yourself.",
                "recording_start_ms": 0,
                "recording_end_ms": 5000,
                "chunks": [],
                "transcript": "I build useful tools.",
                "transcript_words": [],
                "merged_summary": {},
                "critique": "Clear and concise.",
            }
        )

        asyncio.run(
            self.repository.create_phase_b_session(
                session_id="phase-b-1",
                state=state,
            )
        )

        document = asyncio.run(self.repository.get_session("phase-b-1"))
        self.assertIsNotNone(document)
        self.assertEqual(document["mode"], "phase_b")
        self.assertEqual(document["summary"]["total_turns"], 1)

    def test_in_memory_repository_normalizes_phase_b_chunks_and_trends(self) -> None:
        state = build_initial_state("phase-b-chunks", "interview", 4)
        state["status"] = "complete"
        state["turns"].append(
            {
                "turn_index": 0,
                "prompt_text": "Tell me about yourself.",
                "recording_start_ms": 0,
                "recording_end_ms": 5000,
                "chunks": [
                    {
                        "chunk_index": 0,
                        "start_ms": 0,
                        "end_ms": 5000,
                        "mediapipe_metrics": {"avg_eye_contact_score": 0.75},
                        "video_emotions": [{"emotion_type": "confident", "confidence": 0.8}],
                        "audio_emotions": [{"emotion_type": "calm", "confidence": 0.7}],
                        "status": "done",
                        "video_upload": {
                            "path": "/tmp/video-0.webm",
                            "file_id": "video-file-0",
                            "storage_key": "phase_b/phase-b-chunks/turn_0/chunk_0_video.webm",
                            "filename": "chunk_0_video.webm",
                            "original_filename": "video-0.webm",
                            "mime_type": "video/webm",
                            "size_bytes": 1234,
                            "uploaded_at": "2026-04-25T00:00:00+00:00",
                        },
                        "audio_upload": {
                            "path": "/tmp/audio-0.webm",
                            "file_id": "audio-file-0",
                            "storage_key": "phase_b/phase-b-chunks/turn_0/chunk_0_audio.webm",
                            "filename": "chunk_0_audio.webm",
                            "original_filename": "audio-0.webm",
                            "mime_type": "audio/webm",
                            "size_bytes": 4321,
                            "uploaded_at": "2026-04-25T00:00:01+00:00",
                        },
                    }
                ],
                "transcript": "I build useful tools.",
                "transcript_words": [{"word": "I", "start": 0.1, "end": 0.2}],
                "transcript_audio_upload": {
                    "path": "/tmp/transcript.webm",
                    "file_id": "transcript-file-0",
                    "storage_key": "phase_b/phase-b-chunks/turn_0/transcript_audio.webm",
                    "filename": "transcript_audio.webm",
                    "original_filename": "turn-audio.webm",
                    "mime_type": "audio/webm",
                    "size_bytes": 6789,
                    "uploaded_at": "2026-04-25T00:00:02+00:00",
                },
                "merged_summary": {
                    "chunks": [
                        {
                            "t_start": 0,
                            "t_end": 5000,
                            "dominant_video_emotion": "confident",
                            "video_confidence": 0.8,
                            "dominant_audio_emotion": "calm",
                            "audio_confidence": 0.7,
                            "eye_contact_pct": 75.0,
                            "transcript_segment": "I build useful tools.",
                            "status": "done",
                        }
                    ],
                    "overall": {
                        "dominant_video_emotion": "confident",
                        "dominant_audio_emotion": "calm",
                        "avg_eye_contact_pct": 75.0,
                        "chunks_failed": 0,
                        "chunks_timed_out": 0,
                    },
                },
                "critique": "Clear and concise.",
            }
        )

        asyncio.run(
            self.repository.create_phase_b_session(
                session_id="phase-b-chunks",
                state=state,
            )
        )

        chunks = asyncio.run(self.repository.list_session_chunks("phase-b-chunks"))
        trends = asyncio.run(self.repository.get_user_trends())

        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0]["dominant_video_emotion"], "confident")
        self.assertEqual(chunks[0]["dominant_audio_emotion"], "calm")
        self.assertEqual(chunks[0]["eye_contact_pct"], 75.0)
        self.assertEqual(chunks[0]["transcript_segment"], "I build useful tools.")
        self.assertEqual(chunks[0]["video_upload"]["storage_key"], "phase_b/phase-b-chunks/turn_0/chunk_0_video.webm")
        self.assertEqual(chunks[0]["audio_upload"]["storage_key"], "phase_b/phase-b-chunks/turn_0/chunk_0_audio.webm")
        self.assertNotIn("path", chunks[0]["video_upload"])
        self.assertTrue(chunks[0]["video_upload"]["download_url"].endswith("/chunks/0/video"))
        document = asyncio.run(self.repository.get_session("phase-b-chunks"))
        self.assertEqual(len(document["media_refs"]), 3)
        self.assertEqual(document["media_refs"][0]["kind"], "turn_transcript_audio")
        self.assertNotIn("path", document["raw_state"]["turns"][0]["chunks"][0]["video_upload"])
        self.assertEqual(trends["chunk_count"], 1)
        self.assertEqual(trends["average_eye_contact_pct"], 75.0)
        self.assertEqual(trends["dominant_video_emotions"], {"confident": 1})

    def test_mongo_repository_preserves_existing_phase_b_user_id_on_update(self) -> None:
        async def scenario() -> None:
            collection = AsyncMock()
            collection.find_one = AsyncMock(return_value={"session_id": "phase-b-owned", "user_id": "user-123"})
            chunks_collection = AsyncMock()
            repo = MongoSessionRepository(
                {"db": {"practice_sessions": collection, "session_chunks": chunks_collection}},
                "db",
            )
            repo._upsert_phase_b_chunks = AsyncMock()

            state = build_initial_state("phase-b-owned", "interview", 4)
            await repo.update_phase_b_state(session_id="phase-b-owned", state=state)

            update_call = collection.update_one.await_args_list[0]
            self.assertEqual(update_call.args[0], {"session_id": "phase-b-owned"})
            self.assertEqual(update_call.args[1]["$setOnInsert"]["user_id"], "user-123")
            repo._upsert_phase_b_chunks.assert_awaited_once_with(
                session_id="phase-b-owned",
                state=state,
                user_id="user-123",
            )

        asyncio.run(scenario())

    def test_schedule_repository_write_serializes_tasks_with_same_key(self) -> None:
        async def scenario() -> None:
            events: list[str] = []

            async def write_event(name: str, delay_seconds: float) -> None:
                await asyncio.sleep(delay_seconds)
                events.append(name)

            schedule_repository_write(write_event("first", 0.02), key="phase-c-session")
            schedule_repository_write(write_event("second", 0), key="phase-c-session")
            schedule_repository_write(write_event("other", 0), key="other-session")

            await asyncio.sleep(0.08)

            self.assertEqual(events[:2], ["other", "first"])
            self.assertEqual(events[-1], "second")

        asyncio.run(scenario())

    def test_in_memory_repository_serializes_phase_c_state_and_trends(self) -> None:
        state = {
            "session_id": "phase-c-1",
            "status": "complete",
            "current_recording": None,
            "completed_recording": {
                "recording_start_ms": 0,
                "recording_end_ms": 10000,
                "chunks": [
                    {
                        "chunk_index": 0,
                        "start_ms": 0,
                        "end_ms": 5000,
                        "mediapipe_metrics": {},
                        "video_emotions": [],
                        "audio_emotions": [],
                        "status": "done",
                        "video_upload": {
                            "path": "/tmp/phase-c-video.webm",
                            "file_id": "phase-c-video-file",
                            "storage_key": "phase_c/phase-c-1/chunk_0_video.webm",
                            "filename": "chunk_0_video.webm",
                            "original_filename": "phase-c-video.webm",
                            "mime_type": "video/webm",
                            "size_bytes": 1024,
                            "uploaded_at": "2026-04-25T00:00:00+00:00",
                        },
                        "audio_upload": {
                            "path": "/tmp/phase-c-audio.webm",
                            "file_id": "phase-c-audio-file",
                            "storage_key": "phase_c/phase-c-1/chunk_0_audio.webm",
                            "filename": "chunk_0_audio.webm",
                            "original_filename": "phase-c-audio.webm",
                            "mime_type": "audio/webm",
                            "size_bytes": 512,
                            "uploaded_at": "2026-04-25T00:00:01+00:00",
                        },
                    }
                ],
                "transcript_audio_upload": {
                    "path": "/tmp/phase-c-transcript.webm",
                    "file_id": "phase-c-transcript-file",
                    "storage_key": "phase_c/phase-c-1/transcript_audio.webm",
                    "filename": "transcript_audio.webm",
                    "original_filename": "phase-c-transcript.webm",
                    "mime_type": "audio/webm",
                    "size_bytes": 2048,
                    "uploaded_at": "2026-04-25T00:00:02+00:00",
                },
                "transcript": "This is a clear update.",
                "transcript_words": [],
                "merged_analysis": {},
                "scorecard": {
                    "overall_score": 88,
                    "average_wpm": 144.2,
                    "filler_word_count": 1,
                    "duration_seconds": 10.0,
                    "strengths": ["Good pacing."],
                    "improvement_areas": ["Reduce filler words."],
                },
                "written_summary": "Strong session.",
            },
        }

        asyncio.run(
            self.repository.create_phase_c_session(
                session_id="phase-c-1",
                state=state,
            )
        )

        document = asyncio.run(self.repository.get_session("phase-c-1"))
        trends = asyncio.run(self.repository.get_user_trends())

        self.assertIsNotNone(document)
        self.assertEqual(document["mode"], "phase_c")
        self.assertEqual(document["summary"]["overall_score"], 88)
        self.assertEqual(document["media_refs"][0]["kind"], "transcript_audio_upload")
        self.assertEqual(document["media_refs"][0]["download_url"], "/api/phase-c/sessions/phase-c-1/transcript-audio")
        self.assertEqual(document["media_refs"][1]["kind"], "video_upload")
        self.assertNotIn("path", document["raw_state"]["completed_recording"]["transcript_audio_upload"])
        self.assertEqual(trends["score_history"][0]["mode"], "phase_c")
        self.assertEqual(trends["score_history"][0]["score"], 88)


class PersistenceApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = reset_session_repository(InMemorySessionRepository())
        self.client = TestClient(sprint_api.app)

    def tearDown(self) -> None:
        self.client.close()
        reset_session_repository()

    def test_recent_sessions_endpoint_returns_previews(self) -> None:
        async def seed() -> None:
            await self.repository.create_phase_a_session(
                session_id="recent-a",
                initial_state={
                    "target_emotion": "Surprise",
                },
            )
            await self.repository.update_phase_a_session(
                session_id="recent-a",
                summary={
                    "session_id": "recent-a",
                    "critiques": ["Good pacing."],
                    "match_scores": [0.9],
                    "filler_words": {},
                    "rounds": [],
                },
                status="complete",
            )

        asyncio.run(seed())

        response = self.client.get("/api/sessions/recent")

        self.assertEqual(response.status_code, 200)
        sessions = response.json()["sessions"]
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0]["session_id"], "recent-a")
        self.assertEqual(sessions[0]["mode_label"], "Emotion Drills")
        self.assertEqual(sessions[0]["score"], 90)
        self.assertEqual(sessions[0]["label"], "Surprise")

    def test_session_detail_endpoint_returns_document(self) -> None:
        asyncio.run(
            self.repository.create_phase_a_session(
                session_id="detail-a",
                initial_state={
                    "target_emotion": "Sadness",
                },
            )
        )

        response = self.client.get("/api/sessions/detail-a")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["session_id"], "detail-a")

    def test_session_replay_endpoint_returns_lean_document(self) -> None:
        state = {
            "session_id": "replay-c",
            "status": "complete",
            "completed_recording": {
                "transcript_audio_upload": {
                    "path": "/tmp/replay-c-transcript.webm",
                    "file_id": "replay-c-transcript-file",
                    "storage_key": "phase_c/replay-c/transcript_audio.webm",
                    "filename": "transcript_audio.webm",
                    "original_filename": "replay-c-transcript.webm",
                    "mime_type": "audio/webm",
                    "size_bytes": 2048,
                    "uploaded_at": "2026-04-25T00:00:02+00:00",
                },
                "merged_analysis": {
                    "chunks": [
                        {
                            "chunk_index": 0,
                            "t_start": 0,
                            "t_end": 5000,
                            "transcript_segment": "Concise update.",
                            "dominant_video_emotion": "confidence",
                            "video_confidence": 0.81,
                            "dominant_audio_emotion": "confidence",
                            "audio_confidence": 0.74,
                            "eye_contact_pct": 82.0,
                            "status": "done",
                        }
                    ]
                },
                "scorecard": {
                    "overall_score": 91,
                    "average_wpm": 148.5,
                    "filler_word_count": 3,
                    "filler_word_breakdown": {"um": 2, "like": 1},
                    "duration_seconds": 12.4,
                    "strengths": ["Clear pacing."],
                    "improvement_areas": ["Add more vocal variety."],
                },
                "written_summary": "Strong session.",
            },
        }

        asyncio.run(
            self.repository.create_phase_c_session(
                session_id="replay-c",
                state=state,
            )
        )

        response = self.client.get("/api/sessions/replay-c/replay")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["session_id"], "replay-c")
        self.assertNotIn("raw_state", payload)
        self.assertIn("media_refs", payload)
        self.assertEqual(payload["media_refs"][0]["kind"], "transcript_audio_upload")
        self.assertEqual(payload["phase_c_recording"]["scorecard"]["overall_score"], 91)
        self.assertEqual(payload["phase_c_recording"]["scorecard"]["filler_word_breakdown"], {"um": 2, "like": 1})
        self.assertEqual(payload["phase_c_recording"]["written_summary"], "Strong session.")
        self.assertEqual(payload["phase_c_recording"]["merged_chunks"][0]["chunk_index"], 0)

    def test_chunk_and_trend_endpoints_return_normalized_analytics(self) -> None:
        state = build_initial_state("api-phase-b", "public_speaking", 4)
        state["status"] = "complete"
        state["turns"].append(
            {
                "turn_index": 0,
                "prompt_text": "Give your opening.",
                "recording_start_ms": 0,
                "recording_end_ms": 5000,
                "chunks": [
                    {
                        "chunk_index": 0,
                        "start_ms": 0,
                        "end_ms": 5000,
                        "mediapipe_metrics": {"avg_eye_contact_score": 0.6},
                        "video_emotions": [{"emotion_type": "focused", "confidence": 0.9}],
                        "audio_emotions": [{"emotion_type": "steady", "confidence": 0.8}],
                        "status": "done",
                    }
                ],
                "transcript": "Welcome everyone.",
                "transcript_words": [],
                "merged_summary": {
                    "chunks": [
                        {
                            "t_start": 0,
                            "t_end": 5000,
                            "dominant_video_emotion": "focused",
                            "dominant_audio_emotion": "steady",
                            "eye_contact_pct": 60.0,
                            "transcript_segment": "Welcome everyone.",
                            "status": "done",
                        }
                    ],
                    "overall": {
                        "dominant_video_emotion": "focused",
                        "dominant_audio_emotion": "steady",
                        "avg_eye_contact_pct": 60.0,
                        "chunks_failed": 0,
                        "chunks_timed_out": 0,
                    },
                },
                "critique": "Good presence.",
            }
        )
        asyncio.run(
            self.repository.create_phase_b_session(
                session_id="api-phase-b",
                state=state,
            )
        )

        chunks_response = self.client.get("/api/sessions/api-phase-b/chunks")
        trends_response = self.client.get("/api/users/demo-user/trends")

        self.assertEqual(chunks_response.status_code, 200)
        self.assertEqual(chunks_response.json()["chunks"][0]["transcript_segment"], "Welcome everyone.")
        self.assertEqual(trends_response.status_code, 200)
        self.assertEqual(trends_response.json()["average_eye_contact_pct"], 60.0)

    def test_phase_a_download_endpoint_serves_saved_media(self) -> None:
        upload = asyncio.run(
            get_media_store().save_media(
                data=b"phase-a-video",
                storage_key="phase_a/phase-a-download/round_0/video.webm",
                original_filename="phase-a-video.webm",
                mime_type="video/webm",
            )
        )

        asyncio.run(
            self.repository.create_phase_a_session(
                session_id="phase-a-download",
                initial_state={"target_emotion": "Happiness"},
            )
        )
        asyncio.run(
            self.repository.update_phase_a_session(
                session_id="phase-a-download",
                media_refs=[
                    {
                        "round_index": 0,
                        "kind": "video",
                        "download_url": "/api/phase-a/sessions/phase-a-download/rounds/0/video",
                        "upload": upload,
                    }
                ],
            )
        )

        response = self.client.get("/api/phase-a/sessions/phase-a-download/rounds/0/video")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"phase-a-video")
        self.assertEqual(response.headers["content-type"], "video/webm")

    def test_phase_b_download_endpoint_serves_saved_chunk_media(self) -> None:
        upload = asyncio.run(
            get_media_store().save_media(
                data=b"phase-b-video",
                storage_key="phase_b/phase-b-download/turn_0/chunk_0_video.webm",
                original_filename="phase-b-video.webm",
                mime_type="video/webm",
            )
        )

        state = build_initial_state("phase-b-download", "interview", 4)
        state["turns"].append(
            {
                "turn_index": 0,
                "prompt_text": "Tell me about yourself.",
                "recording_start_ms": 0,
                "recording_end_ms": 5000,
                "chunks": [
                    {
                        "chunk_index": 0,
                        "start_ms": 0,
                        "end_ms": 5000,
                        "mediapipe_metrics": {},
                        "video_emotions": [],
                        "audio_emotions": [],
                        "status": "done",
                        "video_upload": upload,
                    }
                ],
                "transcript": "Hello",
                "transcript_words": [],
                "transcript_audio_upload": None,
                "merged_summary": {"chunks": [], "overall": {}},
                "critique": "Nice start.",
            }
        )
        asyncio.run(self.repository.create_phase_b_session(session_id="phase-b-download", state=state))
        asyncio.run(self.repository.update_phase_b_state(session_id="phase-b-download", state=state))

        response = self.client.get("/api/phase-b/sessions/phase-b-download/turns/0/chunks/0/video")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"phase-b-video")
        self.assertEqual(response.headers["content-type"], "video/webm")

    def test_phase_c_download_endpoints_serve_saved_media(self) -> None:
        chunk_upload = asyncio.run(
            get_media_store().save_media(
                data=b"phase-c-video",
                storage_key="phase_c/phase-c-download/chunk_0_video.webm",
                original_filename="phase-c-video.webm",
                mime_type="video/webm",
            )
        )
        transcript_upload = asyncio.run(
            get_media_store().save_media(
                data=b"phase-c-transcript",
                storage_key="phase_c/phase-c-download/transcript_audio.webm",
                original_filename="phase-c-transcript.webm",
                mime_type="audio/webm",
            )
        )

        state = {
            "session_id": "phase-c-download",
            "status": "complete",
            "current_recording": None,
            "completed_recording": {
                "recording_start_ms": 0,
                "recording_end_ms": 5000,
                "chunks": [
                    {
                        "chunk_index": 0,
                        "start_ms": 0,
                        "end_ms": 5000,
                        "mediapipe_metrics": {},
                        "video_emotions": [],
                        "audio_emotions": [],
                        "status": "done",
                        "video_upload": chunk_upload,
                    }
                ],
                "transcript_audio_upload": transcript_upload,
                "transcript": "hello",
                "transcript_words": [],
                "merged_analysis": {},
                "scorecard": {
                    "overall_score": 72,
                    "average_wpm": 130,
                    "filler_word_count": 0,
                    "duration_seconds": 5,
                    "strengths": [],
                    "improvement_areas": [],
                },
                "written_summary": "Solid baseline.",
            },
        }
        asyncio.run(self.repository.create_phase_c_session(session_id="phase-c-download", state=state))
        asyncio.run(self.repository.update_phase_c_state(session_id="phase-c-download", state=state))

        chunk_response = self.client.get("/api/phase-c/sessions/phase-c-download/chunks/0/video")
        transcript_response = self.client.get("/api/phase-c/sessions/phase-c-download/transcript-audio")

        self.assertEqual(chunk_response.status_code, 200)
        self.assertEqual(chunk_response.content, b"phase-c-video")
        self.assertEqual(chunk_response.headers["content-type"], "video/webm")
        self.assertEqual(transcript_response.status_code, 200)
        self.assertEqual(transcript_response.content, b"phase-c-transcript")
        self.assertEqual(transcript_response.headers["content-type"], "audio/webm")

    def test_phase_a_download_endpoint_returns_404_for_missing_gridfs_blob(self) -> None:
        asyncio.run(
            self.repository.create_phase_a_session(
                session_id="phase-a-missing",
                initial_state={"target_emotion": "Fear"},
            )
        )
        asyncio.run(
            self.repository.update_phase_a_session(
                session_id="phase-a-missing",
                media_refs=[
                    {
                        "round_index": 0,
                        "kind": "audio",
                        "download_url": "/api/phase-a/sessions/phase-a-missing/rounds/0/audio",
                        "upload": {
                            "file_id": "missing-file-id",
                            "storage_key": "phase_a/phase-a-missing/round_0/audio.webm",
                            "filename": "audio.webm",
                            "original_filename": "missing-audio.webm",
                            "mime_type": "audio/webm",
                            "size_bytes": 12,
                            "uploaded_at": "2026-04-25T00:00:00+00:00",
                        },
                    }
                ],
            )
        )

        response = self.client.get("/api/phase-a/sessions/phase-a-missing/rounds/0/audio")

        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
