'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';

import type {
  PatternBadge,
  PhaseCMergedAnalysisChunk,
  PhaseCScorecard,
  TranscriptWord,
  WordCorrelation,
} from '@/lib/phase-c-api';

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

export type SessionMode = 'phase_a' | 'phase_b' | 'phase_c';
export type PersistedSessionStatus = 'active' | 'complete' | 'error';

export interface SessionPreview {
  session_id: string;
  mode: SessionMode;
  mode_label: string;
  label: string;
  status: PersistedSessionStatus;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
  score: number | null;
  duration_seconds: number | null;
  total_turns: number | null;
  round_count: number | null;
}

export interface PersistedSession {
  session_id: string;
  user_id: string;
  mode: SessionMode;
  mode_label: string;
  status: PersistedSessionStatus;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
  setup: Record<string, unknown>;
  rounds: Array<Record<string, unknown>>;
  summary: Record<string, unknown> | null;
  media_refs: MediaRef[];
  phase_c_recording: {
    scorecard: PhaseCScorecard | null;
    written_summary: string;
    merged_chunks: PhaseCMergedAnalysisChunk[];
    full_transcript: string;
    transcript_words: TranscriptWord[];
    filler_words_found: string[];
    patterns: PatternBadge[];
    word_correlations: WordCorrelation[];
  } | null;
}

export interface MediaRef {
  kind: string;
  round_index?: number;
  turn_index?: number;
  chunk_index?: number;
  download_url: string;
  upload: {
    file_id: string | null;
    storage_key: string;
    filename: string;
    original_filename: string;
    mime_type: string;
    size_bytes: number;
    uploaded_at: string;
  };
}

type LoadableResult<T> = {
  data: T | null;
  loading: boolean;
  error: string;
  refetch: () => Promise<void>;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

async function fetchJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    cache: 'no-store',
    signal,
  });

  if (!response.ok) {
    const body = await response.text().catch(() => '');
    throw new Error(body || `Request failed with status ${response.status}.`);
  }

  return response.json() as Promise<T>;
}

function useApiResource<T>(path: string | null): LoadableResult<T> {
  const [state, setState] = useState<{
    data: T | null;
    error: string;
    loadedPath: string | null;
    loadedToken: number;
  }>({
    data: null,
    error: '',
    loadedPath: null,
    loadedToken: 0,
  });
  const [refreshToken, setRefreshToken] = useState(0);

  useEffect(() => {
    if (!path) {
      return;
    }

    const abortController = new AbortController();

    void fetchJson<T>(path, abortController.signal)
      .then((nextData) => {
        setState({
          data: nextData,
          error: '',
          loadedPath: path,
          loadedToken: refreshToken,
        });
      })
      .catch((fetchError) => {
        if (abortController.signal.aborted) {
          return;
        }
        setState({
          data: null,
          error: fetchError instanceof Error ? fetchError.message : 'Request failed.',
          loadedPath: path,
          loadedToken: refreshToken,
        });
      });

    return () => abortController.abort();
  }, [path, refreshToken]);

  const refetch = useCallback(async () => {
    setRefreshToken((current) => current + 1);
  }, []);

  const data = path && state.loadedPath === path ? state.data : null;
  const error =
    path && state.loadedPath === path && state.loadedToken === refreshToken
      ? state.error
      : '';
  const loading = Boolean(path) && (state.loadedPath !== path || state.loadedToken !== refreshToken);

  return { data, loading, error, refetch };
}

export function useRecentSessions(limit = 10): LoadableResult<SessionPreview[]> {
  const result = useApiResource<{ sessions: SessionPreview[] }>(`/api/sessions/recent?limit=${limit}`);

  return useMemo(
    () => ({
      data: result.data?.sessions ?? null,
      loading: result.loading,
      error: result.error,
      refetch: result.refetch,
    }),
    [result],
  );
}

export function useSession(sessionId: string | null): LoadableResult<PersistedSession> {
  return useApiResource<PersistedSession>(sessionId ? `/api/sessions/${sessionId}/replay` : null);
}

export function getPhaseCScorecardFromSession(
  session: PersistedSession | null | undefined,
): PhaseCScorecard | null {
  return session?.phase_c_recording?.scorecard ?? null;
}

export function getPhaseCMergedChunks(
  session: PersistedSession | null | undefined,
): PhaseCMergedAnalysisChunk[] {
  return session?.phase_c_recording?.merged_chunks ?? [];
}

export function getPhaseCWrittenSummary(
  session: PersistedSession | null | undefined,
): string {
  return session?.phase_c_recording?.written_summary ?? '';
}

export function getSessionSummary(
  session: PersistedSession | null | undefined,
): Record<string, unknown> {
  return isRecord(session?.summary) ? session.summary : {};
}

export function getPhaseCTranscriptWords(
  session: PersistedSession | null | undefined,
): TranscriptWord[] {
  return session?.phase_c_recording?.transcript_words ?? [];
}

export function getPhaseCFullTranscript(
  session: PersistedSession | null | undefined,
): string {
  return session?.phase_c_recording?.full_transcript ?? '';
}

export function getPhaseCFillerWordsFound(
  session: PersistedSession | null | undefined,
): string[] {
  return session?.phase_c_recording?.filler_words_found ?? [];
}

export function getPhaseCPatterns(
  session: PersistedSession | null | undefined,
): PatternBadge[] {
  return session?.phase_c_recording?.patterns ?? [];
}

export function getPhaseCWordCorrelations(
  session: PersistedSession | null | undefined,
): WordCorrelation[] {
  return session?.phase_c_recording?.word_correlations ?? [];
}

export function getMediaUrl(downloadUrl: string): string {
  return `${API_URL}${downloadUrl}`;
}
