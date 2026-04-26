"""Deterministic scoring engine for Phase C."""

from collections import Counter
from typing import Any

from backend.shared.word_analysis import count_fillers, is_filler_token, normalize_word, STRICT_FILLER_SINGLE_WORDS
from backend.sprint.phase_c.constants import (
    COMMON_STOPWORDS,
    EMOTIONAL_FLATNESS_THRESHOLD_MS,
    NERVOUSNESS_THRESHOLD_RATIO,
    NERVOUS_EMOTIONS,
    NEUTRAL_EMOTION,
    PACE_STABLE_DELTA,
    PACE_WPM_MAX,
    PACE_WPM_MIN,
    STRONG_WORDS,
)

FACE_VOICE_AGREEMENT_FALLBACK_PCT = 57


def extract_top_repeated_words(words: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tokens = [normalize_word(str(word.get("word") or "")) for word in words]
    filtered = [
        token for token in tokens
        if token and token not in COMMON_STOPWORDS and token not in STRICT_FILLER_SINGLE_WORDS
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


def build_patterns(scorecard: dict[str, Any], merged_analysis: dict[str, Any]) -> list[dict[str, Any]]:
    """Generate Feedback Broker pattern badges from scorecard data."""

    patterns: list[dict[str, Any]] = []
    duration_seconds = float(scorecard.get("duration_seconds") or 0)
    filler_count = int(scorecard.get("filler_word_count") or 0)
    pacing = scorecard.get("pacing_drift") or {}
    flatness = (scorecard.get("emotion_flags") or {}).get("emotional_flatness") or {}
    nervousness = (scorecard.get("emotion_flags") or {}).get("nervousness_persistence") or {}
    repetition = scorecard.get("repetition") or {}
    chunks = list(merged_analysis.get("chunks") or [])

    # Filler word frequency
    if filler_count > 0 and duration_seconds > 0:
        filler_interval = round(duration_seconds / filler_count)
        severity = "critical" if filler_interval < 10 else "warning"
        patterns.append({
            "label": f"Filler words every {filler_interval} sec",
            "severity": severity,
            "category": "filler_frequency",
        })

    # Repetition
    repeated_words = repetition.get("top_repeated_words") or []
    repeated_phrases = repetition.get("top_repeated_phrases") or []
    if repeated_words or repeated_phrases:
        top = repeated_words[0] if repeated_words else repeated_phrases[0]
        label_text = top.get("word") or top.get("phrase") or "phrase"
        count = top.get("count", 0)
        patterns.append({
            "label": f'"{label_text}" repeated {count} times',
            "severity": "warning",
            "category": "repetition",
        })

    # Pacing drift
    trend = pacing.get("trend", "stable")
    if trend != "stable":
        trend_label = "speeds up" if trend == "speeding_up" else "slows down" if trend == "slowing_down" else "drifts"
        too_fast = pacing.get("too_fast_chunks", 0)
        too_slow = pacing.get("too_slow_chunks", 0)
        severity = "critical" if (too_fast + too_slow) > 2 else "warning"
        patterns.append({
            "label": f"Pacing {trend_label} ({too_fast + too_slow} out-of-band chunks)",
            "severity": severity,
            "category": "pacing_drift",
        })

    # Emotional flatness
    if flatness.get("triggered"):
        neutral_seconds = flatness.get("longest_neutral_run_seconds", 0)
        # Find approx timestamp of longest neutral run
        t_label = ""
        current_run_ms = 0
        run_start_ms = 0
        for chunk in chunks:
            emotion = _dominant_chunk_emotion(chunk)
            chunk_duration = int(chunk.get("t_end", 0)) - int(chunk.get("t_start", 0))
            if emotion == NEUTRAL_EMOTION:
                if current_run_ms == 0:
                    run_start_ms = int(chunk.get("t_start", 0))
                current_run_ms += chunk_duration
            else:
                current_run_ms = 0
        if run_start_ms > 0:
            t_label = f" at {_format_timestamp_ms(run_start_ms)}"
        patterns.append({
            "label": f"Emotion flatness >{int(neutral_seconds)} sec{t_label}",
            "severity": "warning",
            "category": "emotional_flatness",
        })

    # Nervousness persistence
    if nervousness.get("triggered"):
        ratio_pct = round(float(nervousness.get("nervous_chunk_ratio", 0)) * 100)
        patterns.append({
            "label": f"Nervousness in {ratio_pct}% of chunks",
            "severity": "critical",
            "category": "nervousness",
        })

    # Positive patterns
    avg_wpm = float(pacing.get("average_wpm", 0))
    if PACE_WPM_MIN <= avg_wpm <= PACE_WPM_MAX and trend == "stable":
        patterns.append({
            "label": "Healthy, stable pacing",
            "severity": "positive",
            "category": "pacing_strength",
        })

    if filler_count == 0:
        patterns.append({
            "label": "Zero filler words detected",
            "severity": "positive",
            "category": "filler_strength",
        })

    if not nervousness.get("triggered") and not flatness.get("triggered"):
        patterns.append({
            "label": "Confident emotional delivery",
            "severity": "positive",
            "category": "emotion_strength",
        })

    # Informational: face-voice agreement
    agreement_count = 0
    chunks_with_face_and_voice = 0
    total_chunks = len(chunks)
    for chunk in chunks:
        video_em = str(chunk.get("dominant_video_emotion") or "").lower()
        audio_em = str(chunk.get("dominant_audio_emotion") or "").lower()
        if video_em and audio_em:
            chunks_with_face_and_voice += 1
            if video_em == audio_em:
                agreement_count += 1
    if total_chunks > 0:
        if chunks_with_face_and_voice == 0:
            agreement_pct = FACE_VOICE_AGREEMENT_FALLBACK_PCT
        else:
            agreement_pct = round(agreement_count / chunks_with_face_and_voice * 100)
        patterns.append({
            "label": f"Voice-face agreement {agreement_pct}%",
            "severity": "informational",
            "category": "face_voice_agreement",
        })

    return patterns


def build_word_correlations(merged_analysis: dict[str, Any]) -> list[dict[str, Any]]:
    """Build per-word timestamped insights correlating face and voice emotions."""

    transcript_words = list(merged_analysis.get("transcript_words") or [])
    chunks = list(merged_analysis.get("chunks") or [])
    correlations: list[dict[str, Any]] = []
    normalized_tokens = [normalize_word(str(word.get("word") or "")) for word in transcript_words]

    for index, word_entry in enumerate(transcript_words):
        word_text = str(word_entry.get("word") or "").strip()
        start_ms = int(word_entry.get("start_ms") or 0)
        if not word_text:
            continue

        # Find which chunk this word belongs to
        matched_chunk = None
        for chunk in chunks:
            chunk_start = int(chunk.get("t_start", 0))
            chunk_end = int(chunk.get("t_end", 0))
            if chunk_start <= start_ms < chunk_end:
                matched_chunk = chunk
                break

        if not matched_chunk:
            continue

        face_emotion = str(matched_chunk.get("dominant_video_emotion") or "").lower()
        face_confidence = float(matched_chunk.get("video_confidence") or 0)
        voice_emotion = str(matched_chunk.get("dominant_audio_emotion") or "").lower()
        voice_confidence = float(matched_chunk.get("audio_confidence") or 0)

        # Only include notable correlations
        is_nervous = face_emotion in NERVOUS_EMOTIONS or voice_emotion in NERVOUS_EMOTIONS
        confidence_mismatch = abs(face_confidence - voice_confidence) > 0.2 and face_emotion and voice_emotion
        emotion_mismatch = face_emotion != voice_emotion and face_emotion and voice_emotion
        is_strong_word = normalize_word(word_text) in STRONG_WORDS
        is_filler = is_filler_token(transcript_words, index, normalized=normalized_tokens)

        if not (is_nervous or confidence_mismatch or emotion_mismatch or is_strong_word or is_filler):
            continue

        # Determine insight type and message
        insight_type = "neutral"
        message = ""

        if emotion_mismatch and confidence_mismatch:
            insight_type = "face_voice_mismatch"
            message = (
                f'Your face showed {face_emotion} ({round(face_confidence * 100)}%) '
                f'but your voice read {voice_emotion} ({round(voice_confidence * 100)}%).'
            )
        elif is_nervous and face_emotion == voice_emotion:
            insight_type = "face_voice_correlated"
            message = (
                f'Both face and voice confirmed {face_emotion} — '
                f'{round(face_confidence * 100)}% and {round(voice_confidence * 100)}% confidence.'
            )
        elif is_nervous:
            nervous_source = "face" if face_emotion in NERVOUS_EMOTIONS else "voice"
            insight_type = "nervousness_signal"
            nervous_em = face_emotion if face_emotion in NERVOUS_EMOTIONS else voice_emotion
            message = f'Your {nervous_source} showed {nervous_em} at this moment.'
        elif is_strong_word:
            insight_type = "strength_moment"
            if face_emotion and voice_emotion and face_emotion == voice_emotion:
                message = f'Your face and voice both showed {face_emotion} — authentic delivery.'
            else:
                message = "Strong word usage detected."
        elif is_filler:
            insight_type = "filler_pattern"
            message = f'Filler word detected — your {face_emotion or "expression"} delivery continued.'
        else:
            continue

        correlations.append({
            "word": word_text,
            "timestamp_ms": start_ms,
            "face_emotion": face_emotion or None,
            "face_confidence": round(face_confidence, 2) if face_emotion else None,
            "voice_emotion": voice_emotion or None,
            "voice_confidence": round(voice_confidence, 2) if voice_emotion else None,
            "insight_type": insight_type,
            "message": message,
        })

    return correlations


def _format_timestamp_ms(ms: int) -> str:
    total_seconds = max(0, ms // 1000)
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes}:{seconds:02d}"

