"""Gemma summary helper for Phase C."""

from langchain_core.messages import HumanMessage, SystemMessage

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
    model = ai_service.gemma_model
    if model is None:
        raise RuntimeError(
            "Gemma model is not configured. "
            "Set OPENROUTER_API_KEY and OPENROUTER_MODEL_GEMMA in .env."
        )

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=f"Scorecard JSON:\n{scorecard_json}"),
    ]
    response = await model.ainvoke(messages, temperature=0.3, max_tokens=220)
    text = str(response.content).strip()
    if not text:
        raise RuntimeError("Gemma returned an empty response.")
    return text
