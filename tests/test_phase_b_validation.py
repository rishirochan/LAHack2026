import unittest

from backend.sprint.phase_b.session_manager import get_phase_b_manager


class PhaseBValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manager = get_phase_b_manager()
        self.manager._sessions.clear()
        self.session = self.manager.create_session("interview", 5)
        self.manager.start_turn(self.session.session_id, "Tell me about yourself.")

    def tearDown(self) -> None:
        self.manager._sessions.clear()

    def _add_chunk(self, chunk_index: int, start_ms: int, end_ms: int) -> None:
        self.manager.add_chunk(
            self.session.session_id,
            {
                "chunk_index": chunk_index,
                "start_ms": start_ms,
                "end_ms": end_ms,
                "mediapipe_metrics": {},
                "video_emotions": None,
                "audio_emotions": None,
                "status": "pending",
            },
        )

    def test_validate_turn_chunks_rejects_empty_turn(self) -> None:
        is_valid, message, window = self.manager.validate_turn_chunks(
            self.session.session_id,
            min_seconds=2,
            max_seconds=45,
        )

        self.assertFalse(is_valid)
        self.assertEqual(message, "The recording was empty. Check camera and microphone access.")
        self.assertIsNone(window)

    def test_validate_turn_chunks_rejects_too_short_duration(self) -> None:
        self._add_chunk(0, 0, 1500)

        is_valid, message, window = self.manager.validate_turn_chunks(
            self.session.session_id,
            min_seconds=2,
            max_seconds=45,
        )

        self.assertFalse(is_valid)
        self.assertEqual(message, "That recording was too short. Try again with a full response.")
        self.assertIsNone(window)

    def test_validate_turn_chunks_rejects_too_long_duration(self) -> None:
        self._add_chunk(0, 0, 46000)

        is_valid, message, window = self.manager.validate_turn_chunks(
            self.session.session_id,
            min_seconds=2,
            max_seconds=45,
        )

        self.assertFalse(is_valid)
        self.assertEqual(message, "That response ran too long. Keep it under 45 seconds.")
        self.assertIsNone(window)

    def test_validate_turn_chunks_rejects_gaps(self) -> None:
        self._add_chunk(0, 0, 5000)
        self._add_chunk(1, 6000, 10000)

        is_valid, message, window = self.manager.validate_turn_chunks(
            self.session.session_id,
            min_seconds=2,
            max_seconds=45,
        )

        self.assertFalse(is_valid)
        self.assertEqual(
            message,
            "Some recording chunks were missing or overlapped. Please record that turn again.",
        )
        self.assertIsNone(window)

    def test_validate_turn_chunks_rejects_overlaps(self) -> None:
        self._add_chunk(0, 0, 5000)
        self._add_chunk(1, 4000, 10000)

        is_valid, message, window = self.manager.validate_turn_chunks(
            self.session.session_id,
            min_seconds=2,
            max_seconds=45,
        )

        self.assertFalse(is_valid)
        self.assertEqual(
            message,
            "Some recording chunks were missing or overlapped. Please record that turn again.",
        )
        self.assertIsNone(window)

    def test_validate_turn_chunks_accepts_out_of_order_contiguous_chunks(self) -> None:
        self._add_chunk(1, 5000, 10000)
        self._add_chunk(0, 0, 5000)

        is_valid, message, window = self.manager.validate_turn_chunks(
            self.session.session_id,
            min_seconds=2,
            max_seconds=45,
        )

        self.assertTrue(is_valid)
        self.assertIsNone(message)
        self.assertEqual(
            window,
            {"recording_start_ms": 0, "recording_end_ms": 10000},
        )

    def test_set_recording_window_persists_on_current_turn(self) -> None:
        self.manager.set_recording_window(self.session.session_id, 0, 10000)
        current_turn = self.manager.get_state(self.session.session_id)["current_turn"]

        self.assertIsNotNone(current_turn)
        self.assertEqual(current_turn["recording_start_ms"], 0)
        self.assertEqual(current_turn["recording_end_ms"], 10000)


if __name__ == "__main__":
    unittest.main()
