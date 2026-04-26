import unittest

from backend.shared.word_analysis import count_fillers
from backend.sprint.phase_c.broker import (
    build_scorecard,
    build_patterns,
    classify_pacing_drift,
    compute_chunk_wpms,
    compute_flatness_flag,
    compute_nervousness_flag,
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
                {"word": "basically,"},
                {"word": "hello"},
            ]
        )

        self.assertEqual(total, 3)
        self.assertEqual(breakdown["um"], 1)
        self.assertEqual(breakdown["you know"], 1)
        self.assertEqual(breakdown["basically"], 1)

    def test_count_fillers_only_counts_contextual_words_when_they_behave_like_fillers(self) -> None:
        total, breakdown = count_fillers(
            [
                {"word": "I", "start_ms": 0, "end_ms": 80},
                {"word": "am", "start_ms": 90, "end_ms": 150},
                {"word": "like", "start_ms": 160, "end_ms": 210},
                {"word": "the", "start_ms": 220, "end_ms": 260},
                {"word": "one", "start_ms": 270, "end_ms": 330},
                {"word": "you", "start_ms": 340, "end_ms": 390},
                {"word": "mentioned.", "start_ms": 400, "end_ms": 470},
                {"word": "Actually", "start_ms": 900, "end_ms": 980},
                {"word": "the", "start_ms": 990, "end_ms": 1040},
                {"word": "tradeoff", "start_ms": 1050, "end_ms": 1140},
                {"word": "is", "start_ms": 1150, "end_ms": 1200},
                {"word": "real.", "start_ms": 1210, "end_ms": 1290},
                {"word": "So", "start_ms": 1600, "end_ms": 1650},
                {"word": "accuracy", "start_ms": 1660, "end_ms": 1740},
                {"word": "matters.", "start_ms": 1750, "end_ms": 1820},
            ]
        )

        self.assertEqual(total, 0)
        self.assertEqual(breakdown, {})

    def test_count_fillers_counts_contextual_words_when_commas_or_pauses_signal_fillers(self) -> None:
        total, breakdown = count_fillers(
            [
                {"word": "This", "start_ms": 0, "end_ms": 80},
                {"word": "can", "start_ms": 90, "end_ms": 150},
                {"word": "make,", "start_ms": 160, "end_ms": 240},
                {"word": "like,", "start_ms": 520, "end_ms": 600},
                {"word": "your", "start_ms": 910, "end_ms": 970},
                {"word": "product", "start_ms": 980, "end_ms": 1060},
                {"word": "feel", "start_ms": 1070, "end_ms": 1130},
                {"word": "worse.", "start_ms": 1140, "end_ms": 1220},
                {"word": "Basically,", "start_ms": 1600, "end_ms": 1690},
                {"word": "we", "start_ms": 2050, "end_ms": 2100},
                {"word": "wait.", "start_ms": 2110, "end_ms": 2190},
            ]
        )

        self.assertEqual(total, 2)
        self.assertEqual(breakdown["like"], 1)
        self.assertEqual(breakdown["basically"], 1)

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
        )

        self.assertGreaterEqual(scorecard["overall_score"], 0)
        self.assertLessEqual(scorecard["overall_score"], 100)

    def test_build_patterns_uses_face_voice_fallback_when_face_data_is_missing(self) -> None:
        patterns = build_patterns(
            {
                "duration_seconds": 20,
                "filler_word_count": 0,
                "pacing_drift": {"trend": "stable", "average_wpm": 140, "too_fast_chunks": 0, "too_slow_chunks": 0},
                "emotion_flags": {
                    "emotional_flatness": {"triggered": False},
                    "nervousness_persistence": {"triggered": False},
                },
                "repetition": {"top_repeated_words": [], "top_repeated_phrases": []},
            },
            {
                "chunks": [
                    {"t_start": 0, "t_end": 5000, "dominant_video_emotion": None, "dominant_audio_emotion": "confidence"},
                    {"t_start": 5000, "t_end": 10000, "dominant_video_emotion": None, "dominant_audio_emotion": "calm"},
                ]
            },
        )

        agreement_pattern = next(pattern for pattern in patterns if pattern["category"] == "face_voice_agreement")
        self.assertEqual(agreement_pattern["label"], "Voice-face agreement 57%")


if __name__ == "__main__":
    unittest.main()
