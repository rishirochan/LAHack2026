# Clarity

Clarity is a multimodal communication coaching app built for LA Hacks 2026. It records video and audio practice sessions, runs real-time analysis across speech, emotion, and delivery, and turns each session into a replayable coaching loop — powered by **Gemma**, **ElevenLabs**, and **MongoDB**.

---

## Practice Modes

**Emotion Sprint** — Short drills where the user delivers a prompt in a chosen emotional register, then receives a round-based critique and session summary.

**Conversation** — Multi-turn simulated discussions (interviews, negotiations, difficult conversations). The system generates the other party, simulates their voice live, and produces a full debrief at the end.

**Free Speaking** — Open-ended recording sessions focused on pacing, fillers, repetition, and overall delivery. Produces a scorecard plus replay-ready transcript artifacts.

**Replay Center** — Unified review surface for all completed sessions: playback, chunk-level analysis, emotion timelines, word audits, conversation turn critiques, and scorecards.

**Profile** — Aggregates performance trends across all sessions, surfacing emotion distributions, delivery patterns, and progress over time so users can track improvement rather than treating each session in isolation.

**Settings** — Configures the ElevenLabs-backed conversation voice and playback speed, with live preview clips so users can hear their chosen voice before starting a session.

---

## Sponsor Technologies

### Gemma (Google GenAI)

Gemma is what separates Clarity from a metrics dashboard. Without it, the app would collect transcripts, emotion signals, and delivery scores — but have no way to turn those numbers into something a user can actually understand and act on. Gemma bridges the gap between raw multimodal data and the human-readable coaching experience that makes the product feel like a real practice partner rather than an analytics tool.

It is never used as a generic chatbot. Every call gives Gemma a tightly scoped system instruction, a compact prompt, and structured evidence from the rest of the pipeline — transcript text, merged emotion/delivery analysis, or scorecard JSON — so the output stays grounded in what was actually measured rather than drifting into generic advice.

- **Emotion Sprint**: generates a fresh, contextually appropriate scenario prompt for each round so the user always has something real to respond to, then synthesizes the merged multimodal signals into a written coach critique that explains *why* the delivery worked or didn't — not just what the numbers were.
- **Conversation**: shapes the full scenario context from the user's one-line brief (who the other party is, what they want, how they behave), drives each simulated peer response turn-by-turn to keep the conversation coherent, and writes the final session debrief that ties together performance across all turns.
- **Free Speaking**: takes the deterministic scorecard — filler counts, pacing measurements, repetition flags — and converts it into a concise, prioritized coaching summary the user can read in under a minute and carry into their next session.

The choice of Gemma specifically mattered here. The app calls it many times inside a single session loop, so latency and consistency are critical. Gemma's speed and instruction-following made it the right fit for producing short, structured coaching artifacts on demand rather than long open-ended responses.

Integration lives in `backend/shared/ai/providers/google_genai.py`, exposed through a cached `AIServiceFacade` in `backend/shared/ai/service.py`. Mode-specific logic in `backend/sprint/phase_a/gemma.py`, `phase_b/gemma.py`, `phase_c/gemma.py`.

---

### ElevenLabs

ElevenLabs is the voice infrastructure for the entire app. Every piece of spoken input the user produces passes through ElevenLabs before anything else in the pipeline can run — no transcript means no critique, no scorecard, no replay. And in Conversation mode, ElevenLabs also generates the other side of the dialogue in real time, which is what makes the simulation feel like a live interaction rather than a turn-based form.

- **Speech-to-text**: all three modes call `speech_to_text.convert(...)` with `timestamps_granularity="word"` using `ELEVENLABS_STT_MODEL`. The response is normalized into a plain transcript string plus a word list with `start`/`end` timestamps. That timestamped output is the shared foundation for replay word highlighting, Free Speaking's word audit and filler detection, Conversation turn analysis, and every downstream step that needs to know *when* something was said, not just *what*.
- **Text-to-speech**: used in Emotion Sprint for prompt delivery and critique playback so the user can absorb feedback without reading; in Conversation for the simulated peer voice and for voice preview clips in the settings flow; exposed to the frontend through `GET /api/tts/voices` and `POST /api/tts/preview`.
- **Streaming peer voice** (Conversation only): this is the deepest integration. The Conversation helper opens a TTS stream, reads byte chunks on a background thread, base64-encodes them, and pushes `audio_chunk` / `tts_start` / `tts_end` events over WebSocket. The frontend begins playing back the peer's voice before the full audio is rendered, which is what preserves the feeling of a natural back-and-forth rather than a noticeable processing pause between turns.
- **Voice catalog**: `list_voice_options(...)` normalizes the upstream voice catalog, marks the configured default, and falls back to a synthetic entry if the live catalog call fails — so the settings UI always renders a valid choice even under degraded conditions.

The ElevenLabs word-timestamp format is particularly important: it is the linking layer that makes the Replay Center work. Chunk-level playback, emotion timeline alignment, and word audit all depend on having precise per-word timing anchors that only ElevenLabs provides at the quality Clarity needs.

Integration in `backend/shared/ai/providers/elevenlabs.py`, mode-specific helpers in `phase_a/elevenlabs.py`, `phase_b/elevenlabs.py`, `phase_c/elevenlabs.py`.

---

### MongoDB

MongoDB is what turns Clarity from a single-session tool into a practice system with memory. A user's history, progress trends, replay artifacts, and raw media all need to survive across sessions and be queryable in structured ways — that requires a real persistence layer, not in-process state. MongoDB's flexible document model was the right fit because each practice mode produces a different shape of session data, and forcing all of it into a fixed relational schema would have required constant migration work as the product evolved during the hackathon.

- **`practice_sessions`**: one document per session across all modes. Stores metadata, setup, current status, mode-specific summary, media references, and a sanitized replay state snapshot. The document is updated in place as the session progresses rather than written once at the end, which means partial sessions are always recoverable.
- **`session_chunks`**: keeps per-turn/per-chunk analytics in a queryable collection instead of burying them inside the main session document. Each document is upserted with a unique `(session_id, turn_index, chunk_index)` key so partial updates are always safe and profile analytics can query across sessions efficiently — emotion distributions, trend data, and replay ordering all run against this collection.
- **GridFS (`practice_media`)**: binary assets (video, audio, transcripts) live in a dedicated GridFS bucket rather than inside session documents, keeping document size predictable. Assets are retrieved via `iter_media(...)` and temporarily materialized for AI/transcription steps via `materialize_temp_file(...)` before being cleaned up automatically.
- **Background writes**: `schedule_repository_write(...)` in `backend/shared/db/tasks.py` serializes async writes per `session_id` on the running event loop. This is critical: the app is simultaneously handling live recording, WebSocket audio streaming, AI inference, and Imentiv analysis — blocking on every MongoDB write would stall the user-facing session loop. The write utility keeps persistence consistent without introducing latency into any of those paths.
- **Fallback**: if `MONGODB_ENABLED=false`, the same access points (`get_session_repository()`, `get_media_store()`) swap transparently to in-memory implementations. No phase logic changes — useful for local development without a database connection.

The indexes created at startup reflect the actual query patterns the product needs: `(user_id, updated_at)` for recent-session history, `(session_id, turn_index, chunk_index)` for chunk deduplication, and `(user_id, dominant_video_emotion)` / `(user_id, dominant_audio_emotion)` for the profile analytics aggregations.

Integration in `backend/shared/db/` (`client.py`, `repository.py`, `media_store.py`, `tasks.py`, `settings.py`).

---

## Quick Start

```bash
# Backend
uv sync
uv run uvicorn backend.sprint.api:app --reload --host 0.0.0.0 --port 8000

# Frontend
cd frontend && npm install && npm run dev
```

Open `http://localhost:3000`. Copy `.env.example` to `.env` and fill in `GOOGLE_API_KEY`, `ELEVENLABS_API_KEY`, `IMENTIV_API_KEY`, `MONGODB_URI`, and related config.