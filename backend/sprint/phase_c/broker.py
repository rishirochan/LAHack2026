"""Deterministic scoring engine for Phase C."""

from collections import Counter
from typing import Any

from backend.sprint.phase_c.constants import (
    COMMON_STOPWORDS,
    EMOTIONAL_FLATNESS_THRESHOLD_MS,
    FILLER_MULTI_WORDS,
    FILLER_SINGLE_WORDS,
    NERVOUSNESS_THRESHOLD_RATIO,
    NERVOUS_EMOTIONS,
    NEUTRAL_EMOTION,
    PACE_STABLE_DELTA,
    PACE_WPM_MAX,
    PACE_WPM_MIN,
)


def normalize_word(word: str) -> str:
    return word.strip().lower().strip(".,!?;:\"'()[]{}")


def count_fillers(words: list[dict[str, Any]]) -> tuple[int, dict[str, int]]:
    normalized = [normalize_word(str(word.get("word") or "")) for word in words]
    breakdown: Counter[str] = Counter()
    index = 0
    while index < len(normalized):
        token = normalized[index]
        matched = False
        for filler in FILLER_MULTI_WORDS:
            filler_tokens = filler.split()
            if normalized[index:index + len(filler_tokens)] == filler_tokens:
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


def extract_top_repeated_words(words: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tokens = [normalize_word(str(word.get("word") or "")) for word in words]
    filtered = [
        token for token in tokens
        if token and token not in COMMON_STOPWORDS and token not in FILLER_SINGLE_WORDS
    ]
    counter = Counter(filtered)
    ordered = sorted(counter.items(), key=lambda item: (-item[1], filtered.index(item[0])))
    return [{"word": word, "count": count} for word, count in ordered if count > 1][:3]


def extract_top_repeated_phrases(words: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tokens = [normalize_word(str(word.get("word") or "")) for word in words]
    tokens = [token for token in tokens if token]
    phrases: list[str] = []
    for size in (2, 3):
        for index in range(len(tokens) - size + 1):
            phrase_tokens = tokens[index:index + size]
            if any(token in COMMON_STOPWORDS for token in phrase_tokens):
                continue
            phrases.append(" ".join(phrase_tokens))
    counter = Counter(phrases)
    ordered = sorted(counter.items(), key=lambda item: (-item[1], phrases.index(item[0])))
    return [{"phrase": phrase, "count": count} for phrase, count in ordered if count > 1][:3]


def compute_chunk_wpms(chunks: list[dict[str, Any]], transcript_words: list[dict[str, Any]]) -> list[dict[str, Any]]:
    chunk_wpms: list[dict[str, Any]] = []
    for chunk in chunks:
        duration_ms = max(int(chunk["t_end"]) - int(chunk["t_start"]), 1)
        words_in_chunk = [
            word for word in transcript_words
            if int(word.get("start_ms") or 0) >= int(chunk["t_start"]) and int(word.get("start_ms") or 0) < int(chunk["t_end"])
        ]
        wpm = round(len(words_in_chunk) / (duration_ms / 60000), 1)
        chunk_wpms.append({
            "chunk_index": chunk.get("chunk_index"),
            "t_start": chunk["t_start"],
            "t_end": chunk["t_end"],
            "word_count": len(words_in_chunk),
            "wpm": wpm,
        })
    return chunk_wpms


def classify_pacing_drift(chunk_wpms: list[dict[str, Any]]) -> dict[str, Any]:
    values = [float(item["wpm"]) for item in chunk_wpms]
    if not values:
        return {
            "average_wpm": 0,
            "target_band": [PACE_WPM_MIN, PACE_WPM_MAX],
            "too_fast_chunks": 0,
            "too_slow_chunks": 0,
            "trend": "stable",
        }

    third = max(len(values) // 3, 1)
    early = sum(values[:third]) / len(values[:third])
    late = sum(values[-third:]) / len(values[-third:])
    delta = late - early
    if abs(delta) <= PACE_STABLE_DELTA:
        trend = "stable"
    elif delta > 0:
        trend = "speeding_up"
    elif delta < 0:
        trend = "slowing_down"
    else:
        trend = "mixed"

    return {
        "average_wpm": round(sum(values) / len(values), 1),
        "target_band": [PACE_WPM_MIN, PACE_WPM_MAX],
        "too_fast_chunks": sum(1 for value in values if value > PACE_WPM_MAX),
        "too_slow_chunks": sum(1 for value in values if value < PACE_WPM_MIN),
        "trend": trend,
    }


def compute_flatness_flag(chunks: list[dict[str, Any]]) -> dict[str, Any]:
    longest_run_ms = 0
    current_run_ms = 0
    for chunk in chunks:
        emotion = _dominant_chunk_emotion(chunk)
        duration_ms = int(chunk["t_end"]) - int(chunk["t_start"])
        if emotion == NEUTRAL_EMOTION:
            current_run_ms += duration_ms
            longest_run_ms = max(longest_run_ms, current_run_ms)
        else:
            current_run_ms = 0
    return {
        "triggered": longest_run_ms > EMOTIONAL_FLATNESS_THRESHOLD_MS,
        "longest_neutral_run_seconds": round(longest_run_ms / 1000, 1),
    }


def compute_nervousness_flag(chunks: list[dict[str, Any]]) -> dict[str, Any]:
    valid = [_dominant_chunk_emotion(chunk) for chunk in chunks]
    valid = [emotion for emotion in valid if emotion is not None]
    if not valid:
        return {"triggered": False, "nervous_chunk_ratio": 0}
    nervous_ratio = sum(1 for emotion in valid if emotion in NERVOUS_EMOTIONS) / len(valid)
    return {
        "triggered": nervous_ratio > NERVOUSNESS_THRESHOLD_RATIO,
        "nervous_chunk_ratio": round(nervous_ratio, 2),
    }


def compute_overall_score(
    *,
    pacing: dict[str, Any],
    filler_word_count: int,
    repeated_words: list[dict[str, Any]],
    repeated_phrases: list[dict[str, Any]],
    flatness: dict[str, Any],
    nervousness: dict[str, Any],
    duration_seconds: float,
) -> int:
    score = 100
    if pacing["average_wpm"] < PACE_WPM_MIN or pacing["average_wpm"] > PACE_WPM_MAX:
        score -= 15
    score -= min((pacing["too_fast_chunks"] + pacing["too_slow_chunks"]) * 4, 15)
    if pacing["trend"] != "stable":
        score -= 8

    filler_rate = filler_word_count / max(duration_seconds / 60, 1 / 60)
    score -= min(round(filler_rate * 2), 20)

    repetition_penalty = sum(item["count"] - 1 for item in repeated_words) + sum(item["count"] - 1 for item in repeated_phrases)
    score -= min(repetition_penalty * 2, 20)

    if flatness["triggered"]:
        score -= 12
    if nervousness["triggered"]:
        score -= 10

    return max(0, min(100, int(round(score))))


def derive_strengths(
    *,
    pacing: dict[str, Any],
    filler_word_count: int,
    flatness: dict[str, Any],
    nervousness: dict[str, Any],
) -> list[str]:
    strengths: list[str] = []
    if PACE_WPM_MIN <= pacing["average_wpm"] <= PACE_WPM_MAX:
        strengths.append("Your pacing stayed in a healthy speaking range.")
    if filler_word_count == 0:
        strengths.append("You avoided filler words throughout the recording.")
    if not flatness["triggered"]:
        strengths.append("Your delivery avoided long stretches of emotional flatness.")
    if not nervousness["triggered"]:
        strengths.append("Nervousness did not dominate the session.")
    return strengths[:3] or ["You completed the session with enough data for a full analysis."]


def derive_improvement_areas(
    *,
    pacing: dict[str, Any],
    filler_word_count: int,
    repeated_words: list[dict[str, Any]],
    flatness: dict[str, Any],
    nervousness: dict[str, Any],
) -> list[str]:
    areas: list[str] = []
    if pacing["average_wpm"] < PACE_WPM_MIN:
        areas.append("Your pacing ran slower than the target band.")
    if pacing["average_wpm"] > PACE_WPM_MAX:
        areas.append("Your pacing ran faster than the target band.")
    if filler_word_count > 0:
        areas.append("Filler words appeared often enough to interrupt clarity.")
    if repeated_words:
        areas.append("A few repeated words or phrases reduced variety.")
    if flatness["triggered"]:
        areas.append("Neutral delivery lasted too long without enough variation.")
    if nervousness["triggered"]:
        areas.append("Nervous or fearful emotion dominated too many chunks.")
    return areas[:3]


def build_scorecard(merged_analysis: dict[str, Any]) -> dict[str, Any]:
    transcript_words = list(merged_analysis.get("transcript_words") or [])
    chunks = list(merged_analysis.get("chunks") or [])
    recording_duration_ms = int(merged_analysis.get("overall", {}).get("recording_duration_ms") or 0)
    duration_seconds = round(recording_duration_ms / 1000, 1)

    filler_word_count, filler_breakdown = count_fillers(transcript_words)
    repeated_words = extract_top_repeated_words(transcript_words)
    repeated_phrases = extract_top_repeated_phrases(transcript_words)
    chunk_wpms = compute_chunk_wpms(chunks, transcript_words)
    pacing = classify_pacing_drift(chunk_wpms)
    flatness = compute_flatness_flag(chunks)
    nervousness = compute_nervousness_flag(chunks)
    overall_score = compute_overall_score(
        pacing=pacing,
        filler_word_count=filler_word_count,
        repeated_words=repeated_words,
        repeated_phrases=repeated_phrases,
        flatness=flatness,
        nervousness=nervousness,
        duration_seconds=max(duration_seconds, 0.1),
    )

    return {
        "duration_seconds": duration_seconds,
        "transcript_word_count": len(transcript_words),
        "average_wpm": pacing["average_wpm"],
        "wpm_by_chunk": chunk_wpms,
        "pacing_drift": pacing,
        "filler_word_count": filler_word_count,
        "filler_word_breakdown": filler_breakdown,
        "repetition": {
            "top_repeated_words": repeated_words,
            "top_repeated_phrases": repeated_phrases,
        },
        "emotion_flags": {
            "emotional_flatness": flatness,
            "nervousness_persistence": nervousness,
        },
        "chunk_health": {
            "total_chunks": merged_analysis.get("overall", {}).get("total_chunks", 0),
            "done_chunks": merged_analysis.get("overall", {}).get("chunks_done", 0),
            "timed_out_chunks": merged_analysis.get("overall", {}).get("chunks_timed_out", 0),
            "failed_chunks": merged_analysis.get("overall", {}).get("chunks_failed", 0),
        },
        "overall_score": overall_score,
        "strengths": derive_strengths(
            pacing=pacing,
            filler_word_count=filler_word_count,
            flatness=flatness,
            nervousness=nervousness,
        ),
        "improvement_areas": derive_improvement_areas(
            pacing=pacing,
            filler_word_count=filler_word_count,
            repeated_words=repeated_words,
            flatness=flatness,
            nervousness=nervousness,
        ),
    }


def _dominant_chunk_emotion(chunk: dict[str, Any]) -> str | None:
    video = normalize_word(str(chunk.get("dominant_video_emotion") or ""))
    audio = normalize_word(str(chunk.get("dominant_audio_emotion") or ""))
    return video or audio or None
