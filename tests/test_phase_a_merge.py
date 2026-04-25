import unittest
from unittest.mock import AsyncMock, patch

from backend.sprint.phase_a.graph import build_initial_state, build_merged_analysis, poll_imentiv_results, upload_to_imentiv


class PhaseAMergeTests(unittest.TestCase):
    def test_merge_correlates_words_with_nearest_stream_events(self) -> None:
        state = build_initial_state("Happiness")
        state.update(
            {
                "scenario_prompt": "Tell me about a win.",
                "transcript": "um I delivered results",
                "word_timestamps": [
                    {"word": "um", "start": 0.1, "end": 0.2},
                    {"word": "delivered", "start": 1.1, "end": 1.4},
                ],
                "video_emotions": [
                    {"emotion_type": "Happiness", "confidence": 0.72, "timestamp": 1100},
                    {"emotion_type": "Neutrality (Neutral)", "confidence": 0.4, "timestamp": 100},
                ],
                "audio_emotions": [
                    {"emotion_type": "Surprise", "confidence": 0.8, "timestamp": 1050},
                ],
            }
        )

        merged_analysis, word_correlations, match_score = build_merged_analysis(state)

        self.assertEqual(match_score, 0.72)
        self.assertEqual(merged_analysis["filler_words_found"], ["um"])
        self.assertEqual(merged_analysis["filler_word_count"], 1)
        self.assertEqual(len(word_correlations), 2)
        delivered = word_correlations[1]
        self.assertEqual(delivered["word"], "delivered")
        self.assertEqual(delivered["face_emotion_type"], "Happiness")
        self.assertEqual(delivered["voice_emotion_type"], "Surprise")

    def test_merge_handles_missing_streams_as_soft_failure(self) -> None:
        state = build_initial_state("Sadness")
        state.update(
            {
                "transcript": "",
                "word_timestamps": [],
                "video_emotions": [],
                "audio_emotions": [
                    {"emotion_type": "Sadness", "confidence": 0.5, "timestamp": 200},
                ],
            }
        )

        merged_analysis, word_correlations, match_score = build_merged_analysis(state)

        self.assertEqual(word_correlations, [])
        self.assertEqual(match_score, 0)
        self.assertTrue(merged_analysis["missing_streams"]["video"])
        self.assertFalse(merged_analysis["missing_streams"]["audio"])
        self.assertTrue(merged_analysis["missing_streams"]["transcript"])

    def test_neutrality_target_matches_neutral_api_label(self) -> None:
        state = build_initial_state("Neutrality (Neutral)")
        state.update(
            {
                "video_emotions": [
                    {"emotion_type": "neutral", "confidence": 0.84, "timestamp": 0},
                ],
            }
        )

        _, _, match_score = build_merged_analysis(state)

        self.assertEqual(match_score, 0.84)


class PhaseAImentivFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_upload_to_imentiv_uses_backend_video_analysis(self) -> None:
        state = build_initial_state("Happiness")
        state["video_upload"] = {"file_id": "video-file", "filename": "clip.webm"}
        analysis = {
            "video_id": "video-123",
            "audio_id": "audio-123",
            "video_emotions": [{"emotion_type": "happiness", "confidence": 0.9, "timestamp": 0}],
            "audio_emotions": [{"emotion_type": "confidence", "confidence": 0.7, "timestamp": 0}],
            "summary": "Good energy.",
            "confidence_score": 90.0,
            "clarity_score": 80.0,
            "resilience_score": 75.0,
            "engagement_score": 85.0,
        }

        with (
            patch("backend.sprint.phase_a.graph._send_event", new=AsyncMock()),
            patch("backend.sprint.phase_a.graph.analyze_video", new=AsyncMock(return_value=analysis)) as analyze_mock,
        ):
            result = await upload_to_imentiv(state, {"configurable": {"session_id": "session-1"}})

        self.assertIsNone(result["error"])
        self.assertEqual(result["video_id"], "video-123")
        self.assertEqual(result["audio_id"], "audio-123")
        self.assertEqual(result["imentiv_analysis"], analysis)
        self.assertEqual(result["video_emotions"], analysis["video_emotions"])
        self.assertEqual(result["audio_emotions"], analysis["audio_emotions"])
        analyze_mock.assert_awaited_once()

    async def test_poll_imentiv_results_only_transcribes_after_analysis(self) -> None:
        state = build_initial_state("Happiness")
        state["audio_upload"] = {"file_id": "audio-file", "filename": "clip.webm"}

        with (
            patch("backend.sprint.phase_a.graph._send_event", new=AsyncMock()),
            patch(
                "backend.sprint.phase_a.graph.transcribe_elevenlabs",
                new=AsyncMock(return_value=("hello there", [{"word": "hello", "start": 0.1, "end": 0.2}])),
            ),
        ):
            result = await poll_imentiv_results(state, {"configurable": {"session_id": "session-1"}})

        self.assertIsNone(result["error"])
        self.assertEqual(result["transcript"], "hello there")
        self.assertEqual(result["word_timestamps"][0]["word"], "hello")


if __name__ == "__main__":
    unittest.main()

