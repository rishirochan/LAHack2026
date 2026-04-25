"""LangGraph workflow for Phase A emotion drills."""

import asyncio
import logging
from typing import Any, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph

from backend.shared.ai import get_ai_service, get_settings
from backend.shared.db import get_session_repository
from .elevenlabs import synthesize_tts_audio, transcribe_audio as transcribe_elevenlabs
from .gemma import generate_coach_critique, generate_scenario_prompt
from .imentiv import analyze_video
from .session_manager import get_session_manager


FILLER_WORDS = {"um", "uh", "like", "you know", "basically", "literally", "so", "right"}
MATCH_WINDOW_MS = 1000
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


async def speak_scenario(state: PhaseAState, config: RunnableConfig) -> dict[str, Any]:
    try:
        await _stream_tts(config, "scenario", state["scenario_prompt"] or "")
        return {}
    except Exception as error:
        logger.exception("Failed to stream Phase A scenario TTS.")
        return {"error": f"Could not speak the scenario: {error}"}


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
        await _send_event(
            config,
            "round_result",
            {
                "critique": critique,
                "match_score": state["match_score"],
                "filler_words_found": state["merged_analysis"].get("filler_words_found", []),
                "filler_word_count": state["merged_analysis"].get("filler_word_count", 0),
            },
        )
        return {"critique": critique, "error": None}
    except Exception as error:
        logger.exception("Failed to generate Phase A critique.")
        return {"error": f"Could not generate critique: {error}"}


async def speak_critique(state: PhaseAState, config: RunnableConfig) -> dict[str, Any]:
    try:
        await _send_event(config, "processing_stage", {"stage": "Preparing playback"})
        await _stream_tts(config, "critique", state["critique"] or "")
        previous_critiques = [*state["previous_critiques"], state["critique"] or ""]
        get_session_manager().add_round(_session_id(config), {**state, "previous_critiques": previous_critiques})
        return {"previous_critiques": previous_critiques, "error": None}
    except Exception as error:
        logger.exception("Failed to stream Phase A critique TTS.")
        return {"error": f"Could not speak critique: {error}"}


async def check_continue(state: PhaseAState, config: RunnableConfig) -> dict[str, Any]:
    try:
        continue_session = await get_session_manager().wait_for_continue(_session_id(config))
        if not continue_session:
            session_id = _session_id(config)
            summary = get_session_manager().get_summary(session_id).model_dump()
            await get_session_repository().update_phase_a_session(
                session_id=session_id,
                summary=summary,
                raw_state=state,
                status="complete",
            )
            await _send_event(config, "session_summary", summary)
        return {
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

    video_emotions = sorted(state["video_emotions"], key=lambda event: int(event.get("timestamp", 0)))
    audio_emotions = sorted(state["audio_emotions"], key=lambda event: int(event.get("timestamp", 0)))
    word_correlations = [
        correlation
        for word in state["word_timestamps"]
        if (correlation := _build_word_correlation(word, video_emotions, audio_emotions)) is not None
    ]
    match_score = _calculate_match_score(video_emotions, state["target_emotion"])
    filler_words_found = _find_filler_words(state["word_timestamps"])
    merged_analysis = {
        "target_emotion": state["target_emotion"],
        "scenario_prompt": state["scenario_prompt"],
        "transcript": state["transcript"],
        "filler_words_found": filler_words_found,
        "filler_word_count": len(filler_words_found),
        "video_emotion_timeline": video_emotions,
        "audio_emotion_timeline": audio_emotions,
        "imentiv_summary": state.get("imentiv_analysis", {}).get("summary"),
        "imentiv_scores": {
            "confidence_score": state.get("imentiv_analysis", {}).get("confidence_score"),
            "clarity_score": state.get("imentiv_analysis", {}).get("clarity_score"),
            "resilience_score": state.get("imentiv_analysis", {}).get("resilience_score"),
            "engagement_score": state.get("imentiv_analysis", {}).get("engagement_score"),
        },
        "word_correlations": word_correlations,
        "match_score": match_score,
        "missing_streams": {
            "video": len(video_emotions) == 0,
            "audio": len(audio_emotions) == 0,
            "transcript": not state["transcript"],
        },
    }
    return merged_analysis, word_correlations, match_score


def compile_phase_a_graph():
    """Compile the Phase A LangGraph workflow."""

    graph = StateGraph(PhaseAState)
    graph.add_node("generate_scenario", generate_scenario)
    graph.add_node("speak_scenario", speak_scenario)
    graph.add_node("await_recording", await_recording)
    graph.add_node("upload_to_imentiv", upload_to_imentiv)
    graph.add_node("poll_imentiv_results", poll_imentiv_results)
    graph.add_node("merge_and_correlate", merge_and_correlate)
    graph.add_node("generate_critique", generate_critique)
    graph.add_node("speak_critique", speak_critique)
    graph.add_node("check_continue", check_continue)
    graph.add_node("handle_error", handle_error)

    graph.set_entry_point("generate_scenario")
    graph.add_conditional_edges(
        "generate_scenario",
        _route_error,
        {"error": "handle_error", "ok": "speak_scenario"},
    )
    graph.add_conditional_edges(
        "speak_scenario",
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
        {"error": "handle_error", "ok": "speak_critique"},
    )
    graph.add_conditional_edges(
        "speak_critique",
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


async def _stream_tts(config: RunnableConfig, audio_type: str, text: str) -> None:
    await _send_event(config, "tts_start", {"audio_type": audio_type, "text": text})
    audio = await synthesize_tts_audio(ai_service=get_ai_service(), text=text)
    await _send_event(
        config,
        "audio_blob",
        {"audio_type": audio_type, "audio": audio, "mime_type": "audio/mpeg"},
    )
    await _send_event(config, "tts_end", {"audio_type": audio_type})


async def _soft_result(awaitable):
    try:
        return await awaitable
    except TimeoutError:
        return []
    except asyncio.TimeoutError:
        return []
    except Exception:
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
    if not events:
        return None
    nearest = min(events, key=lambda event: abs(int(event.get("timestamp", 0)) - timestamp_ms))
    distance = abs(int(nearest.get("timestamp", 0)) - timestamp_ms)
    return nearest if distance <= MATCH_WINDOW_MS else None


def _calculate_match_score(video_emotions: list[dict[str, Any]], target_emotion: str) -> float:
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
        "confident": "confidence",
    }
    return aliases.get(normalized, normalized)


def _find_filler_words(word_timestamps: list[dict[str, Any]]) -> list[str]:
    words = [str(word.get("word") or "").strip().lower().strip(".,!?;:") for word in word_timestamps]
    fillers: list[str] = []
    for index, word in enumerate(words):
        if word in FILLER_WORDS:
            fillers.append(word)
        if index < len(words) - 1 and f"{word} {words[index + 1]}" in FILLER_WORDS:
            fillers.append(f"{word} {words[index + 1]}")
    return fillers


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

