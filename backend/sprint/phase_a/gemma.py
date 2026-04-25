"""Gemma prompt helpers for Phase A."""

import asyncio
import json
import urllib.error
import urllib.request

from backend.shared.ai.settings import AISettings


GENERATE_CONTENT_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
)


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
    """Call the Google Generative Language API without adding another SDK."""

    return await asyncio.to_thread(_generate_text_sync, settings, prompt)


def _generate_text_sync(settings: AISettings, prompt: str) -> str:
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt}],
            }
        ],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 256,
        },
    }
    data = json.dumps(payload).encode("utf-8")
    url = GENERATE_CONTENT_URL.format(
        model=settings.google_gemma_model,
        key=settings.google_ai_api_key,
    )
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Gemma request failed: {detail}") from error

    candidates = body.get("candidates") or []
    if not candidates:
        raise RuntimeError("Gemma returned no candidates.")

    parts = candidates[0].get("content", {}).get("parts") or []
    text = "".join(part.get("text", "") for part in parts).strip()
    if not text:
        raise RuntimeError("Gemma returned an empty response.")
    return text

