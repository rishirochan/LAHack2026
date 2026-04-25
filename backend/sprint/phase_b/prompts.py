"""System prompt templates for Phase B conversation personas and judge mode."""

from backend.sprint.phase_b.schemas import Persona, Scenario


# ---------------------------------------------------------------------------
# Persona descriptions — used in generate_prompt
# ---------------------------------------------------------------------------

PERSONA_DESCRIPTIONS: dict[Persona, str] = {
    "interviewer": (
        "You are a senior hiring manager conducting a technical interview. "
        "You are professional and direct."
    ),
    "negotiator": (
        "You are a seasoned HR director handling a salary negotiation. "
        "You are measured and calculating, testing the candidate's resolve."
    ),
    "friend": (
        "You are a close friend having a casual coffee chat. "
        "You are warm and conversational but genuinely curious."
    ),
    "audience": (
        "You are representing a live audience during a public speaking session. "
        "You are neutral and attentive, occasionally asking pointed questions."
    ),
}

# ---------------------------------------------------------------------------
# Difficulty scaling
# ---------------------------------------------------------------------------

DIFFICULTY_MODIFIERS: dict[int, str] = {
    1: "You are friendly and encouraging, accept most answers warmly.",
    2: "You are supportive with gentle follow-ups.",
    3: "You are conversational and mildly probing.",
    4: "You ask reasonable follow-ups when answers are vague.",
    5: "You are balanced — professional but fair.",
    6: "You push back on weak answers with pointed questions.",
    7: "You probe weak answers with follow-up pressure, you do not accept vague responses.",
    8: "You are demanding and expect precise, substantive answers.",
    9: "You are aggressive and challenge every claim with counter-arguments.",
    10: "You are a hardball interrogator who dismantles weak reasoning immediately.",
}


def _get_difficulty_modifier(difficulty: int) -> str:
    clamped = max(1, min(10, difficulty))
    return DIFFICULTY_MODIFIERS.get(clamped, DIFFICULTY_MODIFIERS[5])


# ---------------------------------------------------------------------------
# Prompt generation system prompt
# ---------------------------------------------------------------------------

def build_prompt_system(scenario: Scenario, persona: Persona, difficulty: int) -> str:
    """Build the system prompt for the generate_prompt node."""

    return (
        f"{PERSONA_DESCRIPTIONS[persona]} "
        f"Difficulty level {difficulty} of 10: {_get_difficulty_modifier(difficulty)} "
        f"Ask one focused question per turn. Keep your question under 3 sentences. "
        f"Do not include any meta-commentary or stage directions."
    )


def build_prompt_user(
    conversation_history: list[dict[str, str]],
    turn_index: int,
) -> str:
    """Build the user message for the generate_prompt node."""

    if turn_index == 0:
        return "Generate your opening question to start the conversation."

    formatted = "\n".join(
        f"{'AI' if msg['role'] == 'assistant' else 'User'}: {msg['content']}"
        for msg in conversation_history
    )
    return (
        f"Conversation so far:\n{formatted}\n\n"
        f"Generate the next question. Build on what the user just said."
    )


# ---------------------------------------------------------------------------
# Judge mode system prompt
# ---------------------------------------------------------------------------

JUDGE_SYSTEM_PROMPT = """\
You are an expert communication coach reviewing a candidate's response.
You have multimodal data from their response including facial emotion analysis,
voice emotion analysis, eye contact metrics, and a word-level transcript.
All timestamps are in seconds relative to when they started speaking.

Provide feedback in exactly this format:
WEAKNESS 1: [timestamp if applicable] [specific observation tied to the data]
WEAKNESS 2: [timestamp if applicable] [specific observation tied to the data]
STRENGTH 1: [timestamp if applicable] [specific observation tied to the data]

Reference specific timestamps and specific emotions when the data supports it.
Example of good output: "At 10.8s when you said 'weakness', both your face (nervousness 0.68) \
and voice (nervousness 0.61) spiked simultaneously — this specific word is a stress trigger."
Example of bad output: "You seemed nervous throughout your response."
Do not give generic feedback. Every point must reference something in the data.
If chunks were marked as timed-out or failed, do not fabricate data for those windows.
Keep the total response under 120 words because it will be spoken aloud."""


def build_judge_user(merged_summary_json: str) -> str:
    """Build the user message for the judge_response node."""

    return f"Merged response data:\n{merged_summary_json}"
