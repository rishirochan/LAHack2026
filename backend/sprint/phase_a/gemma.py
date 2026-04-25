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
    theme: str,
    target_emotion: str,
    previous_critiques: list[str],
) -> str:
    """Ask Gemma for a short speaking scenario."""

    prompt = (
        "Generate exactly 2 sentences describing a realistic speaking scenario. "
        f"The theme is {theme}. The user should naturally practice sounding "
        f"{target_emotion}. Avoid repeating issues from these previous critiques: "
        f"{json.dumps(previous_critiques)}. Return only the scenario text."
    )
    return await _generate_text(settings=settings, prompt=prompt)


async def generate_coach_critique(
    *,
    settings: AISettings,
    theme: str,
    target_emotion: str,
    difficulty: int,
    merged_analysis: dict,
    previous_critiques: list[str],
) -> str:
    """Ask Gemma to critique the merged emotion/transcript analysis."""

    prompt = (
        "You are an expert communication coach. Return exactly 2 specific "
        "weaknesses and 1 specific strength in under 100 words because this will "
        "be spoken aloud. Reference timestamps and words from word_correlations "
        "where possible. Pay special attention to moments where face emotion and "
        "voice emotion diverge. If one stream is missing, only critique streams "
        "that have data.\n\n"
        f"Theme: {theme}\n"
        f"Target emotion: {target_emotion}\n"
        f"Difficulty from 1 to 10: {difficulty}\n"
        f"Previous critiques to avoid repeating: {json.dumps(previous_critiques)}\n"
        f"Merged analysis JSON: {json.dumps(merged_analysis, ensure_ascii=True)}"
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

