"""Provider constructors for external AI services."""

from backend.shared.ai.providers.elevenlabs import (
    create_elevenlabs_client,
    get_default_voice_id,
    get_stt_model_name,
)
from backend.shared.ai.providers.openrouter import (
    create_gemma_model,
    create_haiku_model,
    create_openrouter_chat_model,
)

__all__ = [
    "create_elevenlabs_client",
    "create_gemma_model",
    "create_haiku_model",
    "create_openrouter_chat_model",
    "get_default_voice_id",
    "get_stt_model_name",
]
