import unittest

from backend.shared.db import InMemorySessionRepository, reset_session_repository
from backend.sprint.phase_b.graph import _aggregate_final_metrics, merge_summary
from backend.sprint.phase_b.session_manager import get_phase_b_manager


class PhaseBGraphTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        reset_session_repository(InMemorySessionRepository())
        self.manager = get_phase_b_manager()
        self.manager._sessions.clear()
        self.session = self.manager.create_session(scenario_preference="interview")
        self.manager.start_turn(self.session.session_id, "Tell me about yourself.")

    def tearDown(self) -> None:
        self.manager._sessions.clear()
        reset_session_repository()

    async def test_merge_summary_uses_tone_and_transcript_analysis(self) -> None:
        self.manager.add_chunk(
            self.session.session_id,
            {
                "chunk_index": 0,
                "start_ms": 0,
                "end_ms": 5000,
                "mediapipe_metrics": {"avg_eye_contact_score": 0.95},
                "video_emotions": [],
                "audio_emotions": [],
                "text_emotions": [],
                "status": "done",
            },
        )
        self.manager.store_transcript(
            self.session.session_id,
            0,
            "I led the launch.",
            [
                {"word": "I", "start": 0.0, "end": 0.1},
                {"word": "led", "start": 0.1, "end": 0.2},
                {"word": "the", "start": 0.2, "end": 0.3},
                {"word": "launch.", "start": 0.3, "end": 0.5},
            ],
        )
        self.manager.store_imentiv_analysis(
            self.session.session_id,
            0,
            {
                "status": "completed",
                "audio_emotions": [{"emotion_type": "confidence", "confidence": 0.8}],
                "text_emotions": [{"emotion_type": "optimism", "confidence": 0.7}],
                "transcript_segments": [
                    {
                        "start": 0.0,
                        "end": 1.0,
                        "text": "I led the launch.",
                        "emotion": "optimism",
                        "raw_emotions": [{"label": "optimism", "score": 0.7}],
                    }
                ],
            },
        )

        await merge_summary(
            self.manager.get_state(self.session.session_id),
            {"configurable": {"session_id": self.session.session_id}},
        )

        merged = self.manager.get_turn(self.session.session_id, 0)["merged_summary"]
        self.assertEqual(merged["analysis_basis"], "audio_and_transcript")
        self.assertIsNone(merged["overall"]["dominant_video_emotion"])
        self.assertEqual(merged["overall"]["dominant_audio_emotion"], "confidence")
        self.assertEqual(merged["overall"]["dominant_text_emotion"], "optimism")
        self.assertEqual(merged["overall"]["weighted_dominant_emotion"], "confidence")
        self.assertIsNone(merged["chunks"][0]["eye_contact_pct"])

    async def test_aggregate_final_metrics_uses_merged_tone_and_text_signals(self) -> None:
        turn = self.manager.get_turn(self.session.session_id, 0)
        turn["merged_summary"] = {
            "overall": {
                "dominant_audio_emotion": "confidence",
                "audio_confidence": 0.8,
                "dominant_text_emotion": "optimism",
                "text_confidence": 0.7,
                "weighted_dominant_emotion": "confidence",
            },
            "chunks": [{"status": "done"}],
        }
        turn["turn_analysis"] = {
            "analysis_status": "ready",
            "summary": "Strong turn.",
            "momentum_score": 80,
            "content_quality_score": 78,
            "emotional_delivery_score": 76,
            "energy_match_score": 74,
            "authenticity_score": 79,
            "follow_up_invitation_score": 72,
            "strengths": ["Clear response."],
            "growth_edges": ["Add one more detail."],
        }
        turn["analysis_status"] = "ready"
        self.manager.finish_turn(self.session.session_id, 0)

        metrics = _aggregate_final_metrics(self.manager.get_state(self.session.session_id))

        self.assertEqual(metrics["analysis_basis"], "audio_and_transcript")
        self.assertIsNone(metrics["dominant_video_emotion"])
        self.assertEqual(metrics["dominant_audio_emotion"], "confidence")
        self.assertEqual(metrics["dominant_text_emotion"], "optimism")
        self.assertEqual(metrics["weighted_dominant_emotion"], "confidence")


if __name__ == "__main__":
    unittest.main()
