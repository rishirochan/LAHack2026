"""OpenRouter-backed LLM constructors."""

from langchain_openai import ChatOpenAI

from backend.shared.ai.settings import AISettings


def create_openrouter_chat_model(settings: AISettings, model_name: str) -> ChatOpenAI:
    """Build a chat model routed through OpenRouter."""
    return ChatOpenAI(
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
        model=model_name,
    )


def create_gemma_model(settings: AISettings) -> ChatOpenAI:
    """Build the default Gemma model client."""
    return create_openrouter_chat_model(settings, settings.openrouter_model_gemma)
