"""Constants used by Phase C deterministic scoring and validation."""

PHASE_C_MIN_SECONDS = 2
PHASE_C_MAX_SECONDS = 45
PHASE_C_CHUNK_TIMEOUT_SECONDS = 10
PHASE_C_CHUNK_POLL_SECONDS = 2

RETRY_TOO_SHORT_MESSAGE = "That recording was too short. Try again with a full response."
RETRY_EMPTY_MESSAGE = "The recording was empty. Check camera and microphone access."
RETRY_INVALID_CHUNKS_MESSAGE = "Some recording chunks were missing or overlapped. Please record that turn again."
RETRY_TOO_LONG_MESSAGE = f"That response ran too long. Keep it under {PHASE_C_MAX_SECONDS} seconds."

FILLER_WORDS = ("like", "um", "you know", "basically", "literally")
FILLER_SINGLE_WORDS = {word for word in FILLER_WORDS if " " not in word}
FILLER_MULTI_WORDS = tuple(word for word in FILLER_WORDS if " " in word)

PACE_WPM_MIN = 120
PACE_WPM_MAX = 170
PACE_STABLE_DELTA = 10

EMOTIONAL_FLATNESS_THRESHOLD_MS = 15000
NERVOUSNESS_THRESHOLD_RATIO = 0.60
NERVOUS_EMOTIONS = {"fear", "nervousness"}
NEUTRAL_EMOTION = "neutral"

COMMON_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "for", "from",
    "has", "he", "i", "if", "in", "is", "it", "its", "me", "my", "of", "on",
    "or", "our", "she", "so", "that", "the", "their", "them", "they", "this",
    "to", "was", "we", "were", "with", "you", "your",
}
