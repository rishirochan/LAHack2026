import unittest
from contextlib import asynccontextmanager
from tempfile import NamedTemporaryFile
from unittest.mock import AsyncMock, patch

from backend.shared.ai.settings import AISettings
from backend.shared.imentiv import PreparedAnalysisVideo, prepare_analysis_video_source
from backend.sprint.phase_b.imentiv import analyze_video as analyze_phase_b_video


class ImentivPreprocessingTests(unittest.IsolatedAsyncioTestCase):
    async def test_prepare_analysis_video_source_skips_transcode_when_disabled(self) -> None:
        settings = AISettings(
            elevenlabs_api_key="test-elevenlabs",
            imentiv_api_key="test-imentiv",
            imentiv_analysis_downscale_enabled=False,
        )
        with NamedTemporaryFile(suffix=".webm") as source:
            prepared = await prepare_analysis_video_source(settings, source.name)

        self.assertEqual(prepared.path, source.name)
        self.assertEqual(prepared.cleanup_paths, ())

    async def test_prepare_analysis_video_source_requires_ffmpeg_when_enabled(self) -> None:
        settings = AISettings(
            elevenlabs_api_key="test-elevenlabs",
            imentiv_api_key="test-imentiv",
            imentiv_analysis_downscale_enabled=True,
        )
        with NamedTemporaryFile(suffix=".webm") as source:
            with patch("backend.shared.imentiv.shutil.which", return_value=None):
                with self.assertRaisesRegex(RuntimeError, "requires ffmpeg"):
                    await prepare_analysis_video_source(settings, source.name)


class PhaseBImentivFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_analyze_video_uses_prepared_analysis_asset(self) -> None:
        settings = AISettings(
            elevenlabs_api_key="test-elevenlabs",
            imentiv_api_key="test-imentiv",
            imentiv_analysis_downscale_enabled=True,
        )
        analysis = {"video_id": "video-1", "audio_id": "audio-1"}

        @asynccontextmanager
        async def fake_prepared_video(*_args, **_kwargs):
            yield PreparedAnalysisVideo(path="/tmp/analysis.mp4", cleanup_paths=("/tmp/analysis.mp4",))

        with (
            patch("backend.sprint.phase_b.imentiv.prepared_analysis_video", fake_prepared_video),
            patch(
                "backend.sprint.phase_b.imentiv.analyze_video_file",
                new=AsyncMock(return_value=analysis),
            ) as analyze_file_mock,
        ):
            result = await analyze_phase_b_video(
                settings,
                {"file_id": "video-file", "filename": "chunk.webm"},
                title="phase-b-test",
                description="Phase B conversation chunk analysis.",
            )

        self.assertEqual(result, analysis)
        analyze_file_mock.assert_awaited_once_with(
            settings,
            "/tmp/analysis.mp4",
            title="phase-b-test",
            description="Phase B conversation chunk analysis.",
        )


if __name__ == "__main__":
    unittest.main()
