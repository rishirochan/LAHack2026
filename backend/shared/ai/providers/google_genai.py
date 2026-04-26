"""Google GenAI-backed Gemma helpers."""

from collections.abc import Sequence
from typing import Any

from google import genai
from google.genai import types

from backend.shared.ai.settings import AISettings


def create_gemma_client(settings: AISettings) -> genai.Client:
    """Build the shared Google GenAI client."""
    return genai.Client(api_key=settings.google_api_key)


async def generate_gemma_text(
    *,
    client: genai.Client,
    model_name: str,
    contents: str,
    system_instruction: str | None = None,
    temperature: float | None = None,
    max_output_tokens: int | None = None,
) -> str:
    """Generate text from Gemma and normalize the returned content."""
    config_kwargs: dict[str, Any] = {}
    if system_instruction:
        config_kwargs["system_instruction"] = system_instruction
    if temperature is not None:
        config_kwargs["temperature"] = temperature
    if max_output_tokens is not None:
        config_kwargs["max_output_tokens"] = max_output_tokens

    config = types.GenerateContentConfig(**config_kwargs) if config_kwargs else None
    response = await client.aio.models.generate_content(
        model=model_name,
        contents=contents,
        config=config,
    )
    text = extract_text(response)
    if not text:
        raise RuntimeError("Gemma returned an empty response.")
    return text


def extract_text(response: Any) -> str:
    """Defensively extract text from a Google GenAI response."""
    text = getattr(response, "text", None)
    if isinstance(text, str) and text.strip():
        return text.strip()

    parts: list[str] = []
    for candidate in _sequence_or_empty(getattr(response, "candidates", None)):
        content = getattr(candidate, "content", None)
        if content is None:
            continue
        for part in _sequence_or_empty(getattr(content, "parts", None)):
            part_text = getattr(part, "text", None)
            if isinstance(part_text, str) and part_text.strip():
                parts.append(part_text.strip())

    return "\n".join(parts).strip()


def _sequence_or_empty(value: Any) -> Sequence[Any]:
    if isinstance(value, Sequence) and not isinstance(value, str | bytes):
        return value
    return ()
