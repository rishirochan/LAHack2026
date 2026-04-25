"""Shared AI integration entrypoints."""

from backend.shared.ai.service import AIServiceFacade, get_ai_service
from backend.shared.ai.settings import AISettings, get_settings, validate_settings

__all__ = [
    "AIServiceFacade",
    "AISettings",
    "get_ai_service",
    "get_settings",
    "validate_settings",
]
