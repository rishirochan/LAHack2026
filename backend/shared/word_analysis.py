"""Shared word-level analysis utilities used by Phase A and Phase C."""

from collections import Counter
from typing import Any


FILLER_WORDS = ("um", "uh", "like", "you know", "basically", "literally")
FILLER_SINGLE_WORDS = {w for w in FILLER_WORDS if " " not in w}
FILLER_MULTI_WORDS = tuple(w for w in FILLER_WORDS if " " in w)


def normalize_word(word: str) -> str:
    return word.strip().lower().strip(".,!?;:\"'()[]{}")


def count_fillers(words: list[dict[str, Any]]) -> tuple[int, dict[str, int]]:
    """Count filler words using greedy multi-word-first matching.

    Returns (total_count, breakdown_dict) where breakdown_dict maps each
    filler to its occurrence count.
    """
    normalized = [normalize_word(str(word.get("word") or "")) for word in words]
    breakdown: Counter[str] = Counter()
    index = 0
    while index < len(normalized):
        token = normalized[index]
        matched = False
        for filler in FILLER_MULTI_WORDS:
            filler_tokens = filler.split()
            if normalized[index : index + len(filler_tokens)] == filler_tokens:
                breakdown[filler] += 1
                index += len(filler_tokens)
                matched = True
                break
        if matched:
            continue
        if token in FILLER_SINGLE_WORDS:
            breakdown[token] += 1
        index += 1
    return sum(breakdown.values()), dict(breakdown)
