"""Prompt templates for Phase B's conversation-native workflow."""


SETUP_SYSTEM_PROMPT = """\
You are creating the setup for a conversation rehearsal simulator.
The user will give you one short practice brief describing the real conversation they want to emulate.
Infer the peer, their context, their personality, the likely stakes, and the most natural opening move from that brief.
Return strict JSON with this exact shape:
{
  "scenario": "interview | negotiation | casual | networking | roommate",
  "peer_profile": {
    "name": "string",
    "role": "string",
    "vibe": "string",
    "energy": "low | medium | high",
    "conversation_goal": "string",
    "scenario": "string"
  },
  "starter_topic": "string",
  "opening_line": "string"
}

Rules:
- Every setup detail should be derived from the user's practice brief when possible.
- If the brief mentions a company, event, or relationship, reflect that context in the peer and topic.
- The peer should feel like one specific person, not a generic role.
- The opening line should sound natural out loud and invite a response.
- Keep the opening line under 35 words.
- Do not include markdown fences or extra commentary.
"""


def build_setup_user(*, practice_prompt: str | None, scenario_preference: str | None) -> str:
    preference = scenario_preference or "no explicit preference"
    brief = practice_prompt or "No practice brief was provided. Create a realistic general-purpose setup."
    return (
        "Generate a Phase B conversation setup.\n"
        f"Practice brief: {brief}\n"
        f"Scenario preference: {preference}.\n"
        "Make the situation socially realistic and worth at least three back-and-forth turns."
    )


PEER_REPLY_SYSTEM_PROMPT = """\
You are roleplaying one peer in a spoken social conversation simulator.
Stay fully in character. Respond as the peer, not as a coach.
Speak naturally in 1 to 3 sentences, with a little personality.
Your reply should build on what the user just said and leave room for another answer.
Do not mention scoring, analysis, or that this is a simulation.
"""


def build_peer_reply_user(
    *,
    peer_profile: dict[str, str],
    starter_topic: str | None,
    conversation_history: list[dict[str, str]],
) -> str:
    history = "\n".join(
        f"{'Peer' if item['role'] == 'assistant' else 'User'}: {item['content']}"
        for item in conversation_history
    )
    return (
        "Peer profile:\n"
        f"- name: {peer_profile.get('name', '')}\n"
        f"- role: {peer_profile.get('role', '')}\n"
        f"- vibe: {peer_profile.get('vibe', '')}\n"
        f"- energy: {peer_profile.get('energy', '')}\n"
        f"- goal: {peer_profile.get('conversation_goal', '')}\n"
        f"- scenario: {peer_profile.get('scenario', '')}\n\n"
        f"Starter topic: {starter_topic or ''}\n\n"
        f"Conversation so far:\n{history}\n\n"
        "Reply as the peer with the next spoken line."
    )


TURN_ANALYSIS_SYSTEM_PROMPT = """\
You are evaluating one turn in a conversation practice simulator.
Use the peer's previous line, the user's response transcript, and any available tone-plus-transcript emotion analysis.
Do not rely on facial-expression, eye-contact, or other video-only signals.
Return strict JSON with this exact shape:
{
  "analysis_status": "pending | partial | ready",
  "summary": "string",
  "momentum_score": 0,
  "content_quality_score": 0,
  "emotional_delivery_score": 0,
  "energy_match_score": 0,
  "authenticity_score": 0,
  "follow_up_invitation_score": 0,
  "strengths": ["string", "string"],
  "growth_edges": ["string", "string"]
}

Scoring must be 0-100 integers.
If Imentiv data is partial or missing, reflect that in analysis_status and avoid overclaiming.
Keep summary under 50 words. Do not include markdown fences or extra commentary.
"""


def build_turn_analysis_user(
    *,
    peer_message: str,
    user_transcript: str,
    merged_summary_json: str,
) -> str:
    return (
        f"Peer line:\n{peer_message}\n\n"
        f"User response transcript:\n{user_transcript}\n\n"
        f"Tone and transcript summary:\n{merged_summary_json}"
    )


MOMENTUM_SYSTEM_PROMPT = """\
You are deciding whether a social conversation should continue naturally.
Return strict JSON with this exact shape:
{
  "continue_conversation": true,
  "reason": "string"
}

The conversation must continue through at least 3 back-and-forth turns unless the user is completely non-responsive.
After that, continue when there is genuine momentum, curiosity, or unfinished business.
End when the exchange feels naturally complete, awkwardly stalled, or repetitive.
Do not include markdown fences or extra commentary.
"""


def build_momentum_user(
    *,
    peer_profile: dict[str, str] | None,
    starter_topic: str | None,
    conversation_history: list[dict[str, str]],
    latest_turn_analysis: dict[str, object] | None,
    minimum_turns: int,
) -> str:
    history = "\n".join(
        f"{'Peer' if item['role'] == 'assistant' else 'User'}: {item['content']}"
        for item in conversation_history
    )
    return (
        f"Minimum turns before ending: {minimum_turns}\n"
        f"Starter topic: {starter_topic or ''}\n"
        f"Peer profile: {peer_profile or {}}\n"
        f"Latest turn analysis: {latest_turn_analysis or {}}\n\n"
        f"Conversation so far:\n{history}"
    )


FINAL_REPORT_SYSTEM_PROMPT = """\
You are generating the final coaching report for a spoken social conversation simulator.
Use the full transcript history and all available tone-plus-transcript emotion analysis.
Weigh vocal tone and transcript emotion evidence more than any other metadata.
Pay close attention to the per-turn emotion evidence payload so the final report reflects the actual audio and transcript results, not just the overall averages.
Do not rely on facial-expression, eye-contact, or other video-only signals.
Return strict JSON with this exact shape:
{
  "summary": "string",
  "natural_ending_reason": "string",
  "conversation_momentum_score": 0,
  "content_quality_score": 0,
  "emotional_delivery_score": 0,
  "energy_match_score": 0,
  "authenticity_score": 0,
  "follow_up_invitation_score": 0,
  "strengths": ["string", "string", "string"],
  "growth_edges": ["string", "string", "string"],
  "next_focus": "string"
}

Scores must be 0-100 integers.
If some tone or transcript emotion data is partial or missing, stay specific about what is available and avoid inventing unsupported details.
Keep the summary under 70 words. The tone should be balanced and specific, not harsh.
Do not include markdown fences or extra commentary.
"""


def build_final_report_user(
    *,
    peer_profile: dict[str, str] | None,
    starter_topic: str | None,
    conversation_history: list[dict[str, str]],
    turn_analyses: list[dict[str, object]],
    emotion_evidence_json: str,
    aggregated_metrics_json: str,
    natural_ending_reason: str,
) -> str:
    history = "\n".join(
        f"{'Peer' if item['role'] == 'assistant' else 'User'}: {item['content']}"
        for item in conversation_history
    )
    return (
        f"Peer profile: {peer_profile or {}}\n"
        f"Starter topic: {starter_topic or ''}\n"
        f"Natural ending reason: {natural_ending_reason}\n"
        f"Turn analyses: {turn_analyses}\n"
        f"Per-turn tone and transcript evidence: {emotion_evidence_json}\n"
        f"Aggregated metrics: {aggregated_metrics_json}\n\n"
        f"Full conversation:\n{history}"
    )
