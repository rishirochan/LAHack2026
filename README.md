# LAHacks 2026 Demo Setup

## Quick Start

Run the backend and frontend in separate terminals from the repository root.

```powershell
uv sync
uv run uvicorn backend.sprint.api:app --reload --host 0.0.0.0 --port 8000
```

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`.

## Environment

Copy `.env.example` to `.env`, then fill in real values. The frontend defaults to `http://localhost:8000` and `ws://localhost:8000`; for different hosts, copy `frontend/.env.example` to `frontend/.env.local`.

- `OPENROUTER_API_KEY`
- `OPENROUTER_MODEL_GEMMA`
- `OPENROUTER_MODEL_HAIKU`
- `ELEVENLABS_API_KEY`
- `ELEVENLABS_DEFAULT_VOICE_ID`
- `ELEVENLABS_STT_MODEL` (default `scribe_v1` is prefilled)
- `ELEVENLABS_TTS_MODEL` (default `eleven_multilingual_v2` is prefilled)
- `IMENTIV_API_KEY`
- `IMENTIV_BASE_URL` (defaults to `https://api.imentiv.ai/`)
- `IMENTIV_USER_CONSENT_VERSION` (defaults to `2.0.0`)
- `IMENTIV_MOCK=false` for live Imentiv analysis during the demo
- `MONGODB_ENABLED` (set `true` when using MongoDB Atlas persistence)
- `MONGODB_URI` (your MongoDB Atlas connection string; keep this in local `.env`)
- `MONGODB_DB_NAME` (defaults to `voxcoach`)
- `NEXT_PUBLIC_API_URL` (frontend backend HTTP URL)
- `NEXT_PUBLIC_WS_URL` (frontend backend websocket URL)

`OPENROUTER_BASE_URL` defaults to `https://openrouter.ai/api/v1`.

## Integration Notes

The backend has a shared AI integration layer under `backend/shared/ai` and a backend-only Imentiv wrapper under `backend/shared/imentiv.py`.

- `from backend.shared.ai import get_settings, validate_settings`
- `from backend.shared.ai import get_ai_service`
- `from backend.shared.imentiv import get_imentiv_client`

Phase A, B, and C keep Imentiv API calls on the backend. Recordings are saved server-side, uploaded to Imentiv with `X-API-Key`, and normalized before being returned through existing session status/result endpoints and websocket events.

## MongoDB Persistence

MongoDB stores durable practice-session history for the dashboard while live websocket coordination remains in memory. Create a MongoDB Atlas database user with read/write access, allow your current IP in Network Access, then paste your Atlas URI into `.env` as `MONGODB_URI`.

For a no-network local rehearsal, set `MONGODB_ENABLED=false` and `IMENTIV_MOCK=true`.
