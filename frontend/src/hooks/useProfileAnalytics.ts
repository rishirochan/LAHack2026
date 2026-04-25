'use client';

import { useCallback, useEffect, useState } from 'react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

export interface PhaseAEmotionScore {
  [emotion: string]: number;
}

export interface ScoreDataPoint {
  session_id: string;
  date: string;
  score: number;
  target_emotion?: string;
}

export interface EyeContactDataPoint {
  session_id: string;
  date: string;
  eye_contact_pct: number;
}

export interface PhaseAStats {
  session_count: number;
  average_match_score: number | null;
  average_filler_rate: number | null;
  average_score_by_emotion: PhaseAEmotionScore;
  best_emotion: string | null;
  worst_emotion: string | null;
  score_over_time: ScoreDataPoint[];
}

export interface PhaseBStats {
  session_count: number;
  average_eye_contact_pct: number | null;
  dominant_video_emotions: Record<string, number>;
  dominant_audio_emotions: Record<string, number>;
  chunks_failed: number;
  chunks_timed_out: number;
  chunk_count: number;
  avg_turns_per_session: number | null;
  eye_contact_over_time: EyeContactDataPoint[];
}

export interface RecentSession {
  session_id: string;
  mode: string;
  mode_label: string;
  label: string;
  status: string;
  score: number | null;
  date: string | null;
}

export interface ProfileSummary {
  user_id: string;
  total_sessions: number;
  completed_sessions: number;
  completion_rate: number;
  total_practice_minutes: number;
  phase_a: PhaseAStats;
  phase_b: PhaseBStats;
  score_history: Array<{
    session_id: string;
    mode: string;
    score: number;
    completed_at: string | null;
    updated_at: string | null;
  }>;
  recent_sessions: RecentSession[];
}

export type ProfileAnalyticsState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'success'; data: ProfileSummary }
  | { status: 'error'; message: string };

export function useProfileAnalytics() {
  const [state, setState] = useState<ProfileAnalyticsState>({ status: 'idle' });

  const load = useCallback(async () => {
    setState({ status: 'loading' });
    try {
      const res = await fetch(`${API_BASE}/api/profile-summary`);
      if (!res.ok) {
        throw new Error(`Server returned ${res.status}`);
      }
      const data = (await res.json()) as ProfileSummary;
      setState({ status: 'success', data });
    } catch (err) {
      setState({
        status: 'error',
        message: err instanceof Error ? err.message : 'Failed to load profile data.',
      });
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return { state, reload: load };
}
