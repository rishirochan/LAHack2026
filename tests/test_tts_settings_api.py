import unittest
import asyncio
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

    def test_preview_tts_voice_allows_default_voice_when_voice_id_is_missing(self) -> None:
        ai_service = SimpleNamespace()
        synthesize_mock = AsyncMock(return_value=b"preview-audio")

        with (
            patch("backend.shared.ai.get_ai_service", return_value=ai_service),
            patch("backend.sprint.phase_b.elevenlabs.synthesize_tts_audio", synthesize_mock),
        ):
            response = self.client.post(
                "/api/tts/preview",
                json={"voice_name": "Ava", "text": "Replay this line."},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"preview-audio")
        self.assertIsNone(synthesize_mock.await_args.kwargs["voice_id"])
        self.assertEqual(synthesize_mock.await_args.kwargs["text"], "Replay this line.")

    def test_phase_b_next_turn_updates_voice_id_before_prompt(self) -> None:
        session = self.manager.create_session(
            scenario_preference="interview",
            voice_id="voice-old",
        )

        async def fake_prompt_graph(*args, **kwargs):
            self.manager.start_turn(session.session_id, "Thanks for joining me today.")
            return {}

        with (
            patch.object(sprint_api.prompt_graph, "ainvoke", fake_prompt_graph),
            patch("backend.sprint.api.stream_peer_tts", AsyncMock(return_value=None)),
        ):
            response = self.client.post(
                f"/api/phase-b/sessions/{session.session_id}/turns/next",
                json={"voice_id": "voice-new"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "prompt_sent"})
        self.assertEqual(self.manager.get_state(session.session_id)["voice_id"], "voice-new")

    def test_phase_b_next_turn_can_skip_peer_tts(self) -> None:
        session = self.manager.create_session(
            scenario_preference="interview",
            voice_id="voice-old",
        )

        async def fake_prompt_graph(*args, **kwargs):
            self.manager.start_turn(session.session_id, "Thanks for joining me today.")
            return {}

        stream_tts_mock = AsyncMock(return_value=None)
        with (
            patch.object(sprint_api.prompt_graph, "ainvoke", fake_prompt_graph),
            patch("backend.sprint.api.stream_peer_tts", stream_tts_mock),
        ):
            response = self.client.post(
                f"/api/phase-b/sessions/{session.session_id}/turns/next",
                json={"voice_id": "voice-old", "speak_peer_message": False},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "prompt_sent"})
        stream_tts_mock.assert_not_awaited()
        pending_events = self.manager.get_session(session.session_id).pending_events
        self.assertEqual(pending_events[-1]["type"], "recording_ready")

    def test_phase_b_next_turn_suppresses_follow_up_events_after_end(self) -> None:
        session = self.manager.create_session(
            scenario_preference="interview",
            voice_id="voice-old",
        )

        async def fake_prompt_graph(*args, **kwargs):
            self.manager.start_turn(session.session_id, "One more question before we wrap.")
            self.manager.begin_session_shutdown(session.session_id)
            return {}

        stream_tts_mock = AsyncMock(return_value=None)
        with (
            patch.object(sprint_api.prompt_graph, "ainvoke", fake_prompt_graph),
            patch("backend.sprint.api.stream_peer_tts", stream_tts_mock),
        ):
            response = self.client.post(
                f"/api/phase-b/sessions/{session.session_id}/turns/next",
                json={"voice_id": "voice-old"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "session_complete"})
        stream_tts_mock.assert_not_awaited()
        self.assertEqual(self.manager.get_state(session.session_id)["current_turn"], None)
        self.assertEqual(self.manager.get_session(session.session_id).pending_events, [])

    def test_stream_peer_tts_stops_when_session_has_been_ended(self) -> None:
        session = self.manager.create_session(
            scenario_preference="interview",
            voice_id="voice-old",
        )
        self.manager.start_turn(session.session_id, "Tell me about the next step.")
        original_send_event = self.manager.send_event

        async def fake_stream(*args, **kwargs):
            yield "chunk-one"
            yield "chunk-two"

        async def wrapped_send_event(session_id: str, event_type: str, payload: dict[str, object]):
            await original_send_event(session_id, event_type, payload)
            if event_type == "audio_chunk":
                self.manager.begin_session_shutdown(session.session_id)

        with (
            patch("backend.sprint.phase_b.graph.stream_tts_chunks", fake_stream),
            patch("backend.sprint.phase_b.graph.get_ai_service", return_value=object()),
            patch.object(self.manager, "send_event", wrapped_send_event),
        ):
            asyncio.run(sprint_api.stream_peer_tts(session.session_id))

        pending_events = self.manager.get_session(session.session_id).pending_events
        self.assertEqual(
            [event["type"] for event in pending_events],
            ["tts_start", "audio_chunk"],
        )


if __name__ == "__main__":
    unittest.main()
