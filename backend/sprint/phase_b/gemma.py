"""Gemma helpers for Phase B conversations."""

from backend.shared.ai.service import AIServiceFacade


async def generate_text(
    *,
    ai_service: AIServiceFacade,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.7,
    max_tokens: int = 512,
) -> str:
    """Send a system + user prompt to Gemma via Google GenAI and return text."""

    client = ai_service.gemma_client
    if client is None:
        raise RuntimeError(
            "Gemma model is not configured. "
            "Set GOOGLE_API_KEY and GOOGLE_GEMMA_MODEL in .env."
        )

    from backend.shared.ai.providers.google_genai import generate_gemma_text

    return await generate_gemma_text(
        client=client,
        model_name=ai_service.settings.google_gemma_model,
        contents=user_prompt,
        system_instruction=system_prompt,
        temperature=temperature,
        max_output_tokens=max_tokens,
    )
