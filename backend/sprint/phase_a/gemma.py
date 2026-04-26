"""Gemma prompt helpers for Phase A."""

import json
import logging

from ...shared.ai.settings import AISettings


logger = logging.getLogger(__name__)


async def generate_scenario_prompt(
    *,
    settings: AISettings,
    target_emotion: str,
    previous_critiques: list[str],
) -> str:
    """Ask Gemma for a short speaking scenario."""

    prompt = (
        "Generate exactly 2 sentences for the user to say thatgives them a natural opportunity to "
        f"practice expressing {target_emotion}. The prompt should encourage that "
        "emotion clearly without mentioning analysis, coaching, or acting drills. "
        f"Avoid repeating issues from these previous critiques: {json.dumps(previous_critiques)}. "
        "Return only the prompt text."
    )
    return await _generate_text(settings=settings, prompt=prompt)


async def generate_coach_critique(
    *,
    settings: AISettings,
    target_emotion: str,
    merged_analysis: dict,
    previous_critiques: list[str],
) -> str:
    """Ask Gemma to critique the merged emotion/transcript analysis."""

    raw_data = merged_analysis.get("raw_data", merged_analysis)
    derived_metrics = merged_analysis.get("derived_metrics", {})
    prompt = (
        "You are an expert communication coach. Explain what the measured signals "
        "mean for the user. Return exactly 2 specific weaknesses and 1 specific "
        "strength. Return well formatted text with markdown. Use both "
        "the raw evidence and the derived metrics. Treat overall_match_score, "
        "target_frame_ratio, average_target_confidence, emotion_stability_score, "
        "and face_voice_alignment_ratio as the primary indicators. Treat "
        "peak_match_score as a secondary signal only. You cna also reference the raw data for timestamps and words if needed and more context if needed. If the evidence is mixed, "
        "say that the performance was mixed instead of framing it as a total miss and mention which emotions they favored over the target emotion. "
        "For Neutrality (Neutral), interpret success as steady, low-drift delivery "
        "rather than a perfectly flat or empty expression. Reference timestamps "
        "and words when the data supports them. Pay special attention to moments "
        "where face emotion and voice emotion diverge. Focus on how well the user "
        "expressed the target emotion and what they can do better next time. If "
        "one stream is missing, only critique streams that have data. Do not "
        "invent findings that are not supported by the supplied evidence. When referencing things they said use quotes to indicate the exact words they used.\n\n"
        f"Target emotion: {target_emotion}\n"
        f"Previous critiques to avoid repeating: {json.dumps(previous_critiques)}\n"
        f"Raw evidence JSON: {json.dumps(raw_data, ensure_ascii=True)}\n"
        f"Derived metrics JSON: {json.dumps(derived_metrics, ensure_ascii=True)}"
    )
    return await _generate_text(settings=settings, prompt=prompt)


async def _generate_text(*, settings: AISettings, prompt: str) -> str:
    """Call Gemma through the shared Google GenAI client."""

    if not settings.google_api_key:
        raise RuntimeError("GOOGLE_API_KEY is not configured for Gemma requests.")

    from ...shared.ai.providers.google_genai import create_gemma_client, extract_text

    client = create_gemma_client(settings)
    try:
        response = await client.aio.models.generate_content(
            model=settings.google_gemma_model,
            contents=prompt,
        )
    except Exception as error:
        logger.exception(
            "Google GenAI Gemma request failed for model %s.",
            settings.google_gemma_model,
        )
        raise RuntimeError(f"Google GenAI Gemma request failed: {error}") from error

    text = extract_text(response)
    if not text:
        logger.error(
            "Google GenAI Gemma returned an empty response for model %s.",
            settings.google_gemma_model,
        )
        raise RuntimeError("Google GenAI Gemma returned an empty response.")
    return text
