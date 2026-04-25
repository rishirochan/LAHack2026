"""LangGraph workflow for standalone Phase C analysis."""

import asyncio
import json
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph

from backend.shared.ai import get_ai_service
from backend.sprint.phase_c.broker import build_scorecard
from backend.sprint.phase_c.constants import PHASE_C_CHUNK_POLL_SECONDS, PHASE_C_CHUNK_TIMEOUT_SECONDS
from backend.sprint.phase_c.gemma import generate_phase_c_summary
from backend.sprint.phase_c.schemas import PhaseCState
from backend.sprint.phase_c.session_manager import get_phase_c_manager


async def collect_chunks(state: PhaseCState, config: RunnableConfig) -> dict[str, Any]:
    session_id = _session_id(config)
    manager = get_phase_c_manager()
    recording = manager.get_state(session_id).get("current_recording")
    if recording is None:
        return {"error": "No active recording for collect_chunks."}

    await _send_event(config, "processing_stage", {"stage": "Collecting analysis results"})

    deadline = asyncio.get_event_loop().time() + PHASE_C_CHUNK_TIMEOUT_SECONDS
    while asyncio.get_event_loop().time() < deadline:
        pending = [chunk for chunk in recording["chunks"] if chunk["status"] in ("pending", "processing")]
        if not pending:
            break
        await asyncio.sleep(PHASE_C_CHUNK_POLL_SECONDS)

    for chunk in recording["chunks"]:
        if chunk["status"] in ("pending", "processing"):
            chunk["status"] = "timed_out"

    return {"error": None}


async def merge_recording_data(state: PhaseCState, config: RunnableConfig) -> dict[str, Any]:
    session_id = _session_id(config)
    manager = get_phase_c_manager()
    recording = manager.get_state(session_id).get("current_recording")
    if recording is None:
        return {"error": "No active recording for merge_recording_data."}

    await _send_event(config, "processing_stage", {"stage": "Merging analysis"})

    transcript_words = [
        {
            "word": str(word.get("word") or ""),
            "start_ms": int(float(word.get("start") or word.get("start_ms") or 0) * (1000 if "start" in word else 1)),
            "end_ms": int(float(word.get("end") or word.get("end_ms") or 0) * (1000 if "end" in word else 1)),
        }
        for word in (recording.get("transcript_words") or [])
    ]
    chunks = sorted(recording["chunks"], key=lambda chunk: (chunk["start_ms"], chunk["chunk_index"]))

    merged_chunks: list[dict[str, Any]] = []
    for chunk in chunks:
        segment_words = [
            word for word in transcript_words
            if word["start_ms"] >= chunk["start_ms"] and word["start_ms"] < chunk["end_ms"]
        ]
        dominant_video = _dominant_emotion(chunk.get("video_emotions") or [])
        dominant_audio = _dominant_emotion(chunk.get("audio_emotions") or [])
        mediapipe_metrics = chunk.get("mediapipe_metrics") or {}

        merged_chunks.append(
            {
                "chunk_index": chunk["chunk_index"],
                "t_start": chunk["start_ms"],
                "t_end": chunk["end_ms"],
                "transcript_segment": " ".join(word["word"] for word in segment_words).strip(),
                "dominant_video_emotion": dominant_video.get("emotion_type") if dominant_video else None,
                "video_confidence": dominant_video.get("confidence") if dominant_video else None,
                "dominant_audio_emotion": dominant_audio.get("emotion_type") if dominant_audio else None,
                "audio_confidence": dominant_audio.get("confidence") if dominant_audio else None,
                "eye_contact_pct": (mediapipe_metrics.get("avg_eye_contact_score", 0) or 0) * 100,
                "status": chunk["status"],
            }
        )

    overall = {
        "total_chunks": len(chunks),
        "chunks_done": sum(1 for chunk in chunks if chunk["status"] == "done"),
        "chunks_failed": sum(1 for chunk in chunks if chunk["status"] == "failed"),
        "chunks_timed_out": sum(1 for chunk in chunks if chunk["status"] == "timed_out"),
        "recording_duration_ms": int((recording.get("recording_end_ms") or 0) - (recording.get("recording_start_ms") or 0)),
    }
    merged_analysis = {
        "full_transcript": recording.get("transcript") or "",
        "transcript_words": transcript_words,
        "chunks": merged_chunks,
        "overall": overall,
    }
    manager.set_merged_analysis(session_id, merged_analysis)
    return {"error": None}


async def compute_scorecard(state: PhaseCState, config: RunnableConfig) -> dict[str, Any]:
    session_id = _session_id(config)
    manager = get_phase_c_manager()
    recording = manager.get_state(session_id).get("current_recording")
    if recording is None or recording.get("merged_analysis") is None:
        return {"error": "No merged analysis available for Phase C scorecard generation."}

    await _send_event(config, "processing_stage", {"stage": "Computing scorecard"})
    recording["scorecard"] = build_scorecard(recording["merged_analysis"])
    return {"error": None}


async def generate_written_summary_node(state: PhaseCState, config: RunnableConfig) -> dict[str, Any]:
    session_id = _session_id(config)
    manager = get_phase_c_manager()
    session_state = manager.get_state(session_id)
    recording = session_state.get("current_recording")
    if recording is None or recording.get("scorecard") is None:
        return {"error": "No scorecard available for written summary generation."}

    await _send_event(config, "processing_stage", {"stage": "Generating summary"})
    recording["written_summary"] = await generate_phase_c_summary(
        ai_service=get_ai_service(),
        scorecard_json=json.dumps(recording["scorecard"], ensure_ascii=True),
    )
    return {"error": None}


async def finalize_recording_node(state: PhaseCState, config: RunnableConfig) -> dict[str, Any]:
    session_id = _session_id(config)
    manager = get_phase_c_manager()
    recording = manager.get_state(session_id).get("current_recording")
    if recording is None:
        return {"error": "No active recording to finalize."}

    scorecard = recording.get("scorecard") or {}
    written_summary = recording.get("written_summary") or ""
    final_state = manager.finalize_recording(session_id, scorecard, written_summary)
    await _send_event(
        config,
        "session_result",
        {
            "scorecard": final_state["completed_recording"]["scorecard"] if final_state.get("completed_recording") else {},
            "written_summary": final_state["completed_recording"]["written_summary"] if final_state.get("completed_recording") else "",
        },
    )
    return {"error": None}


async def handle_error(state: PhaseCState, config: RunnableConfig) -> dict[str, Any]:
    await _send_event(config, "error", {"message": state.get("error") or "Phase C failed unexpectedly."})
    return {}


async def _send_event(config: RunnableConfig, event_type: str, payload: dict[str, Any]) -> None:
    await get_phase_c_manager().send_event(_session_id(config), event_type, payload)


def _session_id(config: RunnableConfig) -> str:
    configurable = (config or {}).get("configurable", {})
    session_id = configurable.get("session_id")
    if not session_id:
        raise RuntimeError("Missing Phase C session_id in LangGraph config.")
    return str(session_id)


def _route_error(state: PhaseCState) -> str:
    return "error" if state.get("error") else "ok"


def _dominant_emotion(emotions: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not emotions:
        return None
    return max(emotions, key=lambda emotion: float(emotion.get("confidence") or 0))


def compile_phase_c_graph():
    graph = StateGraph(PhaseCState)
    graph.add_node("collect_chunks", collect_chunks)
    graph.add_node("merge_recording_data", merge_recording_data)
    graph.add_node("compute_scorecard", compute_scorecard)
    graph.add_node("generate_written_summary", generate_written_summary_node)
    graph.add_node("finalize_recording", finalize_recording_node)
    graph.add_node("handle_error", handle_error)

    graph.set_entry_point("collect_chunks")
    graph.add_conditional_edges("collect_chunks", _route_error, {"ok": "merge_recording_data", "error": "handle_error"})
    graph.add_conditional_edges("merge_recording_data", _route_error, {"ok": "compute_scorecard", "error": "handle_error"})
    graph.add_conditional_edges("compute_scorecard", _route_error, {"ok": "generate_written_summary", "error": "handle_error"})
    graph.add_conditional_edges("generate_written_summary", _route_error, {"ok": "finalize_recording", "error": "handle_error"})
    graph.add_conditional_edges("finalize_recording", _route_error, {"ok": END, "error": "handle_error"})
    graph.add_edge("handle_error", END)
    return graph.compile()


phase_c_graph = compile_phase_c_graph()
