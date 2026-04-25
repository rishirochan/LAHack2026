# LAHacks 2026 Backend Setup

## AI Integration Prerequisites

The backend now has a shared AI integration layer under `backend/shared/ai` so every backend module can import the same provider configuration and clients.

### 1) Install Dependencies

Use your Python package workflow to install dependencies from `pyproject.toml`.

### 2) Configure Environment Variables

Copy `.env.example` to `.env`, then fill in real values:

- `OPENROUTER_API_KEY`
- `OPENROUTER_MODEL_GEMMA`
- `OPENROUTER_MODEL_HAIKU`
- `ELEVENLABS_API_KEY`
- `ELEVENLABS_DEFAULT_VOICE_ID`
- `ELEVENLABS_STT_MODEL` (default `scribe_v1` is prefilled)

`OPENROUTER_BASE_URL` defaults to `https://openrouter.ai/api/v1`.

### 3) Shared Imports

Use these shared entrypoints anywhere in backend code:

- `from backend.shared.ai import get_settings, validate_settings`
- `from backend.shared.ai import get_ai_service`

`get_ai_service()` gives access to:

- OpenRouter Gemma chat model
- OpenRouter Haiku chat model
- ElevenLabs client (TTS/STT ready)
