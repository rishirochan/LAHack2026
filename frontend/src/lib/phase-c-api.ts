const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
const WS_URL = process.env.NEXT_PUBLIC_WS_URL ?? 'ws://localhost:8000';

export type SessionStatus = 'active' | 'complete' | 'error';

export interface PhaseCWpmChunk {
  chunk_index: number;
  t_start: number;
  t_end: number;
  word_count: number;
  wpm: number;
}

export interface PhaseCPacingDrift {
  average_wpm: number;
  target_band: [number, number];
  too_fast_chunks: number;
  too_slow_chunks: number;
  trend: 'stable' | 'speeding_up' | 'slowing_down' | 'mixed' | string;
}

export interface PhaseCRepeatedWord {
  word: string;
  count: number;
}

export interface PhaseCRepeatedPhrase {
  phrase: string;
  count: number;
}

export interface PhaseCEmotionFlag {
  triggered: boolean;
  longest_neutral_run_seconds?: number;
  nervous_chunk_ratio?: number;
}

export interface PhaseCScorecard {
  duration_seconds: number;
  transcript_word_count: number;
  average_wpm: number;
  wpm_by_chunk: PhaseCWpmChunk[];
  pacing_drift: PhaseCPacingDrift;
  filler_word_count: number;
  filler_word_breakdown: Record<string, number>;
  repetition: {
    top_repeated_words: PhaseCRepeatedWord[];
    top_repeated_phrases: PhaseCRepeatedPhrase[];
  };
  emotion_flags: {
    emotional_flatness: PhaseCEmotionFlag;
    nervousness_persistence: PhaseCEmotionFlag;
  };
  chunk_health: {
    total_chunks: number;
    done_chunks: number;
    timed_out_chunks: number;
    failed_chunks: number;
  };
  overall_score: number;
  strengths: string[];
  improvement_areas: string[];
}

export interface PhaseCMergedAnalysisChunk {
  chunk_index: number;
  t_start: number;
  t_end: number;
  transcript_segment: string;
  dominant_video_emotion: string | null;
  video_confidence: number | null;
  dominant_audio_emotion: string | null;
  audio_confidence: number | null;
  eye_contact_pct: number | null;
  status: string;
}

export interface StartPhaseCSessionResponse {
  session_id: string;
  status: SessionStatus;
}

export interface PhaseCChunkRecord {
  chunk_index: number;
  start_ms: number;
  end_ms: number;
  mediapipe_metrics: Record<string, unknown>;
  video_emotions: Array<Record<string, unknown>> | null;
  audio_emotions: Array<Record<string, unknown>> | null;
  status: 'pending' | 'processing' | 'done' | 'failed' | 'timed_out';
}

export interface PhaseCRecordingState {
  recording_start_ms: number | null;
  recording_end_ms: number | null;
  chunks: PhaseCChunkRecord[];
  transcript: string | null;
  transcript_words: Array<Record<string, unknown>> | null;
  merged_analysis: {
    chunks?: PhaseCMergedAnalysisChunk[];
    overall?: Record<string, unknown>;
    transcript_words?: Array<Record<string, unknown>>;
  } | null;
  scorecard: PhaseCScorecard | null;
  written_summary: string | null;
}

export interface PhaseCSessionStateResponse {
  session_id: string;
  status: SessionStatus;
  current_recording: PhaseCRecordingState | null;
  completed_recording: PhaseCRecordingState | null;
}

export type PhaseCWsEvent =
  | { type: 'recording_ready'; payload: { max_seconds: number } }
  | { type: 'processing_stage'; payload: { stage: string } }
  | {
      type: 'session_result';
      payload: {
        scorecard: PhaseCScorecard;
        written_summary: string;
      };
    }
  | { type: 'retry_recording'; payload: { message: string } }
  | { type: 'error'; payload: { message: string } };

async function json<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    const body = await response.text().catch(() => '');
    throw new Error(`${response.status}: ${body}`);
  }
  return response.json() as Promise<T>;
}

export function createSession() {
  return json<StartPhaseCSessionResponse>(`${API_URL}/api/phase-c/sessions`, {
    method: 'POST',
  });
}

export function getSession(sessionId: string) {
  return json<PhaseCSessionStateResponse>(`${API_URL}/api/phase-c/sessions/${sessionId}`);
}

export function startRecording(sessionId: string) {
  return json<{ status: string }>(`${API_URL}/api/phase-c/sessions/${sessionId}/recording/start`, {
    method: 'POST',
  });
}

export function uploadChunk(
  sessionId: string,
  options: {
    chunkIndex: number;
    startMs: number;
    endMs: number;
    videoBlob: Blob;
    audioBlob: Blob;
    mediapipeMetrics?: Record<string, unknown>;
  },
) {
  const form = new FormData();
  form.append('video_file', options.videoBlob, `phase-c-chunk-${options.chunkIndex}.webm`);
  form.append('audio_file', options.audioBlob, `phase-c-chunk-${options.chunkIndex}-audio.webm`);
  form.append('chunk_index', String(options.chunkIndex));
  form.append('start_ms', String(options.startMs));
  form.append('end_ms', String(options.endMs));
  form.append('mediapipe_metrics', JSON.stringify(options.mediapipeMetrics ?? {}));

  return json<{ status: string; chunk_index: string }>(
    `${API_URL}/api/phase-c/sessions/${sessionId}/chunks`,
    { method: 'POST', body: form },
  );
}

export function transcribeAudio(sessionId: string, audioBlob: Blob) {
  const form = new FormData();
  form.append('audio_file', audioBlob, 'phase-c-transcript-audio.webm');
  return json<{ transcript: string; word_count: number }>(
    `${API_URL}/api/phase-c/sessions/${sessionId}/transcribe`,
    { method: 'POST', body: form },
  );
}

export function completeSession(sessionId: string) {
  return json<{ status: string }>(`${API_URL}/api/phase-c/sessions/${sessionId}/complete`, {
    method: 'POST',
  });
}

export function connectWs(sessionId: string, onEvent: (event: PhaseCWsEvent) => void) {
  const socket = new WebSocket(`${WS_URL}/api/phase-c/ws/${sessionId}`);

  socket.onmessage = (message) => {
    try {
      const event = JSON.parse(message.data) as PhaseCWsEvent;
      onEvent(event);
    } catch {
      // Ignore malformed websocket frames.
    }
  };

  return socket;
}
