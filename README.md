# LAHacks 2026 Backend Setup

## AI Integration Prerequisites

The backend now has a shared AI integration layer under `backend/shared/ai` so every backend module can import the same provider configuration and clients.

### 1) Install Dependencies

Use your Python package workflow to install dependencies from `pyproject.toml`.

### 2) Configure Environment Variables

Copy `.env.example` to `.env`, then fill in real values:

- `OPENROUTER_API_KEY` (optional unless using the legacy OpenRouter facade)
- `OPENROUTER_MODEL_GEMMA`
- `OPENROUTER_MODEL_HAIKU`
- `GOOGLE_AI_API_KEY`
- `GOOGLE_GEMMA_MODEL` (defaults to `gemma-4`)
- `ELEVENLABS_API_KEY`
- `ELEVENLABS_DEFAULT_VOICE_ID`
- `ELEVENLABS_STT_MODEL` (default `scribe_v1` is prefilled)
- `ELEVENLABS_TTS_MODEL` (default `eleven_multilingual_v2` is prefilled)
- `IMENTIV_API_KEY`
- `IMENTIV_BASE_URL` (defaults to `https://api.imentiv.ai/v2`)
- `MONGODB_ENABLED` (set `true` when using MongoDB Atlas persistence)
- `MONGODB_URI` (your MongoDB Atlas connection string; keep this in local `.env`)
- `MONGODB_DB_NAME` (defaults to `voxcoach`)
- `NEXT_PUBLIC_API_URL` (frontend backend HTTP URL)
- `NEXT_PUBLIC_WS_URL` (frontend backend websocket URL)

`OPENROUTER_BASE_URL` defaults to `https://openrouter.ai/api/v1`.

### 3) Shared Imports

Use these shared entrypoints anywhere in backend code:

- `from backend.shared.ai import get_settings, validate_settings`
- `from backend.shared.ai import get_ai_service`

`get_ai_service()` gives access to:

- OpenRouter Gemma chat model
- OpenRouter Haiku chat model
- ElevenLabs client (TTS/STT ready)

Phase A Emotion Drills uses Google AI/Gemma for both scenario generation and critique generation, ElevenLabs for speech-to-text and TTS playback, and Imentiv for video/audio emotion analysis.

### 4) MongoDB Persistence

MongoDB stores durable practice-session history for the dashboard while live websocket coordination remains in memory. Create a MongoDB Atlas database user with read/write access, allow your current IP in Network Access, then paste your Atlas URI into `.env` as `MONGODB_URI`.
