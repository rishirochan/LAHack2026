import unittest
from unittest.mock import AsyncMock, patch

from elevenlabs.core.api_error import ApiError
from fastapi.testclient import TestClient

import backend.sprint.api as sprint_api
from backend.sprint.phase_c.session_manager import get_phase_c_manager


def _file_payload(filename: str, data: bytes, content_type: str) -> tuple[str, bytes, str]:
    return (filename, data, content_type)


class PhaseCApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(sprint_api.app)
        self.manager = get_phase_c_manager()
        self.manager._sessions.clear()
        self.session = self.manager.create_session()
        self.manager.start_recording(self.session.session_id)

    def tearDown(self) -> None:
        self.manager._sessions.clear()
        self.client.close()

    def _session_url(self) -> str:
        return f"/api/phase-c/sessions/{self.session.session_id}"

    def _chunk_url(self) -> str:
        return f"/api/phase-c/sessions/{self.session.session_id}/chunks"

    def _transcribe_url(self) -> str:
        return f"/api/phase-c/sessions/{self.session.session_id}/transcribe"

    def _complete_url(self) -> str:
        return f"/api/phase-c/sessions/{self.session.session_id}/complete"

    def _post_chunk(self, *, chunk_index: int, start_ms: int, end_ms: int, video_data: bytes = b"video", audio_data: bytes = b"audio"):
        with patch("backend.sprint.api._process_phase_c_chunk", new=AsyncMock(return_value=None)):
            return self.client.post(
                self._chunk_url(),
                data={
                    "chunk_index": str(chunk_index),
                    "start_ms": str(start_ms),
                    "end_ms": str(end_ms),
                    "mediapipe_metrics": "{}",
                },
                files={
                    "video_file": _file_payload("video.webm", video_data, "video/webm"),
                    "audio_file": _file_payload("audio.webm", audio_data, "audio/webm"),
                },
            )

    def test_create_session_succeeds(self) -> None:
        response = self.client.post("/api/phase-c/sessions", json={})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "active")

    def test_create_session_accepts_empty_request_body(self) -> None:
        response = self.client.post("/api/phase-c/sessions")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "active")

    def test_recording_start_emits_recording_ready(self) -> None:
        session = self.manager.create_session()
        response = self.client.post(f"/api/phase-c/sessions/{session.session_id}/recording/start")

        self.assertEqual(response.status_code, 200)
        pending_events = self.manager.get_session(session.session_id).pending_events
        self.assertEqual(pending_events[-1]["type"], "recording_ready")
        self.assertEqual(pending_events[-1]["payload"]["max_seconds"], 45)

    def test_chunk_upload_rejects_invalid_time_range(self) -> None:
        response = self._post_chunk(chunk_index=0, start_ms=1000, end_ms=1000)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Chunk end_ms must be greater than start_ms.")

    def test_chunk_upload_rejects_duplicates(self) -> None:
        first = self._post_chunk(chunk_index=0, start_ms=0, end_ms=5000)
        second = self._post_chunk(chunk_index=0, start_ms=5000, end_ms=10000)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 409)

    def test_chunk_upload_rejects_zero_byte_files(self) -> None:
        response = self._post_chunk(chunk_index=0, start_ms=0, end_ms=5000, video_data=b"", audio_data=b"")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Chunk uploads must contain non-empty audio and video.")

    def test_transcribe_rejects_zero_byte_audio(self) -> None:
        response = self.client.post(
            self._transcribe_url(),
            files={"audio_file": _file_payload("audio.webm", b"", "audio/webm")},
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["detail"], "The recording was empty. Check camera and microphone access.")

    def test_transcribe_stores_transcript_audio_upload_and_transcript(self) -> None:
        with patch(
            "backend.sprint.phase_c.elevenlabs.transcribe_audio",
            new=AsyncMock(return_value=("A concise update.", [{"word": "A", "start": 0.0, "end": 0.1}])),
        ):
            response = self.client.post(
                self._transcribe_url(),
                files={"audio_file": _file_payload("audio.webm", b"audio-bytes", "audio/webm")},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["transcript"], "A concise update.")
        recording = self.manager.get_state(self.session.session_id)["current_recording"]
        self.assertIsNotNone(recording)
        self.assertEqual(recording["transcript"], "A concise update.")
        self.assertEqual(recording["transcript_audio_upload"]["storage_key"], f"phase_c/{self.session.session_id}/transcript_audio.webm")

    def test_transcribe_returns_actionable_error_for_missing_speech_to_text_permission(self) -> None:
        with patch(
            "backend.sprint.phase_c.elevenlabs.transcribe_audio",
            new=AsyncMock(
                side_effect=ApiError(
                    status_code=401,
                    body={
                        "detail": {
                            "status": "missing_permissions",
                            "message": "The API key you used is missing the permission speech_to_text to execute this operation.",
                        }
                    },
                )
            ),
        ):
            response = self.client.post(
                self._transcribe_url(),
                files={"audio_file": _file_payload("audio.webm", b"audio-bytes", "audio/webm")},
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["detail"],
            "Speech transcription is unavailable because the configured ElevenLabs API key does not include the "
            "speech_to_text permission. Update ELEVENLABS_API_KEY to a key with Speech-to-Text access.",
        )

    def test_complete_rejects_no_chunks(self) -> None:
        graph_mock = AsyncMock(return_value={})
        with patch.object(sprint_api.phase_c_graph, "ainvoke", graph_mock):
            response = self.client.post(self._complete_url())

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["detail"], "The recording was empty. Check camera and microphone access.")
        graph_mock.assert_not_awaited()

    def test_complete_rejects_short_recording(self) -> None:
        self.manager.add_chunk(
            self.session.session_id,
            {
                "chunk_index": 0,
                "start_ms": 0,
                "end_ms": 1500,
                "mediapipe_metrics": {},
                "video_emotions": [],
                "audio_emotions": [],
                "status": "done",
            },
        )

        graph_mock = AsyncMock(return_value={})
        with patch.object(sprint_api.phase_c_graph, "ainvoke", graph_mock):
            response = self.client.post(self._complete_url())

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["detail"], "That recording was too short. Try again with a full response.")
        graph_mock.assert_not_awaited()

    def test_complete_rejects_long_recording(self) -> None:
        self.manager.add_chunk(
            self.session.session_id,
            {
                "chunk_index": 0,
                "start_ms": 0,
                "end_ms": 46000,
                "mediapipe_metrics": {},
                "video_emotions": [],
                "audio_emotions": [],
                "status": "done",
            },
        )

        graph_mock = AsyncMock(return_value={})
        with patch.object(sprint_api.phase_c_graph, "ainvoke", graph_mock):
            response = self.client.post(self._complete_url())

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["detail"], "That response ran too long. Keep it under 45 seconds.")
        graph_mock.assert_not_awaited()

    def test_complete_rejects_gaps_and_overlaps(self) -> None:
        self.manager.add_chunk(
            self.session.session_id,
            {
                "chunk_index": 0,
                "start_ms": 0,
                "end_ms": 5000,
                "mediapipe_metrics": {},
                "video_emotions": [],
                "audio_emotions": [],
                "status": "done",
            },
        )
        self.manager.add_chunk(
            self.session.session_id,
            {
                "chunk_index": 1,
                "start_ms": 6000,
                "end_ms": 10000,
                "mediapipe_metrics": {},
                "video_emotions": [],
                "audio_emotions": [],
                "status": "done",
            },
        )

        graph_mock = AsyncMock(return_value={})
        with patch.object(sprint_api.phase_c_graph, "ainvoke", graph_mock):
            response = self.client.post(self._complete_url())

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["detail"], "Some recording chunks were missing or overlapped. Please record that turn again.")
        graph_mock.assert_not_awaited()

    def test_complete_accepts_contiguous_out_of_order_chunks_and_emits_session_result(self) -> None:
        self.manager.add_chunk(
            self.session.session_id,
            {
                "chunk_index": 1,
                "start_ms": 5000,
                "end_ms": 10000,
                "mediapipe_metrics": {"avg_eye_contact_score": 0.6},
                "video_emotions": [{"emotion_type": "confidence", "confidence": 0.8, "timestamp": 0}],
                "audio_emotions": [{"emotion_type": "confidence", "confidence": 0.7, "timestamp": 0}],
                "status": "done",
            },
        )
        self.manager.add_chunk(
            self.session.session_id,
            {
                "chunk_index": 0,
                "start_ms": 0,
                "end_ms": 5000,
                "mediapipe_metrics": {"avg_eye_contact_score": 0.7},
                "video_emotions": [{"emotion_type": "neutral", "confidence": 0.6, "timestamp": 0}],
                "audio_emotions": [{"emotion_type": "neutral", "confidence": 0.5, "timestamp": 0}],
                "status": "done",
            },
        )
        self.manager.store_transcript(
            self.session.session_id,
            "clear next step",
            [
                {"word": "clear", "start": 0.1, "end": 0.2},
                {"word": "next", "start": 5.2, "end": 5.3},
                {"word": "step", "start": 5.5, "end": 5.6},
            ],
        )

        with (
            patch("backend.sprint.phase_c.graph.get_ai_service", return_value=object()),
            patch("backend.sprint.phase_c.graph.generate_phase_c_summary", new=AsyncMock(return_value="Strong finish.")),
        ):
            response = self.client.post(self._complete_url())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "complete"})
        state = self.manager.get_state(self.session.session_id)
        self.assertEqual(state["status"], "complete")
        self.assertIsNone(state["current_recording"])
        self.assertEqual(state["completed_recording"]["recording_start_ms"], 0)
        self.assertEqual(state["completed_recording"]["recording_end_ms"], 10000)
        pending_events = self.manager.get_session(self.session.session_id).pending_events
        self.assertEqual(pending_events[-1]["type"], "session_result")
        self.assertIn("scorecard", pending_events[-1]["payload"])
        self.assertEqual(pending_events[-1]["payload"]["written_summary"], "Strong finish.")


if __name__ == "__main__":
    unittest.main()
