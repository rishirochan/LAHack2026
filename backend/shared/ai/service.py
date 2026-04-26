"""Facade that exposes shared AI integration primitives."""

from functools import lru_cache

from backend.shared.ai.providers.elevenlabs import create_elevenlabs_client
from backend.shared.ai.providers.google_genai import create_gemma_client
from backend.shared.ai.settings import AISettings, get_settings


class AIServiceFacade:
    """Single import surface for AI clients used by backend modules."""

    def __init__(self, settings: AISettings):
        self.settings = settings
        self.gemma_client = create_gemma_client(settings) if settings.google_api_key else None
        self.elevenlabs_client = create_elevenlabs_client(settings)


@lru_cache
def get_ai_service() -> AIServiceFacade:
    """Build and cache the shared AI service facade."""
    return AIServiceFacade(settings=get_settings())
