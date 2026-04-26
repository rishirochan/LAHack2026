"""Lazy provider exports for external AI services."""

from importlib import import_module
from typing import Any

__all__ = [
    "create_elevenlabs_client",
    "create_gemma_client",
    "extract_text",
    "generate_gemma_text",
    "get_default_voice_id",
    "get_stt_model_name",
]


def __getattr__(name: str) -> Any:
    if name in {"create_elevenlabs_client", "get_default_voice_id", "get_stt_model_name"}:
        module = import_module("backend.shared.ai.providers.elevenlabs")
        return getattr(module, name)

    if name in {"create_gemma_client", "extract_text", "generate_gemma_text"}:
        module = import_module("backend.shared.ai.providers.google_genai")
        return getattr(module, name)

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
