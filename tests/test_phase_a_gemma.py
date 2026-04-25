import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import patch


class _FakeModel:
    def __init__(self, content):
        self._content = content

    async def ainvoke(self, _prompt: str):
        return SimpleNamespace(content=self._content)


class PhaseAGemmaTests(unittest.TestCase):
    def test_generate_text_uses_openrouter_model(self) -> None:
        from backend.sprint.phase_a.gemma import _generate_text

        settings = SimpleNamespace(
            openrouter_api_key="test-openrouter-key",
            openrouter_model_gemma="test/gemma",
        )

        with patch("backend.sprint.phase_a.gemma.create_gemma_model", return_value=_FakeModel("scenario text")):
            result = asyncio.run(_generate_text(settings=settings, prompt="hello"))

        self.assertEqual(result, "scenario text")

    def test_generate_text_rejects_empty_response(self) -> None:
        from backend.sprint.phase_a.gemma import _generate_text

        settings = SimpleNamespace(
            openrouter_api_key="test-openrouter-key",
            openrouter_model_gemma="test/gemma",
        )

        with patch("backend.sprint.phase_a.gemma.create_gemma_model", return_value=_FakeModel("")):
            with self.assertRaisesRegex(RuntimeError, "empty response"):
                asyncio.run(_generate_text(settings=settings, prompt="hello"))


if __name__ == "__main__":
    unittest.main()
