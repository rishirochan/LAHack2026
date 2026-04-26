import os
import unittest
from importlib.util import find_spec
from unittest.mock import patch


def _set_required_env() -> None:
    os.environ["OPENROUTER_API_KEY"] = "test-openrouter-key"
    os.environ["OPENROUTER_MODEL_GEMMA"] = "test/gemma"
    os.environ["ELEVENLABS_API_KEY"] = "test-elevenlabs-key"
    os.environ["ELEVENLABS_DEFAULT_VOICE_ID"] = "voice-test"
    os.environ["ELEVENLABS_STT_MODEL"] = "scribe_v1"
    os.environ["IMENTIV_API_KEY"] = "test-imentiv-key"


class AISetupSmokeTests(unittest.TestCase):
    def setUp(self) -> None:
        if not _dependencies_available():
            self.skipTest("AI dependencies not installed in current Python environment.")

        from backend.shared.ai.service import get_ai_service
        from backend.shared.ai.settings import get_settings

        self.get_ai_service = get_ai_service
        self.get_settings = get_settings

        _set_required_env()
        self.get_settings.cache_clear()
        self.get_ai_service.cache_clear()

    def tearDown(self) -> None:
        if hasattr(self, "get_settings"):
            self.get_settings.cache_clear()
        if hasattr(self, "get_ai_service"):
            self.get_ai_service.cache_clear()

    def test_validate_settings_with_required_environment(self) -> None:
        from backend.shared.ai.settings import validate_settings

        settings = validate_settings()
        self.assertEqual(settings.openrouter_model_gemma, "test/gemma")
        self.assertEqual(settings.google_ai_api_key, "")
        self.assertEqual(settings.elevenlabs_stt_model, "scribe_v1")

    @patch("backend.shared.ai.service.create_elevenlabs_client", return_value=object())
    @patch("backend.shared.ai.service.create_gemma_model", return_value=object())
    def test_ai_service_facade_initializes(
        self,
        _mock_gemma,
        _mock_elevenlabs,
    ) -> None:
        service = self.get_ai_service()
        self.assertIsNotNone(service.gemma_model)
        self.assertIsNotNone(service.elevenlabs_client)


def _dependencies_available() -> bool:
    return all(
        find_spec(module_name) is not None
        for module_name in ("langchain_openai", "elevenlabs")
    )


if __name__ == "__main__":
    unittest.main()
