import asyncio
import unittest

from fastapi.testclient import TestClient

import backend.sprint.api as sprint_api
from backend.shared.db import InMemorySessionRepository, reset_session_repository
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
                    "theme": "Job Interview",
                    "target_emotion": "Confident",
                    "difficulty": 5,
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

    def test_in_memory_repository_serializes_phase_b_state(self) -> None:
        state = build_initial_state("phase-b-1", "interview", 7, 4)
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
        state = build_initial_state("phase-b-chunks", "interview", 7, 4)
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
                    }
                ],
                "transcript": "I build useful tools.",
                "transcript_words": [{"word": "I", "start": 0.1, "end": 0.2}],
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
        self.assertEqual(trends["chunk_count"], 1)
        self.assertEqual(trends["average_eye_contact_pct"], 75.0)
        self.assertEqual(trends["dominant_video_emotions"], {"confident": 1})


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
                    "theme": "Public Speaking",
                    "target_emotion": "Confident",
                    "difficulty": 6,
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

    def test_session_detail_endpoint_returns_document(self) -> None:
        asyncio.run(
            self.repository.create_phase_a_session(
                session_id="detail-a",
                initial_state={
                    "theme": "Casual Conversation",
                    "target_emotion": "Calm",
                    "difficulty": 3,
                },
            )
        )

        response = self.client.get("/api/sessions/detail-a")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["session_id"], "detail-a")

    def test_chunk_and_trend_endpoints_return_normalized_analytics(self) -> None:
        state = build_initial_state("api-phase-b", "public_speaking", 8, 4)
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


if __name__ == "__main__":
    unittest.main()
