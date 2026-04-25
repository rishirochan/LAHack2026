"""LangGraph workflow for Phase B long-form conversations.

The graph is invoked **once per turn** — not as a continuous running process.
Two separate subgraphs are compiled:

* ``prompt_graph``  — invoked when the frontend requests the next prompt
                      (generate_prompt only).
* ``critique_graph`` — invoked after the user finishes recording and chunks
                       are uploaded (collect_chunks → merge_summary →
                       judge_response → speak_critique).

The frontend orchestrates the turn loop and decides when to call each.
"""

import json
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph

from backend.shared.ai import get_ai_service
from backend.sprint.phase_b.elevenlabs import stream_tts_chunks
from backend.sprint.phase_b.gemma import generate_text
from backend.sprint.phase_b.prompts import (
    JUDGE_SYSTEM_PROMPT,
    build_judge_user,
    build_prompt_system,
    build_prompt_user,
)
from backend.sprint.phase_b.schemas import PhaseBState
from backend.sprint.phase_b.session_manager import get_phase_b_manager


# ======================================================================
# Node: generate_prompt
# ======================================================================

async def generate_prompt(state: PhaseBState, config: RunnableConfig) -> dict[str, Any]:
    """Generate the AI persona's next question via Gemma (OpenRouter)."""

    try:
        system = build_prompt_system(
            scenario=state["scenario"],
            persona=state["persona"],
            difficulty=state["difficulty"],
        )
        user = build_prompt_user(
            conversation_history=state["conversation_history"],
            turn_index=state["turn_index"],
        )

        prompt_text = await generate_text(
            ai_service=get_ai_service(),
            system_prompt=system,
            user_prompt=user,
        )

        session_id = _session_id(config)
        await _send_event(config, "prompt_generated", {"prompt_text": prompt_text})

        # Register the turn in the session manager
        get_phase_b_manager().start_turn(session_id, prompt_text)

        return {"error": None}
    except Exception as error:
        return {"error": f"Could not generate prompt: {error}"}


# ======================================================================
# Node: collect_chunks  (Phase 5)
# ======================================================================

async def collect_chunks(state: PhaseBState, config: RunnableConfig) -> dict[str, Any]:
    """Read all chunk records for the current turn and wait for pending ones.

    Polls every 2 seconds, up to 10 seconds. Any chunks still unresolved
    after the deadline are marked as timed_out.
    """

    import asyncio

    session_id = _session_id(config)
    manager = get_phase_b_manager()
    session_state = manager.get_state(session_id)
    current_turn = session_state.get("current_turn")

    if current_turn is None:
        return {"error": "No active turn for collect_chunks."}

    await _send_event(config, "processing_stage", {"stage": "Collecting analysis results"})

    deadline = asyncio.get_event_loop().time() + 10
    while asyncio.get_event_loop().time() < deadline:
        pending = [c for c in current_turn["chunks"] if c["status"] in ("pending", "processing")]
        if not pending:
            break
        await asyncio.sleep(2)

    # Mark anything still unresolved
    for chunk in current_turn["chunks"]:
        if chunk["status"] in ("pending", "processing"):
            chunk["status"] = "timed_out"

    return {"error": None}


# ======================================================================
# Node: merge_summary  (Phase 5)
# ======================================================================

async def merge_summary(state: PhaseBState, config: RunnableConfig) -> dict[str, Any]:
    """Assemble per-chunk emotion data + transcript alignment into the
    merged summary JSON that gets passed to the judge node.

    Aligns ElevenLabs word timestamps to chunk windows by matching each
    word's timestamp to the chunk whose t_start/t_end it falls within.
    """

    session_id = _session_id(config)
    manager = get_phase_b_manager()
    session_state = manager.get_state(session_id)
    current_turn = session_state.get("current_turn")

    if current_turn is None:
        return {"error": "No active turn for merge_summary."}

    await _send_event(config, "processing_stage", {"stage": "Merging analysis"})

    words = current_turn.get("transcript_words") or []
    chunks = current_turn["chunks"]

    # Build per-chunk summary with transcript segments
    chunk_summaries: list[dict[str, Any]] = []
    for chunk in chunks:
        if chunk["status"] not in ("done", "timed_out", "failed"):
            continue

        t_start = chunk["start_ms"]
        t_end = chunk["end_ms"]

        # Words that fall in this chunk's window
        segment_words = [
            w for w in words
            if w.get("start", 0) * 1000 >= t_start and w.get("start", 0) * 1000 < t_end
        ]
        segment_text = " ".join(w.get("word", "") for w in segment_words)

        # Dominant emotions from Imentiv results
        video_ems = chunk.get("video_emotions") or []
        audio_ems = chunk.get("audio_emotions") or []
        dominant_video = _dominant_emotion(video_ems)
        dominant_audio = _dominant_emotion(audio_ems)

        mp = chunk.get("mediapipe_metrics") or {}

        chunk_summaries.append({
            "t_start": t_start,
            "t_end": t_end,
            "dominant_video_emotion": dominant_video.get("emotion_type") if dominant_video else None,
            "video_confidence": dominant_video.get("confidence") if dominant_video else None,
            "dominant_audio_emotion": dominant_audio.get("emotion_type") if dominant_audio else None,
            "audio_confidence": dominant_audio.get("confidence") if dominant_audio else None,
            "eye_contact_pct": mp.get("avg_eye_contact_score", 0) * 100 if mp else 0,
            "transcript_segment": segment_text,
            "status": chunk["status"],
        })

    # Compute overall stats
    all_video = [c for c in chunk_summaries if c["dominant_video_emotion"]]
    all_audio = [c for c in chunk_summaries if c["dominant_audio_emotion"]]
    eye_contacts = [c["eye_contact_pct"] for c in chunk_summaries if c["eye_contact_pct"]]
    timed_out = sum(1 for c in chunks if c["status"] == "timed_out")
    failed = sum(1 for c in chunks if c["status"] == "failed")

    # Emotion arc description
    arc_parts = []
    for cs in chunk_summaries:
        t_sec = cs["t_start"] / 1000
        em = cs["dominant_video_emotion"] or cs["dominant_audio_emotion"] or "unknown"
        arc_parts.append(f"{em} at {t_sec:.0f}s")
    emotion_arc = ", ".join(arc_parts) if arc_parts else "no data"

    merged = {
        "persona": state["persona"],
        "difficulty": state["difficulty"],
        "question_asked": current_turn.get("prompt_text", ""),
        "full_transcript": current_turn.get("transcript") or "",
        "transcript_words": [
            {"word": w["word"], "start_ms": int(w["start"] * 1000), "end_ms": int(w["end"] * 1000)}
            for w in words
        ],
        "chunks": chunk_summaries,
        "overall": {
            "dominant_video_emotion": _most_common([c["dominant_video_emotion"] for c in all_video]),
            "dominant_audio_emotion": _most_common([c["dominant_audio_emotion"] for c in all_audio]),
            "avg_eye_contact_pct": round(sum(eye_contacts) / len(eye_contacts), 1) if eye_contacts else 0,
            "emotion_arc": emotion_arc,
            "chunks_timed_out": timed_out,
            "chunks_failed": failed,
        },
    }

    current_turn["merged_summary"] = merged
    return {"error": None}


# ======================================================================
# Node: judge_response  (Phase 5)
# ======================================================================

async def judge_response(state: PhaseBState, config: RunnableConfig) -> dict[str, Any]:
    """Call Gemma in judge mode with the merged summary to produce
    exactly 2 weaknesses and 1 strength with timestamp references."""

    session_id = _session_id(config)
    manager = get_phase_b_manager()
    session_state = manager.get_state(session_id)
    current_turn = session_state.get("current_turn")

    if current_turn is None:
        return {"error": "No active turn for judge_response."}

    merged = current_turn.get("merged_summary")
    if merged is None:
        return {"error": "No merged summary available for judge."}

    await _send_event(config, "processing_stage", {"stage": "Generating critique"})

    try:
        critique = await generate_text(
            ai_service=get_ai_service(),
            system_prompt=JUDGE_SYSTEM_PROMPT,
            user_prompt=build_judge_user(json.dumps(merged, ensure_ascii=True)),
            temperature=0.4,
            max_tokens=300,
        )

        current_turn["critique"] = critique
        await _send_event(config, "critique_generated", {"critique": critique})
        return {"error": None}
    except Exception as error:
        return {"error": f"Could not generate critique: {error}"}


# ======================================================================
# Node: speak_critique  (Phase 5)
# ======================================================================

async def speak_critique(state: PhaseBState, config: RunnableConfig) -> dict[str, Any]:
    """Stream the critique text as TTS audio over the websocket."""

    session_id = _session_id(config)
    manager = get_phase_b_manager()
    session_state = manager.get_state(session_id)
    current_turn = session_state.get("current_turn")

    if current_turn is None:
        return {"error": "No active turn for speak_critique."}

    critique_text = current_turn.get("critique") or ""
    if not critique_text:
        return {"error": "No critique text to speak."}

    try:
        await _stream_tts(config, "critique", critique_text)
        return {"error": None}
    except Exception as error:
        return {"error": f"Could not speak critique: {error}"}


# ======================================================================
# Node: end_session
# ======================================================================

async def end_session(state: PhaseBState, config: RunnableConfig) -> dict[str, Any]:
    """Assemble the final session record and mark complete."""

    session_id = _session_id(config)
    manager = get_phase_b_manager()
    final_state = manager.end_session(session_id)

    summary = {
        "session_id": session_id,
        "scenario": final_state["scenario"],
        "difficulty": final_state["difficulty"],
        "total_turns": len(final_state["turns"]),
        "turns": [
            {
                "turn_index": t["turn_index"],
                "prompt": t["prompt_text"],
                "critique": t.get("critique"),
            }
            for t in final_state["turns"]
        ],
    }

    await _send_event(config, "session_complete", summary)
    return {"error": None}


# ======================================================================
# Error handler
# ======================================================================

async def handle_error(state: PhaseBState, config: RunnableConfig) -> dict[str, Any]:
    message = state.get("error") or "Something went wrong during the conversation."
    await _send_event(config, "error", {"message": message})
    return {}


# ======================================================================
# Shared helpers  (must be defined before graph compilation at module level)
# ======================================================================

async def _stream_tts(config: RunnableConfig, audio_type: str, text: str) -> None:
    """Stream TTS audio over the session websocket."""

    await _send_event(config, "tts_start", {"audio_type": audio_type, "text": text})
    async for chunk in stream_tts_chunks(ai_service=get_ai_service(), text=text):
        await _send_event(
            config,
            "audio_chunk",
            {"audio_type": audio_type, "chunk": chunk, "mime_type": "audio/mpeg"},
        )
    await _send_event(config, "tts_end", {"audio_type": audio_type})


async def _send_event(config: RunnableConfig, event_type: str, payload: dict[str, Any]) -> None:
    await get_phase_b_manager().send_event(_session_id(config), event_type, payload)


def _session_id(config: RunnableConfig) -> str:
    configurable = (config or {}).get("configurable", {})
    session_id = configurable.get("session_id")
    if not session_id:
        raise RuntimeError("Missing Phase B session_id in LangGraph config.")
    return str(session_id)


def _route_error(state: PhaseBState) -> str:
    return "error" if state.get("error") else "ok"


def _dominant_emotion(emotions: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Return the emotion event with the highest confidence."""

    if not emotions:
        return None
    return max(emotions, key=lambda e: float(e.get("confidence") or 0))


def _most_common(values: list[Any]) -> str | None:
    """Return the most frequently occurring non-None value."""

    filtered = [v for v in values if v is not None]
    if not filtered:
        return None
    from collections import Counter
    return Counter(filtered).most_common(1)[0][0]


# ======================================================================
# Graph compilation
# ======================================================================

def compile_prompt_graph():
    """Compile the subgraph for prompt generation (invoked via /turns/next)."""

    graph = StateGraph(PhaseBState)
    graph.add_node("generate_prompt", generate_prompt)
    graph.add_node("handle_error", handle_error)

    graph.set_entry_point("generate_prompt")
    graph.add_conditional_edges(
        "generate_prompt",
        _route_error,
        {"error": "handle_error", "ok": END},
    )
    graph.add_edge("handle_error", END)
    return graph.compile()


def compile_critique_graph():
    """Compile the subgraph for post-recording analysis.

    Invoked via /turns/{turn}/complete after chunks are uploaded and STT
    is finished.

    Flow: collect_chunks → merge_summary → judge_response → speak_critique
    """

    graph = StateGraph(PhaseBState)
    graph.add_node("collect_chunks", collect_chunks)
    graph.add_node("merge_summary", merge_summary)
    graph.add_node("judge_response", judge_response)
    graph.add_node("speak_critique", speak_critique)
    graph.add_node("handle_error", handle_error)

    graph.set_entry_point("collect_chunks")
    graph.add_conditional_edges(
        "collect_chunks",
        _route_error,
        {"error": "handle_error", "ok": "merge_summary"},
    )
    graph.add_conditional_edges(
        "merge_summary",
        _route_error,
        {"error": "handle_error", "ok": "judge_response"},
    )
    graph.add_conditional_edges(
        "judge_response",
        _route_error,
        {"error": "handle_error", "ok": "speak_critique"},
    )
    graph.add_conditional_edges(
        "speak_critique",
        _route_error,
        {"error": "handle_error", "ok": END},
    )
    graph.add_edge("handle_error", END)
    return graph.compile()


def compile_end_graph():
    """Compile the subgraph for session finalization."""

    graph = StateGraph(PhaseBState)
    graph.add_node("end_session", end_session)
    graph.add_node("handle_error", handle_error)

    graph.set_entry_point("end_session")
    graph.add_conditional_edges(
        "end_session",
        _route_error,
        {"error": "handle_error", "ok": END},
    )
    graph.add_edge("handle_error", END)
    return graph.compile()


# Pre-compiled graph instances
prompt_graph = compile_prompt_graph()
critique_graph = compile_critique_graph()
end_graph = compile_end_graph()
