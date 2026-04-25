'use client';

import { useRouter, useSearchParams } from 'next/navigation';
import {
  Loader2,
  MessageSquare,
  Mic,
  Zap,
} from 'lucide-react';
import { motion } from 'framer-motion';
import { useCallback, useEffect, useMemo, useState } from 'react';

import { EmotionTimeline } from '@/components/EmotionTimeline';
import { PhaseCScorecard } from '@/components/PhaseCScorecard';
import { Badge } from '@/components/ui/badge';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  getPhaseCMergedChunks,
  getPhaseCScorecardFromSession,
  getPhaseCWrittenSummary,
  getSessionSummary,
  useRecentSessions,
  useSession,
  type PersistedSession,
  type SessionMode,
  type SessionPreview,
} from '@/hooks/useSessions';

type ModeMeta = {
  icon: typeof Zap;
  iconClassName: string;
  badgeClassName: string;
};

const MODE_META: Record<SessionMode, ModeMeta> = {
  phase_a: {
    icon: Zap,
    iconClassName: 'text-navy-500',
    badgeClassName: 'bg-navy-50 text-navy-600 border-navy-200',
  },
  phase_b: {
    icon: MessageSquare,
    iconClassName: 'text-teal-500',
    badgeClassName: 'bg-teal-50 text-teal-700 border-teal-200',
  },
  phase_c: {
    icon: Mic,
    iconClassName: 'text-amber-500',
    badgeClassName: 'bg-amber-50 text-amber-700 border-amber-200',
  },
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function formatDateLabel(value: string | null | undefined) {
  if (!value) {
    return 'Unknown date';
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return 'Unknown date';
  }

  return parsed.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

function formatReplayMeta(session: SessionPreview) {
  if (typeof session.duration_seconds === 'number') {
    return `${session.duration_seconds.toFixed(1)}s`;
  }
  if (typeof session.total_turns === 'number') {
    return `${session.total_turns} turns`;
  }
  if (typeof session.round_count === 'number') {
    return `${session.round_count} rounds`;
  }
  return session.status.replace('_', ' ');
}

function formatPercent(value: unknown) {
  const number = Number(value);
  return Number.isFinite(number) ? `${number}%` : '--';
}

function ReplayCard({ session, index, onSelect }: {
  session: SessionPreview;
  index: number;
  onSelect: (sessionId: string) => void;
}) {
  const modeMeta = MODE_META[session.mode];

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay: index * 0.05 }}
      className="rounded-2xl border border-cream-300 bg-white p-5 shadow-sm transition-shadow hover:shadow-md"
    >
      <div className="flex items-center gap-4">
        <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-cream-100">
          <modeMeta.icon size={22} className={modeMeta.iconClassName} />
        </div>

        <div className="min-w-0 flex-1">
          <h3 className="truncate font-medium text-slate-900">{session.label}</h3>
          <div className="mt-1 flex flex-wrap items-center gap-3 text-xs text-slate-500">
            <span>{formatDateLabel(session.completed_at || session.updated_at || session.created_at)}</span>
            <span>{formatReplayMeta(session)}</span>
          </div>
          <div className="mt-2">
            <Badge className={modeMeta.badgeClassName}>{session.mode_label}</Badge>
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-4">
          <div className="text-center">
            <p className="text-2xl font-semibold text-navy-500">{session.score ?? '--'}</p>
            <p className="text-[10px] uppercase tracking-wider text-slate-400">Score</p>
          </div>
          <button
            type="button"
            onClick={() => onSelect(session.session_id)}
            className="rounded-full bg-navy-500 px-4 py-2 text-sm font-medium text-white shadow-sm transition-colors hover:bg-navy-600"
          >
            View replay
          </button>
        </div>
      </div>
    </motion.div>
  );
}

function PhaseAReplayDetail({ session }: { session: PersistedSession }) {
  const summary = getSessionSummary(session);
  const setup = isRecord(session.setup) ? session.setup : {};
  const rounds = Array.isArray(summary.rounds)
    ? summary.rounds.filter((round): round is Record<string, unknown> => isRecord(round))
    : [];
  const matchScores = Array.isArray(summary.match_scores)
    ? summary.match_scores.map((score) => Number(score)).filter(Number.isFinite)
    : [];
  const averageScore = matchScores.length
    ? Math.round((matchScores.reduce((total, score) => total + score, 0) / matchScores.length) * 100)
    : null;
  const fillerWords = isRecord(summary.filler_words) ? Object.entries(summary.filler_words) : [];

  return (
    <div className="space-y-5">
      <div className="grid gap-4 md:grid-cols-3">
        <div className="rounded-2xl border border-cream-300 bg-white p-5">
          <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Target Emotion</p>
          <p className="mt-3 text-xl font-semibold text-slate-900">
            {String(setup.target_emotion || 'Emotion Sprint')}
          </p>
        </div>
        <div className="rounded-2xl border border-cream-300 bg-white p-5">
          <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Average Match</p>
          <p className="mt-3 text-xl font-semibold text-slate-900">
            {averageScore !== null ? `${averageScore}` : '--'}
          </p>
        </div>
        <div className="rounded-2xl border border-cream-300 bg-white p-5">
          <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Rounds</p>
          <p className="mt-3 text-xl font-semibold text-slate-900">{rounds.length}</p>
        </div>
      </div>

      <div className="rounded-[28px] border border-cream-300 bg-white p-6 shadow-sm">
        <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Round Critiques</p>
        <div className="mt-4 space-y-3">
          {rounds.length ? rounds.map((round, index) => (
            <div key={`${index}-${String(round.critique || '')}`} className="rounded-2xl bg-cream-50 p-4">
              <p className="text-sm font-semibold text-slate-900">Round {index + 1}</p>
              <p className="mt-2 text-sm leading-6 text-slate-600">
                {String(round.critique || 'No critique stored for this round.')}
              </p>
            </div>
          )) : (
            <p className="text-sm text-slate-500">No round critiques were stored for this session.</p>
          )}
        </div>
      </div>

      <div className="rounded-[28px] border border-cream-300 bg-white p-6 shadow-sm">
        <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Filler Words</p>
        <div className="mt-4 flex flex-wrap gap-2">
          {fillerWords.length ? fillerWords.map(([word, count]) => (
            <Badge key={word} className="border-cream-200 bg-cream-50 px-3 py-1.5 text-slate-700">
              {word} x{String(count)}
            </Badge>
          )) : (
            <p className="text-sm text-slate-500">No filler words were recorded for this session.</p>
          )}
        </div>
      </div>
    </div>
  );
}

function PhaseBReplayDetail({ session }: { session: PersistedSession }) {
  const summary = getSessionSummary(session);
  const setup = isRecord(session.setup) ? session.setup : {};
  const turns = Array.isArray(summary.turns)
    ? summary.turns.filter((turn): turn is Record<string, unknown> => isRecord(turn))
    : [];

  return (
    <div className="space-y-5">
      <div className="grid gap-4 md:grid-cols-3">
        <div className="rounded-2xl border border-cream-300 bg-white p-5">
          <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Scenario</p>
          <p className="mt-3 text-xl font-semibold text-slate-900">
            {String(setup.scenario || summary.scenario || 'Conversation')}
          </p>
        </div>
        <div className="rounded-2xl border border-cream-300 bg-white p-5">
          <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Eye Contact</p>
          <p className="mt-3 text-xl font-semibold text-slate-900">
            {formatPercent(summary.avg_eye_contact_pct)}
          </p>
        </div>
        <div className="rounded-2xl border border-cream-300 bg-white p-5">
          <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Turns</p>
          <p className="mt-3 text-xl font-semibold text-slate-900">
            {typeof summary.total_turns === 'number' ? summary.total_turns : turns.length}
          </p>
        </div>
      </div>

      <div className="rounded-[28px] border border-cream-300 bg-white p-6 shadow-sm">
        <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Conversation Review</p>
        <div className="mt-4 space-y-3">
          {turns.length ? turns.map((turn, index) => (
            <div
              key={`${String(turn.turn_index ?? index)}-${String(turn.prompt || '')}`}
              className="rounded-2xl bg-cream-50 p-4"
            >
              <p className="text-sm font-semibold text-slate-900">
                Turn {Number(turn.turn_index ?? 0) + 1}
              </p>
              <p className="mt-2 text-xs uppercase tracking-[0.16em] text-slate-400">
                {String(turn.prompt || 'Prompt unavailable')}
              </p>
              <p className="mt-3 text-sm leading-6 text-slate-600">
                {String(turn.critique || 'No critique stored for this turn.')}
              </p>
            </div>
          )) : (
            <p className="text-sm text-slate-500">No turn-level critiques were stored for this session.</p>
          )}
        </div>
      </div>
    </div>
  );
}

function PhaseCReplayDetail({ session }: { session: PersistedSession }) {
  const scorecard = getPhaseCScorecardFromSession(session);
  const writtenSummary = getPhaseCWrittenSummary(session);
  const mergedChunks = getPhaseCMergedChunks(session);

  return (
    <div className="space-y-6">
      <PhaseCScorecard scorecard={scorecard} writtenSummary={writtenSummary} />
      <EmotionTimeline chunks={mergedChunks} />
    </div>
  );
}

export default function ReplaysPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const sessionIdFromUrl = searchParams.get('session');
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(sessionIdFromUrl);
  const { data: sessions, loading, error } = useRecentSessions(20);
  const {
    data: selectedSession,
    loading: selectedSessionLoading,
    error: selectedSessionError,
  } = useSession(selectedSessionId);

  useEffect(() => {
    setSelectedSessionId(sessionIdFromUrl);
  }, [sessionIdFromUrl]);

  const updateSelectedSessionId = useCallback((nextSessionId: string | null) => {
    const nextParams = new URLSearchParams(searchParams.toString());
    if (nextSessionId) {
      nextParams.set('session', nextSessionId);
    } else {
      nextParams.delete('session');
    }

    const nextUrl = nextParams.toString() ? `/replays?${nextParams.toString()}` : '/replays';
    router.replace(nextUrl, { scroll: false });
    setSelectedSessionId(nextSessionId);
  }, [router, searchParams]);

  const selectedModeMeta = useMemo(() => {
    if (!selectedSession) {
      return null;
    }
    return MODE_META[selectedSession.mode];
  }, [selectedSession]);

  return (
    <div className="mx-auto max-w-4xl">
      <div className="mb-8">
        <h1 className="font-['Playfair_Display'] text-2xl font-semibold text-slate-900">
          Replays
        </h1>
        <p className="mt-1 text-sm text-slate-500">
          Review your persisted practice sessions across all three modes.
        </p>
      </div>

      {loading && (
        <div className="inline-flex items-center gap-3 rounded-full bg-white px-4 py-3 text-sm text-slate-700 shadow-sm">
          <Loader2 size={16} className="animate-spin text-navy-500" />
          Loading recent sessions
        </div>
      )}

      {error && (
        <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-600">
          {error}
        </div>
      )}

      {!loading && !error && (
        <div className="space-y-4">
          {sessions?.length ? sessions.map((session, index) => (
            <ReplayCard
              key={session.session_id}
              session={session}
              index={index}
              onSelect={updateSelectedSessionId}
            />
          )) : (
            <div className="rounded-[28px] border border-cream-300 bg-white p-8 text-center shadow-sm">
              <p className="font-['Playfair_Display'] text-2xl font-semibold text-slate-900">
                No sessions yet
              </p>
              <p className="mt-2 text-sm text-slate-500">
                Complete a practice session to see its persisted replay here.
              </p>
            </div>
          )}
        </div>
      )}

      <Dialog open={Boolean(selectedSessionId)} onOpenChange={(open) => !open && updateSelectedSessionId(null)}>
        <DialogContent
          showCloseButton
          className="max-h-[88vh] max-w-5xl overflow-y-auto rounded-[28px] border-cream-300 bg-cream-50 p-0"
        >
          {selectedSession && selectedModeMeta && (
            <DialogHeader className="border-b border-cream-200 px-6 py-5 text-left">
              <div className="flex items-center gap-3">
                <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-cream-100">
                  <selectedModeMeta.icon size={20} className={selectedModeMeta.iconClassName} />
                </div>
                <div>
                  <DialogTitle className="font-['Playfair_Display'] text-2xl text-slate-900">
                    {selectedSession.mode_label}
                  </DialogTitle>
                  <DialogDescription className="mt-1 text-sm text-slate-500">
                    {formatDateLabel(selectedSession.completed_at || selectedSession.updated_at || selectedSession.created_at)}
                  </DialogDescription>
                </div>
              </div>
            </DialogHeader>
          )}

          <div className="p-6">
            {selectedSessionLoading && (
              <div className="inline-flex items-center gap-3 rounded-full bg-white px-4 py-3 text-sm text-slate-700 shadow-sm">
                <Loader2 size={16} className="animate-spin text-navy-500" />
                Loading replay details
              </div>
            )}

            {selectedSessionError && (
              <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-600">
                {selectedSessionError}
              </div>
            )}

            {selectedSession && (
              <>
                {selectedSession.mode === 'phase_c' && <PhaseCReplayDetail session={selectedSession} />}
                {selectedSession.mode === 'phase_b' && <PhaseBReplayDetail session={selectedSession} />}
                {selectedSession.mode === 'phase_a' && <PhaseAReplayDetail session={selectedSession} />}
              </>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
