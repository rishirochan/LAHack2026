import unittest
from unittest.mock import AsyncMock, patch

from elevenlabs.core.api_error import ApiError
from fastapi.testclient import TestClient

import backend.sprint.api as sprint_api
from backend.shared.db import InMemorySessionRepository, reset_session_repository
from backend.sprint.phase_b.session_manager import get_phase_b_manager


def _file_payload(filename: str, data: bytes, content_type: str) -> tuple[str, bytes, str]:
    return (filename, data, content_type)


class PhaseBApiTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_session_repository(InMemorySessionRepository())
        self.client = TestClient(sprint_api.app)
        self.manager = get_phase_b_manager()
        self.manager._sessions.clear()
        self.session = self.manager.create_session(scenario_preference="interview")
        self.manager.start_turn(self.session.session_id, "Tell me about yourself.")

    def tearDown(self) -> None:
        self.manager._sessions.clear()
        self.client.close()
        reset_session_repository()

    def _chunk_url(self) -> str:
        return f"/api/phase-b/sessions/{self.session.session_id}/turns/0/chunks"

    def _complete_url(self) -> str:
        return f"/api/phase-b/sessions/{self.session.session_id}/turns/0/complete"

    def _transcribe_url(self) -> str:
        return f"/api/phase-b/sessions/{self.session.session_id}/turns/0/transcribe"

    def _post_chunk(self, *, chunk_index: int, start_ms: int, end_ms: int, video_data: bytes = b"video", audio_data: bytes = b"audio"):
        with patch("backend.sprint.api._process_phase_b_chunk", new=AsyncMock(return_value=None)):
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

    def test_chunk_upload_rejects_invalid_time_range(self) -> None:
        response = self._post_chunk(chunk_index=0, start_ms=5000, end_ms=5000)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Chunk end_ms must be greater than start_ms.")

    def test_chunk_upload_rejects_duplicate_chunk_index(self) -> None:
        first = self._post_chunk(chunk_index=0, start_ms=0, end_ms=5000)
        second = self._post_chunk(chunk_index=0, start_ms=5000, end_ms=10000)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 409)
        self.assertEqual(second.json()["detail"], "Chunk 0 has already been uploaded.")

    def test_chunk_upload_rejects_zero_byte_files(self) -> None:
        response = self._post_chunk(chunk_index=0, start_ms=0, end_ms=5000, video_data=b"", audio_data=b"")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Chunk uploads must contain non-empty audio and video.")

    def test_transcribe_rejects_zero_byte_audio_and_emits_retry(self) -> None:
        response = self.client.post(
            self._transcribe_url(),
            files={"audio_file": _file_payload("audio.webm", b"", "audio/webm")},
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.json()["detail"],
            "The recording was empty. Check camera and microphone access.",
        )
        pending_events = self.manager.get_session(self.session.session_id).pending_events
        self.assertEqual(pending_events[-1]["type"], "retry_recording")
        self.assertEqual(
            pending_events[-1]["payload"]["message"],
            "The recording was empty. Check camera and microphone access.",
        )

    def test_transcribe_returns_actionable_error_for_missing_speech_to_text_permission(self) -> None:
        with patch(
            "backend.sprint.phase_b.elevenlabs.transcribe_audio",
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

    def test_start_session_stores_practice_prompt(self) -> None:
        self.manager._sessions.clear()

        response = self.client.post(
            "/api/phase-b/sessions",
            json={
                "practice_prompt": "I have a Roblox interview tomorrow and want to practice with a thoughtful hiring manager.",
                "voice_id": "voice-42",
            },
        )

        self.assertEqual(response.status_code, 200)
        session_id = response.json()["session_id"]
        state = self.manager.get_state(session_id)
        self.assertEqual(
            state["practice_prompt"],
            "I have a Roblox interview tomorrow and want to practice with a thoughtful hiring manager.",
        )
        self.assertEqual(state["voice_id"], "voice-42")

    def test_start_session_rejects_prompt_over_word_limit(self) -> None:
        self.manager._sessions.clear()
        over_limit_prompt = " ".join(f"word{i}" for i in range(61))

        response = self.client.post(
            "/api/phase-b/sessions",
            json={"practice_prompt": over_limit_prompt},
        )

        self.assertEqual(response.status_code, 422)
        self.assertIn("Practice prompt must be 60 words or fewer.", str(response.json()["detail"]))

    def test_complete_rejects_turn_with_no_chunks(self) -> None:
        critique_mock = AsyncMock(return_value={})
        with patch.object(sprint_api.critique_graph, "ainvoke", critique_mock):
            response = self.client.post(self._complete_url())

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.json()["detail"],
            "The recording was empty. Check camera and microphone access.",
        )
        critique_mock.assert_not_awaited()

    def test_complete_rejects_short_recording(self) -> None:
        self.manager.add_chunk(
            self.session.session_id,
            {
                "chunk_index": 0,
                "start_ms": 0,
                "end_ms": 1500,
                "mediapipe_metrics": {},
                "video_emotions": None,
                "audio_emotions": None,
                "status": "done",
            },
        )

        critique_mock = AsyncMock(return_value={})
        with patch.object(sprint_api.critique_graph, "ainvoke", critique_mock):
            response = self.client.post(self._complete_url())

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.json()["detail"],
            "That recording was too short. Try again with a full response.",
        )
        critique_mock.assert_not_awaited()

    def test_complete_rejects_long_recording(self) -> None:
        self.manager.add_chunk(
            self.session.session_id,
            {
                "chunk_index": 0,
                "start_ms": 0,
                "end_ms": 46000,
                "mediapipe_metrics": {},
                "video_emotions": None,
                "audio_emotions": None,
                "status": "done",
            },
        )

        critique_mock = AsyncMock(return_value={})
        with patch.object(sprint_api.critique_graph, "ainvoke", critique_mock):
            response = self.client.post(self._complete_url())

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["detail"], "That response ran too long. Keep it under 45 seconds.")
        critique_mock.assert_not_awaited()

    def test_complete_rejects_gap_between_chunks(self) -> None:
        self.manager.add_chunk(
            self.session.session_id,
            {
                "chunk_index": 0,
                "start_ms": 0,
                "end_ms": 5000,
                "mediapipe_metrics": {},
                "video_emotions": None,
                "audio_emotions": None,
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
                "video_emotions": None,
                "audio_emotions": None,
                "status": "done",
            },
        )

        critique_mock = AsyncMock(return_value={})
        with patch.object(sprint_api.critique_graph, "ainvoke", critique_mock):
            response = self.client.post(self._complete_url())

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.json()["detail"],
            "Some recording chunks were missing or overlapped. Please record that turn again.",
        )
        critique_mock.assert_not_awaited()

    def test_complete_rejects_overlapping_chunks(self) -> None:
        self.manager.add_chunk(
            self.session.session_id,
            {
                "chunk_index": 0,
                "start_ms": 0,
                "end_ms": 5000,
                "mediapipe_metrics": {},
                "video_emotions": None,
                "audio_emotions": None,
                "status": "done",
            },
        )
        self.manager.add_chunk(
            self.session.session_id,
            {
                "chunk_index": 1,
                "start_ms": 4000,
                "end_ms": 10000,
                "mediapipe_metrics": {},
                "video_emotions": None,
                "audio_emotions": None,
                "status": "done",
            },
        )

        critique_mock = AsyncMock(return_value={})
        with patch.object(sprint_api.critique_graph, "ainvoke", critique_mock):
            response = self.client.post(self._complete_url())

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.json()["detail"],
            "Some recording chunks were missing or overlapped. Please record that turn again.",
        )
        critique_mock.assert_not_awaited()

    def test_complete_accepts_out_of_order_contiguous_chunks_and_persists_window(self) -> None:
        self.manager.add_chunk(
            self.session.session_id,
            {
                "chunk_index": 1,
                "start_ms": 5000,
                "end_ms": 10000,
                "mediapipe_metrics": {},
                "video_emotions": [],
                "audio_emotions": [],
                "status": "done",
            },
        )
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
        self.manager.store_transcript(self.session.session_id, 0, "hello there", [])

        critique_mock = AsyncMock(return_value={})
        with patch.object(sprint_api.critique_graph, "ainvoke", critique_mock):
            response = self.client.post(self._complete_url())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "turn_complete")
        self.assertTrue(response.json()["continue_conversation"])
        critique_mock.assert_awaited_once()
        state = self.manager.get_state(self.session.session_id)
        finished_turn = state["turns"][0]
        self.assertEqual(finished_turn["recording_start_ms"], 0)
        self.assertEqual(finished_turn["recording_end_ms"], 10000)
        self.assertEqual(state["turn_index"], 1)

    def test_complete_uses_transcript_audio_upload_for_tone_analysis(self) -> None:
        self.manager.add_chunk(
            self.session.session_id,
            {
                "chunk_index": 0,
                "start_ms": 0,
                "end_ms": 5000,
                "mediapipe_metrics": {},
                "video_emotions": [],
                "audio_emotions": [],
                "text_emotions": [],
                "status": "done",
            },
        )
        transcript_upload = {
            "file_id": "turn-audio-file",
            "storage_key": "phase_b/test/turn_0/transcript_audio.webm",
            "filename": "transcript_audio.webm",
            "original_filename": "turn-audio.webm",
            "mime_type": "audio/webm",
            "size_bytes": 123,
            "uploaded_at": "2026-04-25T00:00:00+00:00",
        }
        self.manager.store_transcript_upload(self.session.session_id, 0, transcript_upload)
        self.manager.store_transcript(self.session.session_id, 0, "hello there", [])

        critique_mock = AsyncMock(return_value={})
        analyze_audio_mock = AsyncMock(
            return_value={
                "status": "completed",
                "audio_emotions": [{"emotion_type": "calm", "confidence": 0.8}],
                "text_emotions": [{"emotion_type": "optimism", "confidence": 0.7}],
                "transcript_segments": [],
            }
        )
        with (
            patch.object(sprint_api.critique_graph, "ainvoke", critique_mock),
            patch("backend.sprint.phase_b.imentiv.analyze_audio", analyze_audio_mock),
        ):
            response = self.client.post(self._complete_url())

        self.assertEqual(response.status_code, 200)
        analyze_audio_mock.assert_awaited_once()
        self.assertEqual(analyze_audio_mock.await_args.args[1], transcript_upload)
        state = self.manager.get_state(self.session.session_id)
        self.assertEqual(state["turns"][0]["imentiv_analysis"]["status"], "completed")


if __name__ == "__main__":
    unittest.main()
