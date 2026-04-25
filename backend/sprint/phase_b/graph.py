"""LangGraph workflow for Phase B's live conversation experience."""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph

from backend.shared.ai import get_ai_service
from backend.sprint.phase_b.elevenlabs import stream_tts_chunks
from backend.sprint.phase_b.gemma import generate_text
from backend.sprint.phase_b.prompts import (
    FINAL_REPORT_SYSTEM_PROMPT,
    MOMENTUM_SYSTEM_PROMPT,
    PEER_REPLY_SYSTEM_PROMPT,
    SETUP_SYSTEM_PROMPT,
    TURN_ANALYSIS_SYSTEM_PROMPT,
    build_final_report_user,
    build_momentum_user,
    build_peer_reply_user,
    build_setup_user,
    build_turn_analysis_user,
)
from backend.sprint.phase_b.schemas import PhaseBState, TurnAnalysis
from backend.sprint.phase_b.session_manager import get_phase_b_manager


async def generate_peer_turn(state: PhaseBState, config: RunnableConfig) -> dict[str, Any]:
    """Create the next peer message, generating persona/topic on first use."""

    session_id = _session_id(config)
    manager = get_phase_b_manager()
    session_state = manager.get_state(session_id)

    try:
        if not session_state.get("peer_profile"):
            setup_fallback = {
                "scenario": session_state.get("scenario_preference") or "casual",
                "peer_profile": {
                    "name": "Jordan",
                    "role": "new classmate",
                    "vibe": "friendly but observant",
                    "energy": "medium",
                    "conversation_goal": "get to know the user and see whether the conversation keeps flowing",
                    "scenario": session_state.get("scenario_preference") or "casual",
                },
                "starter_topic": "how the week has been going and what has felt energizing lately",
                "opening_line": "Hey, I am Jordan. What has been the most interesting part of your week so far?",
            }
            setup = await _generate_json(
                system_prompt=SETUP_SYSTEM_PROMPT,
                user_prompt=build_setup_user(
                    difficulty=session_state["difficulty"],
                    scenario_preference=session_state.get("scenario_preference"),
                ),
                fallback=setup_fallback,
                temperature=0.8,
                max_tokens=500,
            )
            peer_profile = _coerce_peer_profile(setup.get("peer_profile"), setup_fallback["peer_profile"])
            scenario = str(setup.get("scenario") or peer_profile.get("scenario") or "casual")
            starter_topic = str(setup.get("starter_topic") or setup_fallback["starter_topic"])
            opening_line = str(setup.get("opening_line") or setup_fallback["opening_line"])
            manager.initialize_context(
                session_id,
                scenario=scenario,
                peer_profile=peer_profile,
                starter_topic=starter_topic,
                opening_line=opening_line,
            )
            await _send_event(
                config,
                "session_initialized",
                {
                    "scenario": scenario,
                    "peer_profile": peer_profile,
                    "starter_topic": starter_topic,
                    "opening_line": opening_line,
                },
            )
            prompt_text = opening_line
        else:
            peer_profile = session_state["peer_profile"] or {}
            fallback_prompt = "Can you tell me a little more about that?"
            prompt_text = await generate_text(
                ai_service=get_ai_service(),
                system_prompt=PEER_REPLY_SYSTEM_PROMPT,
                user_prompt=build_peer_reply_user(
                    peer_profile=peer_profile,
                    starter_topic=session_state.get("starter_topic"),
                    conversation_history=session_state["conversation_history"],
                    difficulty=session_state["difficulty"],
                ),
                temperature=0.8,
                max_tokens=120,
            )
            prompt_text = (prompt_text or fallback_prompt).strip()
            if not prompt_text:
                prompt_text = fallback_prompt

        manager.start_turn(session_id, prompt_text)
        await _send_event(
            config,
            "prompt_generated",
            {"prompt_text": prompt_text, "turn_index": session_state["turn_index"]},
        )
        return {"error": None}
    except Exception as error:
        return {"error": f"Could not generate the next peer turn: {error}"}


async def merge_summary(state: PhaseBState, config: RunnableConfig) -> dict[str, Any]:
    """Assemble per-turn chunk and transcript context without blocking on pending analysis."""

    session_id = _session_id(config)
    manager = get_phase_b_manager()
    session_state = manager.get_state(session_id)
    current_turn = session_state.get("current_turn")

    if current_turn is None:
        return {"error": "No active turn for merge_summary."}

    await _send_event(config, "processing_stage", {"stage": "Preparing turn analysis"})

    words = current_turn.get("transcript_words") or []
    chunks = current_turn["chunks"]

    chunk_summaries: list[dict[str, Any]] = []
    for chunk in chunks:
        t_start = chunk["start_ms"]
        t_end = chunk["end_ms"]
        segment_words = [
            word
            for word in words
            if word.get("start", 0) * 1000 >= t_start and word.get("start", 0) * 1000 < t_end
        ]
        segment_text = " ".join(str(word.get("word") or "") for word in segment_words).strip()
        video_ems = chunk.get("video_emotions") or []
        audio_ems = chunk.get("audio_emotions") or []
        dominant_video = _dominant_emotion(video_ems)
        dominant_audio = _dominant_emotion(audio_ems)
        mp = chunk.get("mediapipe_metrics") or {}

        chunk_summaries.append(
            {
                "t_start": t_start,
                "t_end": t_end,
                "status": chunk["status"],
                "transcript_segment": segment_text,
                "dominant_video_emotion": dominant_video.get("emotion_type") if dominant_video else None,
                "video_confidence": dominant_video.get("confidence") if dominant_video else None,
                "dominant_audio_emotion": dominant_audio.get("emotion_type") if dominant_audio else None,
                "audio_confidence": dominant_audio.get("confidence") if dominant_audio else None,
                "eye_contact_pct": mp.get("avg_eye_contact_score", 0) * 100 if mp else 0,
            }
        )

    eye_contacts = [chunk["eye_contact_pct"] for chunk in chunk_summaries if chunk["eye_contact_pct"]]
    status_counts = Counter(chunk["status"] for chunk in chunk_summaries)
    merged = {
        "peer_profile": session_state.get("peer_profile"),
        "starter_topic": session_state.get("starter_topic"),
        "question_asked": current_turn.get("prompt_text", ""),
        "full_transcript": current_turn.get("transcript") or "",
        "transcript_words": [
            {
                "word": word["word"],
                "start_ms": int(word.get("start", 0) * 1000),
                "end_ms": int(word.get("end", 0) * 1000),
            }
            for word in words
        ],
        "chunks": chunk_summaries,
        "overall": {
            "avg_eye_contact_pct": round(sum(eye_contacts) / len(eye_contacts), 1) if eye_contacts else 0,
            "dominant_video_emotion": _most_common(
                [chunk["dominant_video_emotion"] for chunk in chunk_summaries]
            ),
            "dominant_audio_emotion": _most_common(
                [chunk["dominant_audio_emotion"] for chunk in chunk_summaries]
            ),
            "status_counts": dict(status_counts),
            "chunks_failed": int(status_counts.get("failed") or 0),
            "chunks_timed_out": int(status_counts.get("timed_out") or 0),
            "analysis_ready": status_counts.get("pending", 0) == 0 and status_counts.get("processing", 0) == 0,
        },
    }
    current_turn["merged_summary"] = merged
    manager.persist_state(session_id)
    return {"error": None}


async def analyze_turn(state: PhaseBState, config: RunnableConfig) -> dict[str, Any]:
    """Generate local-context turn analysis for the completed user response."""

    session_id = _session_id(config)
    manager = get_phase_b_manager()
    session_state = manager.get_state(session_id)
    current_turn = session_state.get("current_turn")

    if current_turn is None:
        return {"error": "No active turn for analyze_turn."}

    merged = current_turn.get("merged_summary") or {}
    transcript = (current_turn.get("transcript") or "").strip()
    if not transcript:
        return {"error": "Transcript was empty for this turn."}

    await _send_event(config, "processing_stage", {"stage": "Scoring the turn"})

    status_counts = (merged.get("overall") or {}).get("status_counts") or {}
    pending_count = int(status_counts.get("pending") or 0) + int(status_counts.get("processing") or 0)
    analysis_status = "ready" if pending_count == 0 else "partial"
    fallback = _fallback_turn_analysis(transcript=transcript, analysis_status=analysis_status)

    try:
        turn_analysis = await _generate_json(
            system_prompt=TURN_ANALYSIS_SYSTEM_PROMPT,
            user_prompt=build_turn_analysis_user(
                peer_message=current_turn.get("prompt_text") or "",
                user_transcript=transcript,
                merged_summary_json=json.dumps(merged, ensure_ascii=True),
            ),
            fallback=fallback,
            temperature=0.4,
            max_tokens=400,
        )
    except Exception:
        turn_analysis = fallback

    normalized = _coerce_turn_analysis(turn_analysis, analysis_status=analysis_status, fallback=fallback)
    manager.store_turn_analysis(
        session_id,
        current_turn["turn_index"],
        merged_summary=merged,
        turn_analysis=normalized,
        analysis_status=normalized["analysis_status"],
    )
    await _send_event(
        config,
        "turn_analysis_ready",
        {"turn_index": current_turn["turn_index"], "turn_analysis": normalized},
    )
    return {"error": None}


async def decide_momentum(session_id: str) -> dict[str, Any]:
    """Judge whether the conversation still has natural momentum."""

    manager = get_phase_b_manager()
    state = manager.get_state(session_id)
    if len(state["turns"]) < state["minimum_turns"]:
        decision = {"continue_conversation": True, "reason": "Minimum turn count not reached yet."}
        manager.store_momentum_decision(session_id, decision)
        return decision

    if len(state["turns"]) >= state["max_turns"]:
        decision = {
            "continue_conversation": False,
            "reason": "Maximum turn count reached, so the exchange should wrap up cleanly.",
        }
        manager.store_momentum_decision(session_id, decision)
        return decision

    fallback = {
        "continue_conversation": True,
        "reason": "The conversation still sounds active and unfinished.",
    }
    latest_turn_analysis = state["turns"][-1].get("turn_analysis")
    try:
        decision = await _generate_json(
            system_prompt=MOMENTUM_SYSTEM_PROMPT,
            user_prompt=build_momentum_user(
                peer_profile=state.get("peer_profile"),
                starter_topic=state.get("starter_topic"),
                conversation_history=state["conversation_history"],
                latest_turn_analysis=latest_turn_analysis,
                minimum_turns=state["minimum_turns"],
            ),
            fallback=fallback,
            temperature=0.2,
            max_tokens=150,
        )
    except Exception:
        decision = fallback

    normalized = {
        "continue_conversation": bool(decision.get("continue_conversation", True)),
        "reason": str(decision.get("reason") or fallback["reason"]),
    }
    manager.store_momentum_decision(session_id, normalized)
    return normalized


async def generate_final_report(state: PhaseBState, config: RunnableConfig) -> dict[str, Any]:
    """Create the final session report from full context and accumulated analysis."""

    session_id = _session_id(config)
    manager = get_phase_b_manager()
    session_state = manager.get_state(session_id)
    turn_analyses = [
        turn.get("turn_analysis")
        for turn in session_state["turns"]
        if isinstance(turn.get("turn_analysis"), dict)
    ]
    natural_ending_reason = str(
        (session_state.get("momentum_decision") or {}).get("reason")
        or "The session was ended manually."
    )
    aggregated_metrics = _aggregate_final_metrics(session_state)
    fallback = _fallback_final_report(aggregated_metrics, natural_ending_reason)

    try:
        report = await _generate_json(
            system_prompt=FINAL_REPORT_SYSTEM_PROMPT,
            user_prompt=build_final_report_user(
                peer_profile=session_state.get("peer_profile"),
                starter_topic=session_state.get("starter_topic"),
                conversation_history=session_state["conversation_history"],
                turn_analyses=[analysis for analysis in turn_analyses if isinstance(analysis, dict)],
                aggregated_metrics_json=json.dumps(aggregated_metrics, ensure_ascii=True),
                natural_ending_reason=natural_ending_reason,
            ),
            fallback=fallback,
            temperature=0.4,
            max_tokens=700,
        )
    except Exception:
        report = fallback

    normalized = _coerce_final_report(report, fallback=fallback)
    manager.store_final_report(session_id, normalized)
    return {"error": None}


async def mark_session_complete(state: PhaseBState, config: RunnableConfig) -> dict[str, Any]:
    """Persist completion and emit the final websocket payload."""

    session_id = _session_id(config)
    manager = get_phase_b_manager()
    final_state = manager.end_session(session_id)
    await _send_event(
        config,
        "session_complete",
        {
            "session_id": session_id,
            "status": final_state["status"],
            "total_turns": len(final_state["turns"]),
            "final_report": final_state.get("final_report"),
        },
    )
    return {"error": None}


async def handle_error(state: PhaseBState, config: RunnableConfig) -> dict[str, Any]:
    message = state.get("error") or "Something went wrong during the conversation."
    await _send_event(config, "error", {"message": message})
    return {}


async def _stream_tts(config: RunnableConfig, audio_type: str, text: str) -> None:
    await _send_event(config, "tts_start", {"audio_type": audio_type, "text": text})
    async for chunk in stream_tts_chunks(ai_service=get_ai_service(), text=text):
        await _send_event(
            config,
            "audio_chunk",
            {"audio_type": audio_type, "chunk": chunk, "mime_type": "audio/mpeg"},
        )
    await _send_event(config, "tts_end", {"audio_type": audio_type})


async def stream_peer_tts(session_id: str) -> None:
    """Stream the current peer turn over the websocket."""

    state = get_phase_b_manager().get_state(session_id)
    current_turn = state.get("current_turn")
    if not current_turn or not current_turn.get("prompt_text"):
        return
    await _stream_tts(
        {"configurable": {"session_id": session_id}},
        "peer_message",
        str(current_turn["prompt_text"]),
    )


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


async def _generate_json(
    *,
    system_prompt: str,
    user_prompt: str,
    fallback: dict[str, Any],
    temperature: float,
    max_tokens: int,
) -> dict[str, Any]:
    text = await generate_text(
        ai_service=get_ai_service(),
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return _extract_json_object(text) or fallback


def _extract_json_object(text: str) -> dict[str, Any] | None:
    text = text.strip()
    if not text:
        return None
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            parsed = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None


def _coerce_peer_profile(value: Any, fallback: dict[str, str]) -> dict[str, str]:
    data = value if isinstance(value, dict) else {}
    return {
        "name": str(data.get("name") or fallback["name"]),
        "role": str(data.get("role") or fallback["role"]),
        "vibe": str(data.get("vibe") or fallback["vibe"]),
        "energy": str(data.get("energy") or fallback["energy"]),
        "conversation_goal": str(data.get("conversation_goal") or fallback["conversation_goal"]),
        "scenario": str(data.get("scenario") or fallback["scenario"]),
    }


def _fallback_turn_analysis(*, transcript: str, analysis_status: str) -> TurnAnalysis:
    length_bonus = min(len(transcript.split()) * 2, 20)
    base_score = 58 + length_bonus
    return {
        "analysis_status": "ready" if analysis_status == "ready" else "partial",
        "summary": "You kept the exchange moving, and the next step is making each answer a little more specific.",
        "momentum_score": min(base_score, 82),
        "content_quality_score": min(base_score - 4, 80),
        "emotional_delivery_score": 62,
        "energy_match_score": 60,
        "authenticity_score": 68,
        "follow_up_invitation_score": 57,
        "strengths": [
            "You gave the peer something concrete to react to.",
            "Your response sounded natural instead of scripted.",
        ],
        "growth_edges": [
            "Add one vivid detail so the reply feels more memorable.",
            "End with a thought or question that keeps the conversation easy to continue.",
        ],
    }


def _coerce_turn_analysis(value: Any, *, analysis_status: str, fallback: TurnAnalysis) -> TurnAnalysis:
    data = value if isinstance(value, dict) else {}
    return {
        "analysis_status": str(data.get("analysis_status") or analysis_status or fallback["analysis_status"]),
        "summary": str(data.get("summary") or fallback["summary"]),
        "momentum_score": _score(data.get("momentum_score"), fallback["momentum_score"]),
        "content_quality_score": _score(data.get("content_quality_score"), fallback["content_quality_score"]),
        "emotional_delivery_score": _score(
            data.get("emotional_delivery_score"),
            fallback["emotional_delivery_score"],
        ),
        "energy_match_score": _score(data.get("energy_match_score"), fallback["energy_match_score"]),
        "authenticity_score": _score(data.get("authenticity_score"), fallback["authenticity_score"]),
        "follow_up_invitation_score": _score(
            data.get("follow_up_invitation_score"),
            fallback["follow_up_invitation_score"],
        ),
        "strengths": _string_list(data.get("strengths"), fallback["strengths"]),
        "growth_edges": _string_list(data.get("growth_edges"), fallback["growth_edges"]),
    }


def _aggregate_final_metrics(state: PhaseBState) -> dict[str, Any]:
    turn_analyses = [turn.get("turn_analysis") or {} for turn in state["turns"]]
    all_chunks = [
        chunk
        for turn in state["turns"]
        for chunk in turn.get("chunks") or []
        if isinstance(chunk, dict)
    ]
    eye_contacts = [
        float((chunk.get("mediapipe_metrics") or {}).get("avg_eye_contact_score", 0)) * 100
        for chunk in all_chunks
        if isinstance(chunk.get("mediapipe_metrics"), dict)
    ]
    return {
        "turn_count": len(state["turns"]),
        "analysis_statuses": [turn.get("analysis_status") for turn in state["turns"]],
        "avg_momentum_score": _average(
            [analysis.get("momentum_score") for analysis in turn_analyses if isinstance(analysis, dict)]
        ),
        "avg_content_quality_score": _average(
            [analysis.get("content_quality_score") for analysis in turn_analyses if isinstance(analysis, dict)]
        ),
        "avg_emotional_delivery_score": _average(
            [analysis.get("emotional_delivery_score") for analysis in turn_analyses if isinstance(analysis, dict)]
        ),
        "avg_energy_match_score": _average(
            [analysis.get("energy_match_score") for analysis in turn_analyses if isinstance(analysis, dict)]
        ),
        "avg_authenticity_score": _average(
            [analysis.get("authenticity_score") for analysis in turn_analyses if isinstance(analysis, dict)]
        ),
        "avg_follow_up_invitation_score": _average(
            [analysis.get("follow_up_invitation_score") for analysis in turn_analyses if isinstance(analysis, dict)]
        ),
        "avg_eye_contact_pct": _average(eye_contacts),
        "dominant_video_emotion": _most_common(
            [
                (_dominant_emotion(chunk.get("video_emotions") or []) or {}).get("emotion_type")
                for chunk in all_chunks
            ]
        ),
        "dominant_audio_emotion": _most_common(
            [
                (_dominant_emotion(chunk.get("audio_emotions") or []) or {}).get("emotion_type")
                for chunk in all_chunks
            ]
        ),
        "chunk_status_counts": dict(Counter(str(chunk.get("status") or "unknown") for chunk in all_chunks)),
    }


def _fallback_final_report(metrics: dict[str, Any], natural_ending_reason: str) -> dict[str, Any]:
    return {
        "summary": "You kept the conversation alive and gave the peer enough to work with, with room to become more pointed and inviting.",
        "natural_ending_reason": natural_ending_reason,
        "conversation_momentum_score": _score(metrics.get("avg_momentum_score"), 68),
        "content_quality_score": _score(metrics.get("avg_content_quality_score"), 66),
        "emotional_delivery_score": _score(metrics.get("avg_emotional_delivery_score"), 64),
        "energy_match_score": _score(metrics.get("avg_energy_match_score"), 63),
        "authenticity_score": _score(metrics.get("avg_authenticity_score"), 70),
        "follow_up_invitation_score": _score(metrics.get("avg_follow_up_invitation_score"), 61),
        "strengths": [
            "You stayed engaged long enough for the exchange to feel real.",
            "Your responses generally sounded conversational instead of memorized.",
            "There was enough momentum for the peer to keep responding naturally.",
        ],
        "growth_edges": [
            "Offer one sharper detail in each answer so your ideas land faster.",
            "Match the peer's energy more deliberately when the topic becomes more animated.",
            "Invite the next turn a little more clearly instead of ending flat.",
        ],
        "next_focus": "Practice answering with one specific detail and one easy follow-up hook.",
    }


def _coerce_final_report(value: Any, *, fallback: dict[str, Any]) -> dict[str, Any]:
    data = value if isinstance(value, dict) else {}
    return {
        "summary": str(data.get("summary") or fallback["summary"]),
        "natural_ending_reason": str(data.get("natural_ending_reason") or fallback["natural_ending_reason"]),
        "conversation_momentum_score": _score(
            data.get("conversation_momentum_score"),
            fallback["conversation_momentum_score"],
        ),
        "content_quality_score": _score(data.get("content_quality_score"), fallback["content_quality_score"]),
        "emotional_delivery_score": _score(
            data.get("emotional_delivery_score"),
            fallback["emotional_delivery_score"],
        ),
        "energy_match_score": _score(data.get("energy_match_score"), fallback["energy_match_score"]),
        "authenticity_score": _score(data.get("authenticity_score"), fallback["authenticity_score"]),
        "follow_up_invitation_score": _score(
            data.get("follow_up_invitation_score"),
            fallback["follow_up_invitation_score"],
        ),
        "strengths": _string_list(data.get("strengths"), fallback["strengths"]),
        "growth_edges": _string_list(data.get("growth_edges"), fallback["growth_edges"]),
        "next_focus": str(data.get("next_focus") or fallback["next_focus"]),
    }


def _score(value: Any, fallback: int) -> int:
    try:
        return max(0, min(100, int(round(float(value)))))
    except (TypeError, ValueError):
        return fallback


def _string_list(value: Any, fallback: list[str]) -> list[str]:
    if not isinstance(value, list):
        return fallback
    items = [str(item).strip() for item in value if str(item).strip()]
    return items or fallback


def _average(values: list[Any]) -> int | None:
    numbers: list[float] = []
    for value in values:
        try:
            if value is None:
                continue
            numbers.append(float(value))
        except (TypeError, ValueError):
            continue
    if not numbers:
        return None
    return int(round(sum(numbers) / len(numbers)))


def _dominant_emotion(emotions: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not emotions:
        return None
    return max(emotions, key=lambda event: float(event.get("confidence") or 0))


def _most_common(values: list[Any]) -> str | None:
    filtered = [str(value) for value in values if value]
    if not filtered:
        return None
    return Counter(filtered).most_common(1)[0][0]


def compile_prompt_graph():
    graph = StateGraph(PhaseBState)
    graph.add_node("generate_peer_turn", generate_peer_turn)
    graph.add_node("handle_error", handle_error)
    graph.set_entry_point("generate_peer_turn")
    graph.add_conditional_edges(
        "generate_peer_turn",
        _route_error,
        {"error": "handle_error", "ok": END},
    )
    graph.add_edge("handle_error", END)
    return graph.compile()


def compile_critique_graph():
    graph = StateGraph(PhaseBState)
    graph.add_node("merge_summary", merge_summary)
    graph.add_node("analyze_turn", analyze_turn)
    graph.add_node("handle_error", handle_error)
    graph.set_entry_point("merge_summary")
    graph.add_conditional_edges(
        "merge_summary",
        _route_error,
        {"error": "handle_error", "ok": "analyze_turn"},
    )
    graph.add_conditional_edges(
        "analyze_turn",
        _route_error,
        {"error": "handle_error", "ok": END},
    )
    graph.add_edge("handle_error", END)
    return graph.compile()


def compile_end_graph():
    graph = StateGraph(PhaseBState)
    graph.add_node("generate_final_report", generate_final_report)
    graph.add_node("mark_session_complete", mark_session_complete)
    graph.add_node("handle_error", handle_error)
    graph.set_entry_point("generate_final_report")
    graph.add_conditional_edges(
        "generate_final_report",
        _route_error,
        {"error": "handle_error", "ok": "mark_session_complete"},
    )
    graph.add_conditional_edges(
        "mark_session_complete",
        _route_error,
        {"error": "handle_error", "ok": END},
    )
    graph.add_edge("handle_error", END)
    return graph.compile()


prompt_graph = compile_prompt_graph()
critique_graph = compile_critique_graph()
end_graph = compile_end_graph()
