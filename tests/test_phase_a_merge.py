import unittest

from backend.sprint.phase_a.graph import build_initial_state, build_merged_analysis


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


if __name__ == "__main__":
    unittest.main()

