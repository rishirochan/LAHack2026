/**
 * Phase B conversation API client.
 *
 * Thin wrappers around the backend HTTP + WebSocket surface so the
 * conversation page never contains raw fetch/FormData logic.
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const WS_URL = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000";

// ---------------------------------------------------------------------------
// Scenario / session types
// ---------------------------------------------------------------------------

export type Scenario = "interview" | "negotiation" | "casual" | "public_speaking";

export type Persona = "interviewer" | "negotiator" | "friend" | "audience";

export type SessionStatus = "active" | "complete" | "error";

export interface StartConversationRequest {
  practice_prompt?: string;
  scenario_preference?: Scenario;
  max_turns?: number;
}

export interface StartConversationResponse {
  session_id: string;
  status: SessionStatus;
}

export interface SessionStateResponse {
  session_id: string;
  scenario: Scenario;
  persona: Persona;
  turn_index: number;
  max_turns: number;
  conversation_history: Array<Record<string, string>>;
  current_turn: TurnState | null;
  turns: TurnState[];
  status: SessionStatus;
}

export interface TurnState {
  turn_index: number;
  prompt_text: string;
  recording_start_ms: number | null;
  recording_end_ms: number | null;
  chunks: ChunkRecord[];
  transcript: string | null;
  transcript_words: Array<Record<string, unknown>> | null;
  merged_summary: Record<string, unknown> | null;
  critique: string | null;
}

export interface ChunkRecord {
  chunk_index: number;
  start_ms: number;
  end_ms: number;
  mediapipe_metrics: Record<string, unknown>;
  video_emotions: Array<Record<string, unknown>> | null;
  audio_emotions: Array<Record<string, unknown>> | null;
  status: "pending" | "processing" | "done" | "failed" | "timed_out";
}

// ---------------------------------------------------------------------------
// WebSocket event union
// ---------------------------------------------------------------------------

export type WsEvent =
  | { type: "prompt_generated"; payload: { prompt_text: string } }
  | { type: "tts_start"; payload: { audio_type: "prompt" | "critique"; text: string } }
  | { type: "audio_chunk"; payload: { audio_type: "prompt" | "critique"; chunk: string; mime_type: string } }
  | { type: "tts_end"; payload: { audio_type: "prompt" | "critique" } }
  | { type: "recording_ready"; payload: { max_seconds: number; turn_index: number } }
  | { type: "processing_stage"; payload: { stage: string } }
  | { type: "critique_generated"; payload: { critique: string } }
  | { type: "retry_recording"; payload: { message: string } }
  | {
      type: "session_complete";
      payload: {
        session_id: string;
        scenario: string;
        total_turns: number;
        turns: Array<{ turn_index: number; prompt: string; critique: string | null }>;
      };
    }
  | { type: "error"; payload: { message: string } };

// ---------------------------------------------------------------------------
// HTTP helpers
// ---------------------------------------------------------------------------

async function json<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`${res.status}: ${body}`);
  }
  return res.json() as Promise<T>;
}

export function createSession(req: StartConversationRequest) {
  return json<StartConversationResponse>(`${API_URL}/api/phase-b/sessions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
}

export function getSession(sessionId: string) {
  return json<SessionStateResponse>(`${API_URL}/api/phase-b/sessions/${sessionId}`);
}

export function requestNextTurn(sessionId: string) {
  return json<{ status: string }>(`${API_URL}/api/phase-b/sessions/${sessionId}/turns/next`, {
    method: "POST",
  });
}

export function uploadChunk(
  sessionId: string,
  turnIndex: number,
  opts: {
    chunkIndex: number;
    startMs: number;
    endMs: number;
    videoBlob: Blob;
    audioBlob: Blob;
    mediapipeMetrics?: Record<string, unknown>;
  },
) {
  const form = new FormData();
  form.append("video_file", opts.videoBlob, `chunk_${opts.chunkIndex}.webm`);
  form.append("audio_file", opts.audioBlob, `chunk_${opts.chunkIndex}_audio.webm`);
  form.append("chunk_index", String(opts.chunkIndex));
  form.append("start_ms", String(opts.startMs));
  form.append("end_ms", String(opts.endMs));
  form.append("mediapipe_metrics", JSON.stringify(opts.mediapipeMetrics ?? {}));

  return json<{ status: string; chunk_index: string }>(
    `${API_URL}/api/phase-b/sessions/${sessionId}/turns/${turnIndex}/chunks`,
    { method: "POST", body: form },
  );
}

export function transcribeTurn(sessionId: string, turnIndex: number, audioBlob: Blob) {
  const form = new FormData();
  form.append("audio_file", audioBlob, "turn_audio.webm");
  return json<{ transcript: string; word_count: number }>(
    `${API_URL}/api/phase-b/sessions/${sessionId}/turns/${turnIndex}/transcribe`,
    { method: "POST", body: form },
  );
}

export function completeTurn(sessionId: string, turnIndex: number) {
  return json<{ status: string }>(
    `${API_URL}/api/phase-b/sessions/${sessionId}/turns/${turnIndex}/complete`,
    { method: "POST" },
  );
}

export function endSession(sessionId: string) {
  return json<{ status: string; total_turns: number; turns: Array<{ turn_index: number; prompt: string; critique: string | null }> }>(
    `${API_URL}/api/phase-b/sessions/${sessionId}/end`,
    { method: "POST" },
  );
}

// ---------------------------------------------------------------------------
// WebSocket helper
// ---------------------------------------------------------------------------

export function connectWs(sessionId: string, onEvent: (event: WsEvent) => void) {
  const socket = new WebSocket(`${WS_URL}/api/phase-b/ws/${sessionId}`);

  socket.onmessage = (msg) => {
    try {
      const event = JSON.parse(msg.data) as WsEvent;
      onEvent(event);
    } catch {
      // ignore malformed frames
    }
  };

  return socket;
}
