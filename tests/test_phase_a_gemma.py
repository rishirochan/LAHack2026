import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import patch


class _FakeGenerateContentAPI:
    def __init__(self, response):
        self._response = response

    async def generate_content(self, *, model: str, contents: str):
        return self._response


class _FakeClient:
    def __init__(self, response):
        self.aio = SimpleNamespace(
            models=_FakeGenerateContentAPI(response),
        )


class PhaseAGemmaTests(unittest.TestCase):
    def test_generate_text_uses_google_gemma_model(self) -> None:
        from backend.sprint.phase_a.gemma import _generate_text

        settings = SimpleNamespace(
            google_api_key="test-google-key",
            google_gemma_model="test-gemma-model",
        )

        fake_response = SimpleNamespace(text="scenario text")
        with patch("backend.sprint.phase_a.gemma.create_gemma_client", return_value=_FakeClient(fake_response)):
            result = asyncio.run(_generate_text(settings=settings, prompt="hello"))

        self.assertEqual(result, "scenario text")

    def test_generate_text_rejects_empty_response(self) -> None:
        from backend.sprint.phase_a.gemma import _generate_text

        settings = SimpleNamespace(
            google_api_key="test-google-key",
            google_gemma_model="test-gemma-model",
        )

        fake_response = SimpleNamespace(text="")
        with patch("backend.sprint.phase_a.gemma.create_gemma_client", return_value=_FakeClient(fake_response)):
            with self.assertRaisesRegex(RuntimeError, "empty response"):
                asyncio.run(_generate_text(settings=settings, prompt="hello"))


if __name__ == "__main__":
    unittest.main()
