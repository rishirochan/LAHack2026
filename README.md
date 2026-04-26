# Clarity

Clarity is a communication practice app built for LA Hacks 2026. It records video and audio practice sessions, runs multimodal analysis, and turns each session into a replayable coaching loop.

Two external systems are especially important in this project:

- `ElevenLabs` for speech-to-text, text-to-speech, streamed conversation audio, and voice configuration
- `Imentiv` for emotion and multimodal delivery analysis
- `Gemma` through Google GenAI for prompt generation, conversational reasoning, critique writing, and coaching summaries

At a high level, the product is organized around three practice phases plus a review layer:

- `Phase A` / `Emotion Sprint`: short emotion-targeted drills where the user delivers a prompt in a chosen emotional register.
- `Phase B` / `Conversation`: multi-turn simulated conversations such as interviews, negotiations, or any other difficult discussions.
- `Phase C` / `Free Speaking`: open-ended speaking sessions focused on pacing, fillers, repetition, and overall delivery.
- `Replay Center`: a unified review surface for completed sessions, recordings, chunks, summaries, and scorecards.

## What’s In The Codebase

### Frontend

The frontend is a Next.js app in `frontend/` and is organized around the main product surfaces:

- `LandingPage`: product marketing and authentication entry point.
- `DashboardPage`: entry hub for starting a new session and seeing recent practice history.
- `SprintPage`: Phase A flow for emotion drills.
- `ConversationPage` + `ConversationReportPage`: Phase B live conversation flow and final debrief.
- `FreePage`: Phase C recording and analysis flow.
- `ReplaysPage`: replay browser for persisted sessions across all modes.
- `ProfilePage`: cross-session analytics and trend summaries.
- `SettingsPage`: voice selection and playback-speed configuration for conversation mode.

The frontend hooks in `frontend/src/hooks/` handle most session lifecycle work:

- `usePhaseASession`
- `usePhaseBConversation`
- `usePhaseCSession`
- `useSessions`
- `useProfileAnalytics`

### Backend

The backend is a FastAPI app in `backend/sprint/api.py`. It exposes:

- session start, upload, status, and completion endpoints for Phases A, B, and C
- websocket channels for live session updates
- replay/history endpoints for persisted sessions
- profile/trend endpoints for aggregated analytics
- text-to-speech voice listing and preview endpoints

Phase-specific logic lives under:

- `backend/sprint/phase_a/`
- `backend/sprint/phase_b/`
- `backend/sprint/phase_c/`

Shared integrations and persistence live under:

- `backend/shared/ai/`: provider setup and model integrations
- `backend/shared/db/`: persistence, session history, media metadata, and analytics aggregation
- `backend/shared/imentiv.py`: backend-facing Imentiv wrapper

The shared AI layer exposes cached provider clients through `backend/shared/ai/service.py`, including the ElevenLabs client used across all three phases.

## Feature Map

### Phase A: Emotion Sprint

Phase A is the fastest practice loop in the app. A user chooses a target emotion, receives a short prompt, records a response, and gets round-based critique plus session summary data.

ElevenLabs is used here for:

- transcription of the recorded response with word timestamps
- optional prompt/critique playback through TTS

Gemma is used here for:

- generating the short scenario prompt
- turning merged multimodal analysis into a written coach critique

Code areas:

- frontend UI: `frontend/src/views/SprintPage.tsx`
- frontend session hook: `frontend/src/hooks/usePhaseASession.ts`
- backend flow: `backend/sprint/phase_a/`

### Phase B: Conversation

Phase B simulates a back-and-forth conversation. The user provides a short brief, the system generates the other party and the scenario context, then each turn is recorded, analyzed, and stitched into a final conversation report.

ElevenLabs is used here for:

- full-turn transcription with word timestamps
- streamed peer voice playback over websockets
- saved voice selection for future peer turns
- voice preview clips from the settings flow

Gemma is used here for:

- shaping scenario context from the user brief
- generating conversational responses and coaching text
- helping produce the final conversation report

Code areas:

- frontend UI: `frontend/src/views/ConversationPage.tsx`
- final report UI: `frontend/src/views/ConversationReportPage.tsx`
- backend flow: `backend/sprint/phase_b/`

### Phase C: Free Speaking

Phase C is the open-ended speaking mode. It records a longer session, uploads chunks during capture, and produces a scorecard plus replay-friendly analysis artifacts such as transcript words, filler detections, and pattern summaries.

ElevenLabs is used here for:

- final audio transcription with word timestamps
- transcript generation that feeds scorecards, word audit, and replay analysis

Gemma is used here for:

- converting the deterministic Phase C scorecard into a short practical coaching summary

Code areas:

- frontend UI: `frontend/src/views/FreePage.tsx`
- frontend session hook: `frontend/src/hooks/usePhaseCSession.ts`
- backend flow: `backend/sprint/phase_c/`

### Replay Center

The replay experience is the main review layer across all three phases. It loads persisted sessions and adapts the presentation based on session mode.

In practice, the replay surface can show:

- recent session browsing
- completed session playback
- saved video/audio assets
- chunk-level playback for longer recordings
- conversation turn critiques
- free-speaking scorecards, emotion timelines, word audit, and detected patterns

Code areas:

- replay page: `frontend/src/views/ReplaysPage.tsx`
- replay/session loading: `frontend/src/hooks/useSessions.ts`
- replay backend endpoints: `/api/sessions/recent`, `/api/sessions/{session_id}`, `/api/sessions/{session_id}/replay`

### Analytics, History, and Settings

Outside the core practice phases, the app also includes:

- `Dashboard`: launch point plus recent sessions
- `Profile`: aggregated trends and historical performance summaries
- `Settings`: configurable ElevenLabs-backed conversation voice and playback speed
- `Sidebar` + session context: shared navigation and recent-session refresh behavior

## Persistence Model

The app stores durable practice history for replay and analytics. Session persistence is abstracted behind `backend/shared/db/repository.py`.

Persisted session data includes the basics needed to power the review surfaces:

- session metadata
- mode-specific setup data
- summaries
- media references
- raw or normalized state used for replay and analytics

MongoDB is supported for durable storage, while active websocket/session coordination still lives in process memory during a live run.

## MongoDB Details

MongoDB is wired through a small utility layer in `backend/shared/db/` so the rest of the app does not talk to the database directly.

The main pieces are:

- `settings.py`: loads `MONGODB_ENABLED`, `MONGODB_URI`, and `MONGODB_DB_NAME`
- `client.py`: initializes the process-wide database utilities and swaps between Mongo-backed and in-memory implementations
- `repository.py`: stores session documents and chunk analytics
- `media_store.py`: stores binary media files
- `tasks.py`: schedules non-blocking background persistence writes

### Utility Layer We Use

The MongoDB integration uses:

- `motor` for async MongoDB access
- `certifi` for TLS CA certificates when connecting to Atlas
- MongoDB `GridFS` through Motor for storing larger media blobs

At startup, `backend/shared/db/client.py` does the following:

- reads database settings
- creates a shared `AsyncIOMotorClient` when MongoDB is enabled
- builds a `MongoSessionRepository` for structured session data
- builds a `MongoGridFSMediaStore` for uploaded video/audio/transcript assets
- creates indexes before the app starts serving requests

If MongoDB is disabled, the same utility layer swaps to:

- `InMemorySessionRepository`
- `InMemoryMediaStore`

That means the rest of the backend keeps calling the same access points:

- `get_session_repository()`
- `get_media_store()`

### How We Save Data

The app separates structured session data from binary media data.

Structured data is stored through `MongoSessionRepository` in two collections:

- `practice_sessions`: one document per Phase A, B, or C session
- `session_chunks`: chunk-level documents used mainly for Phase B analytics/trend data

Binary uploads are stored through `MongoGridFSMediaStore` in the GridFS bucket named `practice_media`.

When a session starts, each phase creates an initial session document with:

- `session_id`
- `user_id`
- `mode` and `mode_label`
- `created_at` / `updated_at`
- initial `setup`
- initial `raw_state`

As the session progresses, we keep updating the same session document with:

- current `status`
- refreshed `updated_at`
- `completed_at` when the session is finished
- mode-specific `summary`
- `media_refs` pointing to stored uploads
- sanitized `raw_state` for replay and recovery

The three phases save slightly differently:

- `Phase A`: stores round summaries plus round media references directly on the session document
- `Phase B`: stores the main conversation state on the session document and also upserts per-turn/per-chunk analytics into `session_chunks`
- `Phase C`: stores the completed recording summary, scorecard, transcript-derived artifacts, and media references on the session document

### Why There Is A Separate Chunk Collection

`session_chunks` lets the backend keep chunk-level analytics in a queryable form instead of burying everything inside one large session document.

That is useful for:

- profile analytics
- emotion distribution summaries
- trend calculations across conversation sessions
- ordered replay of chunked recordings

For Phase B, chunk documents are upserted with a unique key across:

- `session_id`
- `turn_index`
- `chunk_index`

This prevents duplicate chunk records and makes partial updates safe.

### Background Write Utility

The session managers do not always block on database writes inline. Instead, they use `schedule_repository_write(...)` from `backend/shared/db/tasks.py`.

That helper:

- schedules async writes on the running event loop
- can serialize writes per `session_id`
- waits for the previous write for the same key before running the next one
- logs failures instead of crashing the live interaction loop

This is important because the product is running live recording, websocket updates, AI processing, and persistence at the same time. The write utility keeps persistence consistent without making every UI step wait on MongoDB.

### Media Storage

Uploaded media does not live inside the main session documents.

Instead:

- metadata about each file is stored in `media_refs`
- the actual bytes are stored in GridFS
- downloads stream back out through `iter_media(...)`
- AI/transcription helpers can temporarily materialize a GridFS file onto disk through `materialize_temp_file(...)`

This keeps the session documents lighter while still letting replay and analysis fetch the exact stored asset later.

### Indexes

The repository creates a few important indexes on startup:

- unique `session_id` on `practice_sessions`
- `(user_id, updated_at)` for recent-session history
- `mode` for filtering sessions by practice type
- unique `(session_id, turn_index, chunk_index)` on `session_chunks`
- `(user_id, updated_at)` on `session_chunks`
- `(user_id, dominant_video_emotion)` and `(user_id, dominant_audio_emotion)` for analytics queries

## ElevenLabs Details

ElevenLabs is a significant part of the app. It powers the speech layer across all three phases and is especially important in Phase B, where generated peer audio is part of the live user experience.

### Utility Layer We Use

The main ElevenLabs integration lives in:

- `backend/shared/ai/settings.py`: loads `ELEVENLABS_API_KEY`, `ELEVENLABS_DEFAULT_VOICE_ID`, `ELEVENLABS_STT_MODEL`, and `ELEVENLABS_TTS_MODEL`
- `backend/shared/ai/providers/elevenlabs.py`: builds the shared SDK client and normalizes the upstream voice catalog
- `backend/shared/ai/service.py`: exposes a cached `AIServiceFacade` with a shared `elevenlabs_client`

The app uses the official ElevenLabs Python SDK through:

- `elevenlabs.client.ElevenLabs`

At runtime, backend code does not construct ad hoc clients inside each route. It goes through `get_ai_service()`, which gives phase helpers access to one shared client and the configured model/voice settings.

### Where We Use ElevenLabs

The app uses ElevenLabs in four main ways:

- `speech-to-text`: converting recorded speech into transcripts with word-level timestamps
- `text-to-speech`: generating spoken prompts, critique playback, voice previews, and peer responses
- `streaming audio`: pushing synthesized conversation audio over websockets in Phase B
- `voice settings`: listing available voices and previewing them before the user starts a conversation

Mode by mode:

- `Phase A`: transcription plus optional TTS playback
- `Phase B`: transcription, streaming peer voice, preview generation, and saved voice preferences
- `Phase C`: transcription for replay and analysis
- `Settings`: voice list and voice preview utilities

### Phase-Specific Helpers

Like the MongoDB layer, the ElevenLabs integration is split into small utilities instead of one oversized module:

- `backend/sprint/phase_a/elevenlabs.py`
- `backend/sprint/phase_b/elevenlabs.py`
- `backend/sprint/phase_c/elevenlabs.py`

Each helper uses the same shared client but shapes the response for that phase’s product flow.

### How We Use Speech-to-Text

All three phases use ElevenLabs speech-to-text to create normalized transcript output.

The helpers call `speech_to_text.convert(...)` with:

- the configured `ELEVENLABS_STT_MODEL`
- `timestamps_granularity="word"`

The upstream response is then normalized into:

- one plain transcript string
- one word list with `word`, `start`, and `end`

That normalized output is reused across the app for:

- conversation transcripts
- Phase C transcript preview and word audit
- replay views that depend on timestamped words
- downstream analysis steps that need transcript timing

For Phase A and Phase B, the helper can accept saved upload metadata and use `get_media_store().materialize_temp_file(...)` to pull the exact stored file back out of the app’s media layer before sending it to ElevenLabs.

### How We Use Text-to-Speech

The app uses ElevenLabs TTS in two patterns:

- full audio generation for direct playback or preview
- chunk streaming for live conversation audio

In Phase A, TTS is used for prompt and critique playback.

In the shared settings flow, TTS is used to generate a short preview clip through:

- `GET /api/tts/voices`
- `POST /api/tts/preview`

In Phase B, TTS is used both for preview clips and for the simulated peer voice during the live conversation.

### Streamed Peer Voice In Phase B

Phase B uses the deepest ElevenLabs integration.

The Phase B helper:

- creates a TTS stream from ElevenLabs
- reads byte chunks from the stream on a background thread
- base64-encodes the chunks
- emits them through websocket events such as `audio_chunk`
- wraps the audio stream with `tts_start` and `tts_end` lifecycle events

This lets the frontend begin playback of the simulated peer without waiting for one fully rendered audio file.

The selected `voice_id` is stored in the Phase B session state and reused for future synthesized peer turns in that conversation.

### Voice Catalog And Preview Utility

`backend/shared/ai/providers/elevenlabs.py` includes `list_voice_options(...)`, which:

- fetches the upstream ElevenLabs voice catalog
- normalizes it into a stable frontend shape
- marks the configured default voice
- falls back to a synthetic default voice if the upstream list is unavailable

That fallback is important because the settings UI can still render a valid option even if the live voice-list call fails.

### Error Handling

The FastAPI layer includes ElevenLabs-specific error handling in `backend/sprint/api.py`.

That code translates upstream SDK failures into cleaner API errors for cases like:

- missing speech-to-text permissions
- rejected API keys
- generic upstream transcription failures

Because speech is central to the product, this keeps the frontend from dealing with raw provider exceptions.

## Gemma Details

Gemma is a cornerstone of the project. It is the reasoning and writing layer that turns raw multimodal signals into prompts, critiques, summaries, and structured coaching output that feels useful to the user instead of just diagnostic.

It also matters strategically for the competition track because the app is not just collecting media analytics. It is using Gemini/Gemma-backed generation to transform those signals into a live practice product with scenario creation, conversation simulation, and actionable feedback.

### Utility Layer We Use

The Gemma integration lives in the shared AI layer:

- `backend/shared/ai/settings.py`: loads `GOOGLE_API_KEY` and `GOOGLE_GEMMA_MODEL`
- `backend/shared/ai/providers/google_genai.py`: builds the Google GenAI client and wraps text generation helpers
- `backend/shared/ai/service.py`: exposes a cached `gemma_client` through `AIServiceFacade`

The app uses Google GenAI as the provider surface and sends Gemma requests through one shared client instead of rebuilding a client inside each feature.

### Where We Use Gemma

Gemma shows up across the full coaching loop:

- `Phase A`: scenario prompt generation and coach critique writing
- `Phase B`: conversation setup, peer behavior shaping, and final conversation debrief
- `Phase C`: concise summary writing from structured scorecard data

Phase-specific code lives in:

- `backend/sprint/phase_a/gemma.py`
- `backend/sprint/phase_b/gemma.py`
- `backend/sprint/phase_c/gemma.py`

### How We Use It In This App

We do not use Gemma as a generic chatbot. We use it as a controlled reasoning layer on top of structured inputs from the rest of the system.

That means Gemma is usually given:

- a tightly scoped system instruction
- a compact user or session prompt
- structured evidence such as transcript text, merged analysis, or scorecard JSON

In practice, this lets the app use Gemma for:

- generating natural practice prompts
- simulating conversation dynamics
- turning emotion/transcript evidence into critiques
- producing short summaries that remain grounded in measured signals

This is an important product choice: the hard analytics come from the rest of the pipeline, and Gemma is used to make those analytics understandable, actionable, and fast to review.

### Why Gemma Was A Good Fit

Gemma was a strong fit for this app for a few reasons:

- `speed`: the app needs responses quickly because users are moving through short practice loops, especially in Phase A and live conversation mode
- `structured instruction following`: the prompts ask for specific output shapes like short scenarios, concise critiques, or tightly bounded summaries
- `lightweight coaching text`: the product benefits from clear, direct writing rather than overly long assistant-style answers
- `good utility per call`: the model is being used many times inside a session flow, so practical latency and consistency matter

For this application, those properties are more useful than raw open-ended creativity. The goal is not to have the model talk as much as possible. The goal is to have it produce fast, grounded, useful coaching artifacts at the right moments in the session.

### Why It Matters For The Product

Without Gemma, the app would still have transcripts, emotion signals, and persistence, but it would feel much more like an analysis dashboard than a communication coach.

Gemma is what helps connect:

- raw session data
- user intent
- readable coaching output

That is why it is a cornerstone of the project rather than an optional extra.

## Quick Start

Run the backend and frontend in separate terminals from the repository root.

```bash
uv sync
uv run uvicorn backend.sprint.api:app --reload --host 0.0.0.0 --port 8000
```

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`.

## Environment

Copy `.env.example` to `.env`, then fill in real values. The frontend defaults to `http://localhost:8000` and `ws://localhost:8000`; for different hosts, copy `frontend/.env.example` to `frontend/.env.local`.

- `GOOGLE_API_KEY`
- `GOOGLE_GEMMA_MODEL`
- `ELEVENLABS_API_KEY`
- `ELEVENLABS_DEFAULT_VOICE_ID`
- `ELEVENLABS_STT_MODEL` (default `scribe_v1`)
- `ELEVENLABS_TTS_MODEL` (default `eleven_multilingual_v2`)
- `IMENTIV_API_KEY`
- `IMENTIV_BASE_URL` (defaults to `https://api.imentiv.ai/`)
- `IMENTIV_USER_CONSENT_VERSION` (defaults to `2.0.0`)
- `IMENTIV_MOCK=false` for live Imentiv analysis
- `MONGODB_ENABLED` (`true` when using MongoDB persistence)
- `MONGODB_URI`
- `MONGODB_DB_NAME` (defaults to `voxcoach`)
- `NEXT_PUBLIC_API_URL`
- `NEXT_PUBLIC_WS_URL`

## Integration Notes

The backend uses a shared AI integration layer under `backend/shared/ai` plus a backend-only Imentiv wrapper under `backend/shared/imentiv.py`.

- `from backend.shared.ai import get_settings, validate_settings`
- `from backend.shared.ai import get_ai_service`
- `from backend.shared.imentiv import get_imentiv_client`

Phase A, B, and C keep Imentiv calls on the backend. Recordings are saved server-side, uploaded from the backend, normalized, and then exposed through session status, replay, and websocket flows.

## MongoDB Persistence

MongoDB stores durable practice-session history for the dashboard, replay center, and profile analytics while live websocket coordination remains in memory.

For a local no-network rehearsal, set:

- `MONGODB_ENABLED=false`
- `IMENTIV_MOCK=true`
