import unittest

from backend.sprint.phase_c.broker import (
    build_scorecard,
    classify_pacing_drift,
    compute_chunk_wpms,
    compute_flatness_flag,
    compute_nervousness_flag,
    count_fillers,
    extract_top_repeated_phrases,
    extract_top_repeated_words,
)


class PhaseCBrokerTests(unittest.TestCase):
    def test_count_fillers_handles_single_and_multi_word_fillers(self) -> None:
        total, breakdown = count_fillers(
            [
                {"word": "um"},
                {"word": "you"},
                {"word": "know"},
                {"word": "literally"},
                {"word": "hello"},
            ]
        )

        self.assertEqual(total, 3)
        self.assertEqual(breakdown["um"], 1)
        self.assertEqual(breakdown["you know"], 1)
        self.assertEqual(breakdown["literally"], 1)

    def test_repeated_words_exclude_fillers_and_stopwords(self) -> None:
        repeated = extract_top_repeated_words(
            [
                {"word": "the"},
                {"word": "um"},
                {"word": "focus"},
                {"word": "focus"},
                {"word": "focus"},
                {"word": "clarity"},
                {"word": "clarity"},
            ]
        )

        self.assertEqual(repeated[0], {"word": "focus", "count": 3})
        self.assertEqual(repeated[1], {"word": "clarity", "count": 2})

    def test_top_repeated_phrases_returns_max_three(self) -> None:
        repeated = extract_top_repeated_phrases(
            [
                {"word": "clear"},
                {"word": "next"},
                {"word": "step"},
                {"word": "clear"},
                {"word": "next"},
                {"word": "step"},
                {"word": "clear"},
                {"word": "next"},
                {"word": "step"},
            ]
        )

        self.assertLessEqual(len(repeated), 3)
        self.assertEqual(repeated[0]["phrase"], "clear next")

    def test_compute_chunk_wpms_and_pacing_drift(self) -> None:
        chunks = [
            {"chunk_index": 0, "t_start": 0, "t_end": 5000},
            {"chunk_index": 1, "t_start": 5000, "t_end": 10000},
        ]
        transcript_words = [{"word": "one", "start_ms": 100}, {"word": "two", "start_ms": 200}] + [
            {"word": f"w{index}", "start_ms": 5000 + index * 100} for index in range(20)
        ]

        wpm_by_chunk = compute_chunk_wpms(chunks, transcript_words)
        pacing = classify_pacing_drift(wpm_by_chunk)

        self.assertEqual(len(wpm_by_chunk), 2)
        self.assertEqual(pacing["trend"], "speeding_up")

    def test_flatness_and_nervousness_rules(self) -> None:
        flatness = compute_flatness_flag(
            [
                {"t_start": 0, "t_end": 5000, "dominant_video_emotion": "neutral", "dominant_audio_emotion": None},
                {"t_start": 5000, "t_end": 10000, "dominant_video_emotion": "neutral", "dominant_audio_emotion": None},
                {"t_start": 10000, "t_end": 15000, "dominant_video_emotion": "neutral", "dominant_audio_emotion": None},
                {"t_start": 15000, "t_end": 20000, "dominant_video_emotion": "neutral", "dominant_audio_emotion": None},
            ]
        )
        nervousness = compute_nervousness_flag(
            [
                {"dominant_video_emotion": "fear", "dominant_audio_emotion": None},
                {"dominant_video_emotion": "nervousness", "dominant_audio_emotion": None},
                {"dominant_video_emotion": "fear", "dominant_audio_emotion": None},
                {"dominant_video_emotion": "confidence", "dominant_audio_emotion": None},
            ]
        )

        self.assertTrue(flatness["triggered"])
        self.assertGreater(flatness["longest_neutral_run_seconds"], 15)
        self.assertTrue(nervousness["triggered"])
        self.assertGreater(nervousness["nervous_chunk_ratio"], 0.6)

    def test_build_scorecard_clamps_score(self) -> None:
        scorecard = build_scorecard(
            {
                "transcript_words": [{"word": "um", "start_ms": 0, "end_ms": 100}] * 50,
                "chunks": [
                    {
                        "chunk_index": index,
                        "t_start": index * 5000,
                        "t_end": (index + 1) * 5000,
                        "dominant_video_emotion": "neutral",
                        "dominant_audio_emotion": None,
                    }
                    for index in range(4)
                ],
                "overall": {
                    "total_chunks": 4,
                    "chunks_done": 4,
                    "chunks_failed": 0,
                    "chunks_timed_out": 0,
                    "recording_duration_ms": 20000,
                },
            },
            difficulty=5,
        )

        self.assertGreaterEqual(scorecard["overall_score"], 0)
        self.assertLessEqual(scorecard["overall_score"], 100)


if __name__ == "__main__":
    unittest.main()
