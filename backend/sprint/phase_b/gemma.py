"""Gemma 4 (via OpenRouter) helpers for Phase B conversations."""

from langchain_core.messages import HumanMessage, SystemMessage

from backend.shared.ai.service import AIServiceFacade


async def generate_text(
    *,
    ai_service: AIServiceFacade,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.7,
    max_tokens: int = 512,
) -> str:
    """Send a system + user prompt to Gemma via OpenRouter and return text."""

    model = ai_service.gemma_model
    if model is None:
        raise RuntimeError(
            "Gemma model is not configured. "
            "Set OPENROUTER_API_KEY and OPENROUTER_MODEL_GEMMA in .env."
        )

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]

    response = await model.ainvoke(
        messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    text = str(response.content).strip()
    if not text:
        raise RuntimeError("Gemma returned an empty response.")
    return text
