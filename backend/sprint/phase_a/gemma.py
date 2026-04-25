"""Gemma prompt helpers for Phase A."""

import json
import logging
from typing import Any

from ...shared.ai.providers.openrouter import create_gemma_model
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
    """Call Gemma through the shared OpenRouter model client."""

    if not settings.openrouter_api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not configured for Gemma requests.")

    model = create_gemma_model(settings)
    try:
        response = await model.ainvoke(prompt)
    except Exception as error:
        logger.exception(
            "OpenRouter Gemma request failed for model %s.",
            settings.openrouter_model_gemma,
        )
        raise RuntimeError(f"OpenRouter Gemma request failed: {error}") from error

    text = _extract_text(getattr(response, "content", response))
    if not text:
        logger.error(
            "OpenRouter Gemma returned an empty response for model %s.",
            settings.openrouter_model_gemma,
        )
        raise RuntimeError("OpenRouter Gemma returned an empty response.")
    return text


def _extract_text(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
                continue
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts).strip()

    return str(content).strip() if content is not None else ""

