"""Shared word-level analysis utilities used by Phase A and Phase C."""

from collections import Counter
from typing import Any


STRICT_FILLER_WORDS = ("um", "uh")
STRICT_FILLER_SINGLE_WORDS = {w for w in STRICT_FILLER_WORDS if " " not in w}
CONTEXTUAL_FILLER_WORDS = ("like", "so", "actually", "basically", "literally")
MULTI_WORD_FILLERS = ("you know", "i would say", "sort of")
FILLER_WORDS = STRICT_FILLER_WORDS + CONTEXTUAL_FILLER_WORDS + MULTI_WORD_FILLERS
FILLER_SINGLE_WORDS = {w for w in FILLER_WORDS if " " not in w}
FILLER_MULTI_WORDS = tuple(w for w in FILLER_WORDS if " " in w)
PAUSE_FILLER_THRESHOLD_MS = 250


def normalize_word(word: str) -> str:
    return word.strip().lower().strip(".,!?;:\"'()[]{}")


def count_fillers(words: list[dict[str, Any]]) -> tuple[int, dict[str, int]]:
    """Count filler words using greedy multi-word-first matching.

    Strict fillers like "um" are always counted. Context-sensitive tokens
    like "like" are only counted when their local punctuation/timing suggests
    they functioned as discourse filler rather than carrying meaning.

    Returns (total_count, breakdown_dict) where breakdown_dict maps each
    filler to its occurrence count.
    """
    normalized = [normalize_word(str(word.get("word") or "")) for word in words]
    breakdown: Counter[str] = Counter()
    index = 0
    while index < len(normalized):
        token = normalized[index]
        matched = False
        for filler in MULTI_WORD_FILLERS:
            filler_tokens = filler.split()
            if normalized[index : index + len(filler_tokens)] == filler_tokens:
                breakdown[filler] += 1
                index += len(filler_tokens)
                matched = True
                break
        if matched:
            continue
        if is_filler_token(words, index, normalized=normalized):
            breakdown[token] += 1
        index += 1
    return sum(breakdown.values()), dict(breakdown)


def is_filler_token(
    words: list[dict[str, Any]],
    index: int,
    *,
    normalized: list[str] | None = None,
) -> bool:
    if index < 0 or index >= len(words):
        return False

    normalized_tokens = normalized or [normalize_word(str(word.get("word") or "")) for word in words]
    token = normalized_tokens[index]
    if token in STRICT_FILLER_SINGLE_WORDS:
        return True
    if token in CONTEXTUAL_FILLER_WORDS:
        return _looks_like_contextual_filler(words, normalized_tokens, index)
    return False


def _looks_like_contextual_filler(
    words: list[dict[str, Any]],
    normalized: list[str],
    index: int,
) -> bool:
    token = normalized[index]
    raw = str(words[index].get("word") or "").strip()
    prev_raw = str(words[index - 1].get("word") or "").strip() if index > 0 else ""
    prev_prev_raw = str(words[index - 2].get("word") or "").strip() if index > 1 else ""
    next_raw = str(words[index + 1].get("word") or "").strip() if index + 1 < len(words) else ""

    comma_neighbor = any(raw_word.endswith(",") for raw_word in (prev_prev_raw, prev_raw, raw))
    sentence_opener = index == 0 or prev_raw.endswith((".", "!", "?"))
    pause_before_ms = _pause_before_ms(words, index)
    pause_after_ms = _pause_after_ms(words, index)
    sandwiched_pause = pause_before_ms >= PAUSE_FILLER_THRESHOLD_MS and pause_after_ms >= PAUSE_FILLER_THRESHOLD_MS
    opener_pause = sentence_opener and pause_after_ms >= PAUSE_FILLER_THRESHOLD_MS

    if token == "like":
        return comma_neighbor or sandwiched_pause
    if token in {"actually", "basically", "literally"}:
        return comma_neighbor or opener_pause
    if token == "so":
        return sentence_opener and (comma_neighbor or opener_pause or sandwiched_pause)
    return False


def _pause_before_ms(words: list[dict[str, Any]], index: int) -> int:
    if index <= 0:
        return 0
    start_ms = _word_start_ms(words[index])
    prev_end_ms = _word_end_ms(words[index - 1])
    if start_ms is None or prev_end_ms is None:
        return 0
    return max(0, start_ms - prev_end_ms)


def _pause_after_ms(words: list[dict[str, Any]], index: int) -> int:
    if index + 1 >= len(words):
        return 0
    end_ms = _word_end_ms(words[index])
    next_start_ms = _word_start_ms(words[index + 1])
    if end_ms is None or next_start_ms is None:
        return 0
    return max(0, next_start_ms - end_ms)


def _word_start_ms(word: dict[str, Any]) -> int | None:
    if word.get("start_ms") is not None:
        return int(float(word["start_ms"]))
    if word.get("start") is not None:
        return int(float(word["start"]) * 1000)
    return None


def _word_end_ms(word: dict[str, Any]) -> int | None:
    if word.get("end_ms") is not None:
        return int(float(word["end_ms"]))
    if word.get("end") is not None:
        return int(float(word["end"]) * 1000)
    return None
