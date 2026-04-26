"""Gemma summary helper for Phase C."""

from backend.shared.ai.providers.google_genai import generate_gemma_text
from backend.shared.ai.service import AIServiceFacade


SYSTEM_PROMPT = """
You are a concise speaking coach.
You will receive a deterministic JSON scorecard for one freeform speaking session.
Do not invent any counts or metrics not present in the JSON.
Write exactly:
1. one strongest point
2. one main issue
3. one concrete next step
Keep it brief and practical.
""".strip()


async def generate_phase_c_summary(
    *,
    ai_service: AIServiceFacade,
    scorecard_json: str,
) -> str:
    client = ai_service.gemma_client
    if client is None:
        raise RuntimeError(
            "Gemma model is not configured. "
            "Set GOOGLE_API_KEY and GOOGLE_GEMMA_MODEL in .env."
        )

    return await generate_gemma_text(
        client=client,
        model_name=ai_service.settings.google_gemma_model,
        contents=f"Scorecard JSON:\n{scorecard_json}",
        system_instruction=SYSTEM_PROMPT,
        temperature=0.3,
        max_output_tokens=220,
    )
