"""LangGraph workflow for Phase A emotion drills."""

import asyncio
import logging
from typing import Any, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph

from backend.shared.ai import get_ai_service, get_settings
from backend.shared.db import get_session_repository
from backend.shared.db.tasks import schedule_repository_write
from backend.shared.word_analysis import count_fillers
from .elevenlabs import transcribe_audio as transcribe_elevenlabs
from .gemma import generate_coach_critique, generate_scenario_prompt
from .imentiv import analyze_video
from .session_manager import get_session_manager


MATCH_WINDOW_MS = 1000
TOP_MOMENTS_LIMIT = 3
logger = logging.getLogger(__name__)


class PhaseAState(TypedDict):
    """State carried through the Phase A LangGraph workflow."""

    target_emotion: str
    previous_critiques: list[str]
    scenario_prompt: str | None
    video_path: str | None
    audio_path: str | None
    video_upload: dict[str, Any] | None
    audio_upload: dict[str, Any] | None
    video_id: str | None
    audio_id: str | None
    imentiv_analysis: dict[str, Any]
    video_emotions: list[dict[str, Any]]
    audio_emotions: list[dict[str, Any]]
    transcript: str | None
    word_timestamps: list[dict[str, Any]]
    merged_analysis: dict[str, Any]
    word_correlations: list[dict[str, Any]]
    critique: str | None
    match_score: float
    continue_session: bool
    error: str | None


def build_initial_state(target_emotion: str) -> PhaseAState:
    """Create the nullable/default state for a new Phase A session."""

    return {
        "target_emotion": target_emotion,
        "previous_critiques": [],
        "scenario_prompt": None,
        "video_path": None,
        "audio_path": None,
        "video_upload": None,
        "audio_upload": None,
        "video_id": None,
        "audio_id": None,
        "imentiv_analysis": {},
        "video_emotions": [],
        "audio_emotions": [],
        "transcript": None,
        "word_timestamps": [],
        "merged_analysis": {},
        "word_correlations": [],
        "critique": None,
        "match_score": 0,
        "continue_session": False,
        "error": None,
    }


async def generate_scenario(state: PhaseAState, config: RunnableConfig) -> dict[str, Any]:
    try:
        scenario_prompt = await generate_scenario_prompt(
            settings=get_settings(),
            target_emotion=state["target_emotion"],
            previous_critiques=state["previous_critiques"],
        )
        await _send_event(config, "scenario", {"scenario_prompt": scenario_prompt})
        return {"scenario_prompt": scenario_prompt, "error": None}
    except Exception as error:
        logger.exception(
            "Failed to generate Phase A scenario for target_emotion=%s.",
            state["target_emotion"],
        )
        return {"error": f"Could not generate a scenario: {error}"}


async def await_recording(state: PhaseAState, config: RunnableConfig) -> dict[str, Any]:
    try:
        await _send_event(config, "recording_ready", {"max_seconds": 20})
        video_upload, audio_upload = await get_session_manager().wait_for_recording(_session_id(config))
        return {
            "video_path": None,
            "audio_path": None,
            "video_upload": video_upload,
            "audio_upload": audio_upload,
            "error": None,
        }
    except Exception as error:
        return {"error": f"Could not receive the recording: {error}"}


async def upload_to_imentiv(state: PhaseAState, config: RunnableConfig) -> dict[str, Any]:
    try:
        if not state["video_upload"]:
            raise RuntimeError("Video recording file was missing.")

        session_id = _session_id(config)
        await _send_event(config, "processing_stage", {"stage": "Uploading recording"})
        await _send_event(config, "processing_stage", {"stage": "Analyzing facial and vocal emotion"})
        analysis = await analyze_video(
            get_settings(),
            state["video_upload"],
            title=f"phase-a-{session_id}-round",
            description=f"Phase A emotion drill for {state['target_emotion']}.",
        )
        return {
            "video_id": analysis.get("video_id"),
            "audio_id": analysis.get("audio_id"),
            "imentiv_analysis": analysis,
            "video_emotions": analysis.get("video_emotions") if isinstance(analysis.get("video_emotions"), list) else [],
            "audio_emotions": analysis.get("audio_emotions") if isinstance(analysis.get("audio_emotions"), list) else [],
            "error": None,
        }
    except Exception as error:
        return {"error": f"Could not upload recording for emotion analysis: {error}"}


async def poll_imentiv_results(state: PhaseAState, config: RunnableConfig) -> dict[str, Any]:
    try:
        await _send_event(config, "processing_stage", {"stage": "Transcribing speech"})

        transcript_task = _soft_result(
            transcribe_elevenlabs(
                ai_service=get_ai_service(),
                audio_source=state["audio_upload"] or state["audio_path"] or "",
            )
        )
        transcript_result = await transcript_task

        transcript = ""
        word_timestamps: list[dict[str, Any]] = []
        if isinstance(transcript_result, tuple):
            transcript, word_timestamps = transcript_result
        else:
            logger.warning("Transcription returned non-tuple result (likely failed silently): %s", type(transcript_result))

        if not word_timestamps:
            logger.warning("No word timestamps returned from transcription.")

        return {
            "transcript": transcript,
            "word_timestamps": word_timestamps,
            "error": None,
        }
    except Exception as error:
        return {"error": f"Could not analyze the recording: {error}"}


async def transcribe_audio(state: PhaseAState, config: RunnableConfig) -> dict[str, Any]:
    try:
        await _send_event(config, "processing_stage", {"stage": "Transcribing speech"})
        transcript, word_timestamps = await transcribe_elevenlabs(
            ai_service=get_ai_service(),
            audio_source=state["audio_upload"] or state["audio_path"] or "",
        )
        return {"transcript": transcript, "word_timestamps": word_timestamps, "error": None}
    except Exception as error:
        return {"error": f"Could not transcribe the recording: {error}"}


async def merge_and_correlate(state: PhaseAState, config: RunnableConfig) -> dict[str, Any]:
    try:
        merged_analysis, word_correlations, match_score = build_merged_analysis(state)
        return {
            "merged_analysis": merged_analysis,
            "word_correlations": word_correlations,
            "match_score": match_score,
            "error": None,
        }
    except Exception as error:
        return {"error": f"Could not merge analysis results: {error}"}


async def generate_critique(state: PhaseAState, config: RunnableConfig) -> dict[str, Any]:
    try:
        await _send_event(config, "processing_stage", {"stage": "Generating critique"})
        critique = await generate_coach_critique(
            settings=get_settings(),
            target_emotion=state["target_emotion"],
            merged_analysis=state["merged_analysis"],
            previous_critiques=state["previous_critiques"],
        )
        round_state = {**state, "critique": critique}
        get_session_manager().add_round(_session_id(config), round_state)
        await _send_event(
            config,
            "round_result",
            {
                "critique": critique,
                "match_score": state["match_score"],
                "filler_words_found": state["merged_analysis"].get("filler_words_found", []),
                "filler_word_count": state["merged_analysis"].get("filler_word_count", 0),
                "filler_word_breakdown": state["merged_analysis"].get("filler_word_breakdown", {}),
                "derived_metrics": state["merged_analysis"].get("derived_metrics", {}),
                "display_metrics": state["merged_analysis"].get("display_metrics", []),
            },
        )
        return {"critique": critique, "error": None}
    except Exception as error:
        logger.exception("Failed to generate Phase A critique.")
        return {"error": f"Could not generate critique: {error}"}

async def check_continue(state: PhaseAState, config: RunnableConfig) -> dict[str, Any]:
    try:
        continue_session = await get_session_manager().wait_for_continue(_session_id(config))
        previous_critiques = [*state["previous_critiques"]]
        if state.get("critique"):
            previous_critiques.append(state["critique"] or "")
        if not continue_session:
            session_id = _session_id(config)
            summary = get_session_manager().get_summary(session_id).model_dump()
            schedule_repository_write(
                get_session_repository().update_phase_a_session(
                    session_id=session_id,
                    summary=summary,
                    raw_state={**state, "previous_critiques": previous_critiques},
                    status="complete",
                ),
                key=session_id,
            )
            await _send_event(config, "session_summary", summary)
        return {
            "previous_critiques": previous_critiques,
            "continue_session": continue_session,
            "video_path": None,
            "audio_path": None,
            "video_upload": None,
            "audio_upload": None,
            "video_id": None,
            "audio_id": None,
            "imentiv_analysis": {},
            "video_emotions": [],
            "audio_emotions": [],
            "transcript": None,
            "word_timestamps": [],
            "merged_analysis": {},
            "word_correlations": [],
            "critique": None,
            "match_score": 0,
            "error": None,
        }
    except Exception as error:
        return {"error": f"Could not read continue decision: {error}"}


async def handle_error(state: PhaseAState, config: RunnableConfig) -> dict[str, Any]:
    message = state.get("error") or "Something went wrong while analyzing your recording."
    await _send_event(config, "error", {"message": message})
    return {"continue_session": False}


def build_merged_analysis(state: PhaseAState) -> tuple[dict[str, Any], list[dict[str, Any]], float]:
    """Merge video, audio, and word streams by nearest timestamps."""

    video_emotions = sorted(state["video_emotions"], key=_event_timestamp_ms)
    audio_emotions = sorted(state["audio_emotions"], key=_event_timestamp_ms)
    word_correlations = [
        correlation
        for word in state["word_timestamps"]
        if (correlation := _build_word_correlation(word, video_emotions, audio_emotions)) is not None
    ]
    peak_match_score = _calculate_peak_match_score(video_emotions, state["target_emotion"])
    filler_word_count, filler_word_breakdown = count_fillers(state["word_timestamps"])
    filler_words_found = [w for w, n in filler_word_breakdown.items() for _ in range(n)]
    missing_streams = {
        "video": len(video_emotions) == 0,
        "audio": len(audio_emotions) == 0,
        "transcript": not state["transcript"],
    }
    imentiv_scores = {
        "confidence_score": state.get("imentiv_analysis", {}).get("confidence_score"),
        "clarity_score": state.get("imentiv_analysis", {}).get("clarity_score"),
        "resilience_score": state.get("imentiv_analysis", {}).get("resilience_score"),
        "engagement_score": state.get("imentiv_analysis", {}).get("engagement_score"),
    }
    raw_data = {
        "transcript": state["transcript"],
        "word_timestamps": state["word_timestamps"],
        "word_correlations": word_correlations,
        "video_emotion_timeline": video_emotions,
        "audio_emotion_timeline": audio_emotions,
        "imentiv_summary": state.get("imentiv_analysis", {}).get("summary"),
        "imentiv_scores": imentiv_scores,
        "imentiv_is_mock": bool(state.get("imentiv_analysis", {}).get("is_mock")),
        "missing_streams": missing_streams,
    }
    derived_metrics = _build_derived_metrics(
        target_emotion=state["target_emotion"],
        peak_match_score=peak_match_score,
        filler_words_found=filler_words_found,
        video_emotions=video_emotions,
        audio_emotions=audio_emotions,
        word_correlations=word_correlations,
        word_timestamps=state["word_timestamps"],
        missing_streams=missing_streams,
        is_mock=bool(state.get("imentiv_analysis", {}).get("is_mock")),
    )
    match_score = float(derived_metrics.get("overall_match_score") or 0)
    display_metrics = _build_display_metrics(derived_metrics)
    merged_analysis = {
        "target_emotion": state["target_emotion"],
        "scenario_prompt": state["scenario_prompt"],
        "transcript": state["transcript"],
        "filler_words_found": filler_words_found,
        "filler_word_count": filler_word_count,
        "filler_word_breakdown": filler_word_breakdown,
        "video_emotion_timeline": video_emotions,
        "audio_emotion_timeline": audio_emotions,
        "imentiv_summary": state.get("imentiv_analysis", {}).get("summary"),
        "imentiv_scores": imentiv_scores,
        "word_correlations": word_correlations,
        "match_score": match_score,
        "peak_match_score": peak_match_score,
        "missing_streams": missing_streams,
        "raw_data": raw_data,
        "derived_metrics": derived_metrics,
        "display_metrics": display_metrics,
    }
    return merged_analysis, word_correlations, match_score


def _build_derived_metrics(
    *,
    target_emotion: str,
    peak_match_score: float,
    filler_words_found: list[str],
    video_emotions: list[dict[str, Any]],
    audio_emotions: list[dict[str, Any]],
    word_correlations: list[dict[str, Any]],
    word_timestamps: list[dict[str, Any]],
    missing_streams: dict[str, bool],
    is_mock: bool,
) -> dict[str, Any]:
    total_words = len([word for word in word_timestamps if str(word.get("word") or "").strip()])
    target_events = [
        event for event in video_emotions if _emotion_matches(str(event.get("emotion_type") or ""), target_emotion)
    ]
    comparable_correlations = [
        correlation
        for correlation in word_correlations
        if correlation.get("face_emotion_type") and correlation.get("voice_emotion_type")
    ]
    aligned_correlations = [
        correlation
        for correlation in comparable_correlations
        if _emotion_matches(
            str(correlation.get("face_emotion_type") or ""),
            str(correlation.get("voice_emotion_type") or ""),
        )
    ]
    top_target_moments = _top_target_moments(target_events)
    top_mismatch_moments = _top_mismatch_moments(word_correlations)
    timed_video_events = [event for event in video_emotions if not event.get("is_aggregate")]
    target_frame_ratio = (
        len([event for event in timed_video_events if _emotion_matches(str(event.get("emotion_type") or ""), target_emotion)])
        / len(timed_video_events)
        if timed_video_events
        else 0
    )
    face_voice_alignment_ratio = (
        len(aligned_correlations) / len(comparable_correlations) if comparable_correlations else 0
    )
    aggregate_alignment_score = _calculate_aggregate_alignment(video_emotions, audio_emotions)
    if not comparable_correlations:
        face_voice_alignment_ratio = aggregate_alignment_score
    average_target_confidence = _average_confidence(target_events)
    target_presence_score = target_frame_ratio if timed_video_events else average_target_confidence
    emotion_stability_score = _calculate_emotion_stability(video_emotions)
    overall_match_score = _calculate_overall_match_score(
        target_emotion=target_emotion,
        target_presence_score=target_presence_score,
        average_target_confidence=average_target_confidence,
        face_voice_alignment_ratio=face_voice_alignment_ratio,
        emotion_stability_score=emotion_stability_score,
        has_video=bool(video_emotions),
        has_alignment=bool(comparable_correlations) or aggregate_alignment_score > 0,
    )
    return {
        "match_score": overall_match_score,
        "overall_match_score": overall_match_score,
        "peak_match_score": peak_match_score,
        "filler_word_count": len(filler_words_found),
        "filler_rate": len(filler_words_found) / total_words if total_words else 0,
        "target_frame_ratio": target_frame_ratio,
        "target_presence_score": target_presence_score,
        "average_target_confidence": average_target_confidence,
        "face_voice_alignment_ratio": face_voice_alignment_ratio,
        "aggregate_face_voice_alignment_ratio": aggregate_alignment_score,
        "emotion_stability_score": emotion_stability_score,
        "top_target_moments": top_target_moments,
        "top_mismatch_moments": top_mismatch_moments,
        "data_quality_flags": _data_quality_flags(
            missing_streams=missing_streams,
            total_words=total_words,
            video_event_count=len(video_emotions),
            comparable_correlation_count=len(comparable_correlations),
            is_mock=is_mock,
            timed_video_event_count=len(timed_video_events),
            has_aggregate_alignment=aggregate_alignment_score > 0,
        ),
    }


def _build_display_metrics(derived_metrics: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "key": "overall_match_score",
            "label": "Overall emotion match",
            "value": round(float(derived_metrics.get("overall_match_score") or 0), 4),
            "display_value": _format_percentage(derived_metrics.get("overall_match_score")),
            "description": "Based on coverage, consistency, and face-voice alignment across the response.",
        },
        {
            "key": "peak_match_score",
            "label": "Peak target moment",
            "value": round(float(derived_metrics.get("peak_match_score") or 0), 4),
            "display_value": _format_percentage(derived_metrics.get("peak_match_score")),
            "description": "The strongest single facial moment matching the target emotion.",
        },
        {
            "key": "target_frame_ratio",
            "label": "Target signal",
            "value": round(float(derived_metrics.get("target_presence_score") or 0), 4),
            "display_value": _format_percentage(derived_metrics.get("target_presence_score")),
            "description": "How strongly the target emotion appeared in the available facial signal.",
        },
        {
            "key": "emotion_stability_score",
            "label": "Emotion stability",
            "value": round(float(derived_metrics.get("emotion_stability_score") or 0), 4),
            "display_value": _format_percentage(derived_metrics.get("emotion_stability_score")),
            "description": "How concentrated the facial emotion signal was around one dominant expression.",
        },
        {
            "key": "face_voice_alignment_ratio",
            "label": "Face and voice alignment",
            "value": round(float(derived_metrics.get("face_voice_alignment_ratio") or 0), 4),
            "display_value": _format_percentage(derived_metrics.get("face_voice_alignment_ratio")),
            "description": "How closely facial and vocal emotion signals agreed using the available data.",
        },
        {
            "key": "filler_rate",
            "label": "Filler rate",
            "value": round(float(derived_metrics.get("filler_rate") or 0), 4),
            "display_value": _format_percentage(derived_metrics.get("filler_rate")),
            "description": "Share of spoken words that were detected as filler words.",
        },
    ]


def compile_phase_a_graph():
    """Compile the Phase A LangGraph workflow."""

    graph = StateGraph(PhaseAState)
    graph.add_node("generate_scenario", generate_scenario)
    graph.add_node("await_recording", await_recording)
    graph.add_node("upload_to_imentiv", upload_to_imentiv)
    graph.add_node("poll_imentiv_results", poll_imentiv_results)
    graph.add_node("merge_and_correlate", merge_and_correlate)
    graph.add_node("generate_critique", generate_critique)
    graph.add_node("check_continue", check_continue)
    graph.add_node("handle_error", handle_error)

    graph.set_entry_point("generate_scenario")
    graph.add_conditional_edges(
        "generate_scenario",
        _route_error,
        {"error": "handle_error", "ok": "await_recording"},
    )
    graph.add_edge("await_recording", "upload_to_imentiv")
    graph.add_conditional_edges(
        "upload_to_imentiv",
        _route_error,
        {"error": "handle_error", "ok": "poll_imentiv_results"},
    )
    graph.add_conditional_edges(
        "poll_imentiv_results",
        _route_error,
        {"error": "handle_error", "ok": "merge_and_correlate"},
    )
    graph.add_conditional_edges(
        "merge_and_correlate",
        _route_error,
        {"error": "handle_error", "ok": "generate_critique"},
    )
    graph.add_conditional_edges(
        "generate_critique",
        _route_error,
        {"error": "handle_error", "ok": "check_continue"},
    )
    graph.add_conditional_edges(
        "check_continue",
        _route_continue,
        {"continue": "generate_scenario", "end": END, "error": "handle_error"},
    )
    graph.add_edge("handle_error", END)
    return graph.compile()

async def _soft_result(awaitable):
    try:
        return await awaitable
    except TimeoutError:
        logger.warning("Soft-result task timed out (TimeoutError).")
        return []
    except asyncio.TimeoutError:
        logger.warning("Soft-result task timed out (asyncio.TimeoutError).")
        return []
    except Exception:
        logger.exception("Soft-result task failed.")
        return []


def _build_word_correlation(
    word: dict[str, Any],
    video_emotions: list[dict[str, Any]],
    audio_emotions: list[dict[str, Any]],
) -> dict[str, Any] | None:
    word_text = str(word.get("word") or "").strip()
    if not word_text:
        return None

    timestamp_ms = int(float(word.get("start") or 0) * 1000)
    face_event = _nearest_event(timestamp_ms, video_emotions)
    voice_event = _nearest_event(timestamp_ms, audio_emotions)
    if face_event is None and voice_event is None:
        return None

    return {
        "word": word_text,
        "timestamp_ms": timestamp_ms,
        "face_emotion_type": face_event.get("emotion_type") if face_event else None,
        "face_confidence": face_event.get("confidence") if face_event else None,
        "voice_emotion_type": voice_event.get("emotion_type") if voice_event else None,
        "voice_confidence": voice_event.get("confidence") if voice_event else None,
    }


def _nearest_event(timestamp_ms: int, events: list[dict[str, Any]]) -> dict[str, Any] | None:
    timed_events = [event for event in events if not event.get("is_aggregate") and event.get("timestamp") is not None]
    if not timed_events:
        return None
    nearest = min(timed_events, key=lambda event: abs(_event_timestamp_ms(event) - timestamp_ms))
    distance = abs(_event_timestamp_ms(nearest) - timestamp_ms)
    return nearest if distance <= MATCH_WINDOW_MS else None


def _event_timestamp_ms(event: dict[str, Any]) -> int:
    try:
        return int(event.get("timestamp") or 0)
    except (TypeError, ValueError):
        return 0


def _calculate_peak_match_score(video_emotions: list[dict[str, Any]], target_emotion: str) -> float:
    matches = [
        float(event.get("confidence") or 0)
        for event in video_emotions
        if _emotion_matches(str(event.get("emotion_type") or ""), target_emotion)
    ]
    return max(matches, default=0)


def _emotion_matches(observed_emotion: str, target_emotion: str) -> bool:
    return _emotion_key(observed_emotion) == _emotion_key(target_emotion)


def _emotion_key(emotion: str) -> str:
    normalized = emotion.lower().strip()
    aliases = {
        "neutrality (neutral)": "neutral",
        "neutrality": "neutral",
        "happy": "happiness",
        "joy": "happiness",
        "angry": "anger",
        "sad": "sadness",
        "confident": "confidence",
    }
    return aliases.get(normalized, normalized)


def _top_target_moments(target_events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked_events = sorted(
        target_events,
        key=lambda event: float(event.get("confidence") or 0),
        reverse=True,
    )
    return [
        {
            "timestamp_ms": event.get("timestamp") if event.get("timestamp") is not None else None,
            "emotion_type": str(event.get("emotion_type") or ""),
            "confidence": float(event.get("confidence") or 0),
            "is_aggregate": bool(event.get("is_aggregate")),
            "source": event.get("source"),
        }
        for event in ranked_events[:TOP_MOMENTS_LIMIT]
    ]


def _top_mismatch_moments(word_correlations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    mismatches = [
        correlation
        for correlation in word_correlations
        if correlation.get("face_emotion_type")
        and correlation.get("voice_emotion_type")
        and not _emotion_matches(
            str(correlation.get("face_emotion_type") or ""),
            str(correlation.get("voice_emotion_type") or ""),
        )
    ]
    ranked_mismatches = sorted(
        mismatches,
        key=lambda correlation: max(
            float(correlation.get("face_confidence") or 0),
            float(correlation.get("voice_confidence") or 0),
        ),
        reverse=True,
    )
    return [
        {
            "timestamp_ms": int(correlation.get("timestamp_ms") or 0),
            "word": str(correlation.get("word") or ""),
            "face_emotion_type": str(correlation.get("face_emotion_type") or ""),
            "voice_emotion_type": str(correlation.get("voice_emotion_type") or ""),
            "face_confidence": float(correlation.get("face_confidence") or 0),
            "voice_confidence": float(correlation.get("voice_confidence") or 0),
        }
        for correlation in ranked_mismatches[:TOP_MOMENTS_LIMIT]
    ]


def _average_confidence(events: list[dict[str, Any]]) -> float:
    if not events:
        return 0
    return sum(float(event.get("confidence") or 0) for event in events) / len(events)


def _calculate_emotion_stability(video_emotions: list[dict[str, Any]]) -> float:
    timed_events = [event for event in video_emotions if not event.get("is_aggregate")]
    if not timed_events:
        return _dominant_aggregate_confidence(video_emotions)

    emotion_keys = [
        _emotion_key(str(event.get("emotion_type") or ""))
        for event in timed_events
        if str(event.get("emotion_type") or "").strip()
    ]
    if not emotion_keys:
        return 0
    if len(emotion_keys) == 1:
        return 1
    switches = sum(
        1
        for previous_emotion, current_emotion in zip(emotion_keys, emotion_keys[1:], strict=False)
        if previous_emotion != current_emotion
    )
    possible_switches = len(emotion_keys) - 1
    return max(0.0, 1 - (switches / possible_switches))


def _dominant_aggregate_confidence(events: list[dict[str, Any]]) -> float:
    distribution = _aggregate_distribution(events, preferred_source_prefix="overall")
    if not distribution:
        distribution = _aggregate_distribution(events)
    return max(distribution.values(), default=0)


def _calculate_aggregate_alignment(
    video_emotions: list[dict[str, Any]],
    audio_emotions: list[dict[str, Any]],
) -> float:
    video_distribution = _aggregate_distribution(video_emotions, preferred_source_prefix="overall")
    audio_distribution = _aggregate_distribution(audio_emotions, preferred_source_prefix="overall")
    if not video_distribution or not audio_distribution:
        return 0
    labels = set(video_distribution) | set(audio_distribution)
    if not labels:
        return 0
    return sum(min(video_distribution.get(label, 0), audio_distribution.get(label, 0)) for label in labels)


def _aggregate_distribution(
    events: list[dict[str, Any]],
    preferred_source_prefix: str | None = None,
) -> dict[str, float]:
    aggregate_events = [event for event in events if event.get("is_aggregate")]
    if preferred_source_prefix:
        preferred_events = [
            event
            for event in aggregate_events
            if str(event.get("source") or "").lower().startswith(preferred_source_prefix)
        ]
        if preferred_events:
            aggregate_events = preferred_events

    distribution: dict[str, float] = {}
    for event in aggregate_events:
        label = _emotion_key(str(event.get("emotion_type") or ""))
        if not label:
            continue
        distribution[label] = max(distribution.get(label, 0), float(event.get("confidence") or 0))
    total = sum(distribution.values())
    if total <= 0:
        return distribution
    return {label: value / total for label, value in distribution.items()}


def _calculate_overall_match_score(
    *,
    target_emotion: str,
    target_presence_score: float,
    average_target_confidence: float,
    face_voice_alignment_ratio: float,
    emotion_stability_score: float,
    has_video: bool,
    has_alignment: bool,
) -> float:
    target_key = _emotion_key(target_emotion)
    weighted_parts: list[tuple[float, float, bool]]
    if target_key == "neutral":
        weighted_parts = [
            (target_presence_score, 0.40, has_video),
            (face_voice_alignment_ratio, 0.25, has_alignment),
            (emotion_stability_score, 0.25, has_video),
            (average_target_confidence, 0.10, has_video),
        ]
    else:
        weighted_parts = [
            (target_presence_score, 0.45, has_video),
            (average_target_confidence, 0.30, has_video),
            (face_voice_alignment_ratio, 0.15, has_alignment),
            (emotion_stability_score, 0.10, has_video),
        ]
    available_parts = [(value, weight) for value, weight, is_available in weighted_parts if is_available]
    if not available_parts:
        return 0
    total_weight = sum(weight for _, weight in available_parts)
    return sum(value * weight for value, weight in available_parts) / total_weight


def _data_quality_flags(
    *,
    missing_streams: dict[str, bool],
    total_words: int,
    video_event_count: int,
    comparable_correlation_count: int,
    is_mock: bool,
    timed_video_event_count: int,
    has_aggregate_alignment: bool,
) -> list[str]:
    flags: list[str] = []
    if is_mock:
        flags.append("mock_imentiv_analysis")
    if missing_streams.get("video"):
        flags.append("missing_video_signal")
    if missing_streams.get("audio"):
        flags.append("missing_audio_signal")
    if missing_streams.get("transcript"):
        flags.append("missing_transcript")
    if total_words < 4:
        flags.append("limited_transcript")
    if video_event_count < 3:
        flags.append("limited_video_samples")
    if video_event_count and timed_video_event_count == 0:
        flags.append("aggregate_emotion_scores")
    if comparable_correlation_count < 2 and not has_aggregate_alignment:
        flags.append("limited_alignment_samples")
    return flags


def _format_percentage(value: Any) -> str:
    return f"{round(float(value or 0) * 100)}%"


async def _send_event(config: RunnableConfig, event_type: str, payload: dict[str, Any]) -> None:
    await get_session_manager().send_event(_session_id(config), event_type, payload)


def _session_id(config: RunnableConfig) -> str:
    configurable = (config or {}).get("configurable", {})
    session_id = configurable.get("session_id")
    if not session_id:
        raise RuntimeError("Missing Phase A session_id in LangGraph config.")
    return str(session_id)


def _route_error(state: PhaseAState) -> str:
    return "error" if state.get("error") else "ok"


def _route_continue(state: PhaseAState) -> str:
    if state.get("error"):
        return "error"
    return "continue" if state["continue_session"] else "end"


phase_a_graph = compile_phase_a_graph()
