import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

import backend.sprint.api as sprint_api
from backend.shared.db import InMemorySessionRepository, reset_session_repository
from backend.sprint.phase_b.session_manager import get_phase_b_manager


class TtsSettingsApiTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_session_repository(InMemorySessionRepository())
        self.client = TestClient(sprint_api.app)
        self.manager = get_phase_b_manager()
        self.manager._sessions.clear()

    def tearDown(self) -> None:
        self.manager._sessions.clear()
        self.client.close()
        reset_session_repository()

    def test_list_tts_voices_returns_normalized_options(self) -> None:
        ai_service = SimpleNamespace(elevenlabs_client=object(), settings=SimpleNamespace())

        with (
            patch("backend.shared.ai.get_ai_service", return_value=ai_service),
            patch(
                "backend.shared.ai.providers.elevenlabs.list_voice_options",
                return_value=[
                    {
                        "voice_id": "voice-1",
                        "name": "Alloy",
                        "category": "premade",
                        "description": "Warm and clear.",
                        "preview_url": None,
                        "is_default": True,
                    }
                ],
            ),
        ):
            response = self.client.get("/api/tts/voices")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "voices": [
                    {
                        "voice_id": "voice-1",
                        "name": "Alloy",
                        "category": "premade",
                        "description": "Warm and clear.",
                        "preview_url": None,
                        "is_default": True,
                    }
                ]
            },
        )

    def test_preview_tts_voice_builds_name_based_sample(self) -> None:
        ai_service = SimpleNamespace()
        synthesize_mock = AsyncMock(return_value=b"preview-audio")

        with (
            patch("backend.shared.ai.get_ai_service", return_value=ai_service),
            patch("backend.sprint.phase_b.elevenlabs.synthesize_tts_audio", synthesize_mock),
        ):
            response = self.client.post(
                "/api/tts/preview",
                json={"voice_id": "voice-42", "voice_name": "Ava"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"preview-audio")
        self.assertEqual(response.headers["content-type"], "audio/mpeg")
        synthesize_mock.assert_awaited_once()
        self.assertEqual(synthesize_mock.await_args.kwargs["voice_id"], "voice-42")
        self.assertEqual(
            synthesize_mock.await_args.kwargs["text"],
            "Hi, my name is Ava. Here's what I sound like at your selected speed.",
        )

    def test_phase_a_tts_endpoint_returns_audio(self) -> None:
        ai_service = SimpleNamespace()
        synthesize_mock = AsyncMock(return_value=b"phase-a-audio")

        with (
            patch("backend.shared.ai.get_ai_service", return_value=ai_service),
            patch("backend.sprint.phase_b.elevenlabs.synthesize_tts_audio", synthesize_mock),
        ):
            response = self.client.post(
                "/api/phase-a/tts",
                json={"text": "Practice this line."},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"phase-a-audio")
        self.assertEqual(response.headers["content-type"], "audio/mpeg")
        self.assertEqual(
            synthesize_mock.await_args.kwargs["text"],
            "Practice this line.",
        )

    def test_phase_b_next_turn_updates_voice_id_before_prompt(self) -> None:
        session = self.manager.create_session(
            scenario_preference="interview",
            voice_id="voice-old",
        )

        with (
            patch.object(sprint_api.prompt_graph, "ainvoke", AsyncMock(return_value={})),
            patch("backend.sprint.api.stream_peer_tts", AsyncMock(return_value=None)),
        ):
            response = self.client.post(
                f"/api/phase-b/sessions/{session.session_id}/turns/next",
                json={"voice_id": "voice-new"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "prompt_sent"})
        self.assertEqual(self.manager.get_state(session.session_id)["voice_id"], "voice-new")


if __name__ == "__main__":
    unittest.main()
