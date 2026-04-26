import unittest
from tempfile import NamedTemporaryFile
from unittest.mock import AsyncMock, patch

from backend.shared.ai.settings import AISettings
from backend.sprint.phase_b.imentiv import analyze_audio, analyze_video


class PhaseBAudioImentivTests(unittest.IsolatedAsyncioTestCase):
    async def test_analyze_audio_uses_uploaded_audio_asset(self) -> None:
        settings = AISettings(
            elevenlabs_api_key="test-elevenlabs",
            imentiv_api_key="test-imentiv",
        )
        analysis = {"audio_id": "audio-1", "audio_emotions": [], "text_emotions": []}

        with patch(
            "backend.sprint.phase_b.imentiv.analyze_audio_file",
            new=AsyncMock(return_value=analysis),
        ) as analyze_file_mock:
            with NamedTemporaryFile(suffix=".webm") as source:
                result = await analyze_audio(
                    settings,
                    source.name,
                    title="phase-b-test",
                    description="Phase B conversation turn tone and transcript analysis.",
                )

        self.assertEqual(result, analysis)
        analyze_file_mock.assert_awaited_once()

    async def test_analyze_video_alias_routes_to_audio_analysis(self) -> None:
        settings = AISettings(
            elevenlabs_api_key="test-elevenlabs",
            imentiv_api_key="test-imentiv",
        )

        with patch(
            "backend.sprint.phase_b.imentiv.analyze_audio",
            new=AsyncMock(return_value={"audio_id": "audio-2"}),
        ) as analyze_audio_mock:
            with NamedTemporaryFile(suffix=".webm") as source:
                result = await analyze_video(
                    settings,
                    source.name,
                    title="phase-b-test",
                    description="Phase B conversation turn tone and transcript analysis.",
                )

        self.assertEqual(result["audio_id"], "audio-2")
        analyze_audio_mock.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
