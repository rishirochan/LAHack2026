'use client';

import { useRouter, useSearchParams } from 'next/navigation';
import {
  Loader2,
  MessageSquare,
  Mic,
  PlayCircle,
  X,
  Zap,
} from 'lucide-react';
import { motion } from 'framer-motion';
import ReactMarkdown from 'react-markdown';
import { startTransition, useCallback, useEffect, useMemo, useState } from 'react';

import { EmotionTimeline } from '@/components/EmotionTimeline';
import { PhaseCScorecard } from '@/components/PhaseCScorecard';
import { WordAudit } from '@/components/WordAudit';
import { PatternsDetected } from '@/components/PatternsDetected';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';
import { Badge } from '@/components/ui/badge';
import {
  getMediaUrl,
  getPhaseCMergedChunks,
  getPhaseCScorecardFromSession,
  getPhaseCWrittenSummary,
  getPhaseCTranscriptWords,
  getPhaseCFillerWordsFound,
  getPhaseCPatterns,
  getPhaseCWordCorrelations,
  getSessionSummary,
  useRecentSessions,
  useSession,
  type MediaRef,
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

type PhaseBFinalReport = {
  summary: string;
  natural_ending_reason: string;
  conversation_momentum_score: number;
  content_quality_score: number;
  emotional_delivery_score: number;
  energy_match_score: number;
  authenticity_score: number;
  follow_up_invitation_score: number;
  strengths: string[];
  growth_edges: string[];
  next_focus: string;
};

function coerceStringArray(value: unknown) {
  return Array.isArray(value) ? value.map(String).filter(Boolean) : [];
}

function getPhaseBFinalReport(summary: Record<string, unknown>): PhaseBFinalReport | null {
  const candidate = isRecord(summary.final_report) ? summary.final_report : null;
  if (!candidate) {
    return null;
  }

  const summaryText = typeof candidate.summary === 'string' ? candidate.summary.trim() : '';
  const nextFocus = typeof candidate.next_focus === 'string' ? candidate.next_focus.trim() : '';
  if (!summaryText && !nextFocus) {
    return null;
  }

  return {
    summary: summaryText,
    natural_ending_reason:
      typeof candidate.natural_ending_reason === 'string' ? candidate.natural_ending_reason : '',
    conversation_momentum_score: Number(candidate.conversation_momentum_score) || 0,
    content_quality_score: Number(candidate.content_quality_score) || 0,
    emotional_delivery_score: Number(candidate.emotional_delivery_score) || 0,
    energy_match_score: Number(candidate.energy_match_score) || 0,
    authenticity_score: Number(candidate.authenticity_score) || 0,
    follow_up_invitation_score: Number(candidate.follow_up_invitation_score) || 0,
    strengths: coerceStringArray(candidate.strengths),
    growth_edges: coerceStringArray(candidate.growth_edges),
    next_focus: nextFocus,
  };
}

function getPhaseBTurnCritique(turn: Record<string, unknown>) {
  const directCritique = typeof turn.critique === 'string' ? turn.critique.trim() : '';
  if (directCritique) {
    return directCritique;
  }

  const turnAnalysis = isRecord(turn.turn_analysis) ? turn.turn_analysis : null;
  const analysisSummary = typeof turnAnalysis?.summary === 'string' ? turnAnalysis.summary.trim() : '';
  if (analysisSummary) {
    return analysisSummary;
  }

  const analysisStatus =
    turn.analysis_status === 'ready' || turn.analysis_status === 'partial' || turn.analysis_status === 'pending'
      ? turn.analysis_status
      : null;

  if (analysisStatus === 'pending') {
    return 'Turn analysis was still pending when this replay was saved.';
  }
  if (analysisStatus === 'partial') {
    return 'Partial turn analysis was saved, but no summary text was available for this replay.';
  }
  return 'No critique stored for this turn.';
}

function MarkdownCritique({ content }: { content: string }) {
  return (
    <ReactMarkdown
      components={{
        h1: ({ children }) => <h1 className="mb-3 text-2xl font-semibold leading-snug text-slate-900">{children}</h1>,
        h2: ({ children }) => <h2 className="mb-3 text-xl font-semibold leading-snug text-slate-900">{children}</h2>,
        h3: ({ children }) => <h3 className="mb-3 text-lg font-semibold leading-snug text-slate-900">{children}</h3>,
        h4: ({ children }) => <h4 className="mb-3 text-base font-semibold leading-snug text-slate-900">{children}</h4>,
        p: ({ children }) => <p className="mb-3 text-sm leading-7 text-slate-600 last:mb-0">{children}</p>,
        strong: ({ children }) => <strong className="font-semibold text-slate-900">{children}</strong>,
        em: ({ children }) => <em className="italic">{children}</em>,
        ul: ({ children }) => <ul className="mb-3 list-disc space-y-2 pl-5 text-sm leading-7 text-slate-600">{children}</ul>,
        ol: ({ children }) => <ol className="mb-3 list-decimal space-y-2 pl-5 text-sm leading-7 text-slate-600">{children}</ol>,
        li: ({ children }) => <li>{children}</li>,
        code: ({ children }) => (
          <code className="rounded-md bg-white px-1.5 py-0.5 text-[0.9em] text-slate-800">{children}</code>
        ),
      }}
    >
      {content}
    </ReactMarkdown>
  );
}

function formatMediaLabel(mediaRef: MediaRef) {
  const sizeMb = mediaRef.upload.size_bytes ? `${(mediaRef.upload.size_bytes / (1024 * 1024)).toFixed(1)} MB` : null;
  const kind = mediaRef.kind.includes('audio') ? 'Audio' : 'Video';
  return sizeMb ? `${kind} • ${sizeMb}` : kind;
}

function ReplayVideoCard({ title, subtitle, mediaRef }: {
  title: string;
  subtitle: string;
  mediaRef: MediaRef;
}) {
  return (
    <div className="overflow-hidden rounded-[24px] border border-cream-300 bg-white shadow-sm">
      <div className="flex items-center justify-between gap-4 border-b border-cream-200 px-5 py-4">
        <div>
          <p className="text-sm font-semibold text-slate-900">{title}</p>
          <p className="mt-1 text-xs uppercase tracking-[0.16em] text-slate-400">{subtitle}</p>
        </div>
        <Badge className="border-cream-200 bg-cream-50 px-3 py-1.5 text-slate-600">
          {formatMediaLabel(mediaRef)}
        </Badge>
      </div>
      <div className="bg-slate-950 p-3">
        <video
          controls
          preload="metadata"
          playsInline
          className="aspect-video w-full rounded-[18px] bg-slate-950 object-contain"
          src={getMediaUrl(mediaRef.download_url)}
        />
      </div>
    </div>
  );
}

function ReplayChunkAccordion({ title, subtitle, items }: {
  title: string;
  subtitle: string;
  items: Array<{ id: string; label: string; detail: string; mediaRef: MediaRef }>;
}) {
  return (
    <div className="rounded-[28px] border border-cream-300 bg-white p-6 shadow-sm">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.18em] text-slate-400">{title}</p>
          <h3 className="mt-2 font-serif text-2xl font-semibold text-slate-900">
            Expand a recording chunk
          </h3>
        </div>
        <div className="rounded-full bg-cream-100 px-4 py-2 text-xs font-medium text-slate-600">
          {items.length} clips
        </div>
      </div>

      <Accordion type="single" collapsible className="mt-5 space-y-3">
        {items.map((item) => (
          <AccordionItem
            key={item.id}
            value={item.id}
            className="overflow-hidden rounded-[22px] border border-cream-200 bg-cream-50 px-0"
          >
            <AccordionTrigger className="px-5 py-4 text-left hover:no-underline">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-white text-navy-500">
                  <PlayCircle size={18} />
                </div>
                <div>
                  <p className="text-sm font-semibold text-slate-900">{item.label}</p>
                  <p className="mt-1 text-xs uppercase tracking-[0.16em] text-slate-400">{item.detail}</p>
                </div>
              </div>
            </AccordionTrigger>
            <AccordionContent className="px-5 pb-5">
              <p className="mb-3 text-xs uppercase tracking-[0.16em] text-slate-400">{subtitle}</p>
              <div className="overflow-hidden rounded-[18px] bg-slate-950 p-3">
                <video
                  controls
                  preload="metadata"
                  playsInline
                  className="aspect-video w-full rounded-[14px] bg-slate-950 object-contain"
                  src={getMediaUrl(item.mediaRef.download_url)}
                />
              </div>
            </AccordionContent>
          </AccordionItem>
        ))}
      </Accordion>
    </div>
  );
}

function ScoreTile({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-[24px] bg-cream-50 p-4">
      <p className="text-xs font-semibold uppercase tracking-widest text-slate-400">{label}</p>
      <p className="mt-3 text-3xl font-semibold text-slate-900">{value}</p>
    </div>
  );
}

function BulletList({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="rounded-[28px] border border-cream-200 bg-white p-5">
      <p className="text-xs font-semibold uppercase tracking-widest text-slate-400">{title}</p>
      {items.length ? (
        <ul className="mt-4 space-y-3 text-sm leading-6 text-slate-700">
          {items.map((item, index) => (
            <li key={`${title}-${index}`} className="flex gap-3">
              <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-navy-500" />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-4 text-sm text-slate-500">No notes stored.</p>
      )}
    </div>
  );
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
  const roundVideoRefs = session.media_refs
    .filter((mediaRef) => mediaRef.kind === 'video' && typeof mediaRef.round_index === 'number')
    .sort((left, right) => Number(left.round_index) - Number(right.round_index));

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
              <div className="mt-2">
                <MarkdownCritique content={String(round.critique || 'No critique stored for this round.')} />
              </div>
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

      {roundVideoRefs.length ? (
        <div className="space-y-4">
          {roundVideoRefs.map((mediaRef) => (
            <ReplayVideoCard
              key={`${mediaRef.kind}-${mediaRef.round_index}`}
              title={`Round ${Number(mediaRef.round_index) + 1} Recording`}
              subtitle="Full round video"
              mediaRef={mediaRef}
            />
          ))}
        </div>
      ) : null}
    </div>
  );
}

function PhaseBReplayDetail({ session }: { session: PersistedSession }) {
  const summary = getSessionSummary(session);
  const setup = isRecord(session.setup) ? session.setup : {};
  const finalReport = getPhaseBFinalReport(summary);
  const turns = Array.isArray(summary.turns)
    ? summary.turns.filter((turn): turn is Record<string, unknown> => isRecord(turn))
    : [];
  const chunkVideoRefs = session.media_refs
    .filter((mediaRef) => mediaRef.kind === 'video_upload' && typeof mediaRef.turn_index === 'number' && typeof mediaRef.chunk_index === 'number')
    .sort((left, right) => {
      const turnDelta = Number(left.turn_index) - Number(right.turn_index);
      return turnDelta !== 0 ? turnDelta : Number(left.chunk_index) - Number(right.chunk_index);
    });
  const chunkItems = chunkVideoRefs.map((mediaRef) => ({
    id: `turn-${mediaRef.turn_index}-chunk-${mediaRef.chunk_index}`,
    label: `Turn ${Number(mediaRef.turn_index) + 1} • Chunk ${Number(mediaRef.chunk_index) + 1}`,
    detail: formatMediaLabel(mediaRef),
    mediaRef,
  }));

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
              <div className="mt-3">
                <MarkdownCritique content={getPhaseBTurnCritique(turn)} />
              </div>
            </div>
          )) : (
            <p className="text-sm text-slate-500">No turn-level critiques were stored for this session.</p>
          )}
        </div>
      </div>

      {finalReport ? (
        <div className="rounded-[28px] border border-cream-300 bg-white p-6 shadow-sm">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Final Report</p>
              <h3 className="mt-2 font-['Playfair_Display'] text-2xl font-semibold text-slate-900">
                Conversation closeout
              </h3>
            </div>
            <Badge className="border-cream-200 bg-cream-50 px-3 py-1.5 text-slate-700">
              Stored with replay
            </Badge>
          </div>

          <p className="mt-5 text-base leading-7 text-slate-700">{finalReport.summary}</p>

          <div className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            <ScoreTile label="Momentum" value={finalReport.conversation_momentum_score} />
            <ScoreTile label="Content" value={finalReport.content_quality_score} />
            <ScoreTile label="Delivery" value={finalReport.emotional_delivery_score} />
            <ScoreTile label="Energy" value={finalReport.energy_match_score} />
            <ScoreTile label="Authenticity" value={finalReport.authenticity_score} />
            <ScoreTile label="Follow-up" value={finalReport.follow_up_invitation_score} />
          </div>

          <div className="mt-6 grid gap-5 lg:grid-cols-[1.1fr_0.9fr]">
            <div className="rounded-[28px] bg-cream-50 p-5">
              <p className="text-xs font-semibold uppercase tracking-widest text-slate-400">Why it ended</p>
              <p className="mt-3 text-sm leading-6 text-slate-700">
                {finalReport.natural_ending_reason || 'No ending note stored for this conversation.'}
              </p>
            </div>
            <div className="rounded-[28px] border border-navy-100 bg-navy-50 p-5">
              <p className="text-xs font-semibold uppercase tracking-widest text-navy-500">Next focus</p>
              <p className="mt-3 text-sm leading-6 text-navy-900">
                {finalReport.next_focus || 'No next focus stored for this conversation.'}
              </p>
            </div>
          </div>

          <div className="mt-6 grid gap-5 lg:grid-cols-2">
            <BulletList title="Strengths" items={finalReport.strengths} />
            <BulletList title="Growth edges" items={finalReport.growth_edges} />
          </div>
        </div>
      ) : null}

      {chunkItems.length ? (
        <ReplayChunkAccordion
          title="Replay Clips"
          subtitle="Turn chunk recording"
          items={chunkItems}
        />
      ) : null}
    </div>
  );
}

function PhaseCReplayDetail({ session }: { session: PersistedSession }) {
  const scorecard = getPhaseCScorecardFromSession(session);
  const writtenSummary = getPhaseCWrittenSummary(session);
  const mergedChunks = getPhaseCMergedChunks(session);
  const transcriptWords = getPhaseCTranscriptWords(session);
  const fillerWordsFound = getPhaseCFillerWordsFound(session);
  const patternsData = getPhaseCPatterns(session);
  const wordCorrelations = getPhaseCWordCorrelations(session);
  const chunkVideoRefs = session.media_refs
    .filter((mediaRef) => mediaRef.kind === 'video_upload' && typeof mediaRef.chunk_index === 'number')
    .sort((left, right) => Number(left.chunk_index) - Number(right.chunk_index));
  const chunkItems = chunkVideoRefs.map((mediaRef) => {
    const mergedChunk = mergedChunks.find((chunk) => chunk.chunk_index === mediaRef.chunk_index);
    const detailParts = [
      `Chunk ${Number(mediaRef.chunk_index) + 1}`,
      mergedChunk?.transcript_segment ? mergedChunk.transcript_segment.slice(0, 64) : formatMediaLabel(mediaRef),
    ];

    return {
      id: `chunk-${mediaRef.chunk_index}`,
      label: `Chunk ${Number(mediaRef.chunk_index) + 1}`,
      detail: detailParts.filter(Boolean).join(' • '),
      mediaRef,
    };
  });

  return (
    <div className="space-y-6">
      <PhaseCScorecard scorecard={scorecard} writtenSummary={writtenSummary} />
      <EmotionTimeline chunks={mergedChunks} />
      <WordAudit
        transcriptWords={transcriptWords}
        fillerWordsFound={fillerWordsFound}
      />
      <PatternsDetected
        patterns={patternsData}
        wordCorrelations={wordCorrelations}
      />
      {chunkItems.length ? (
        <ReplayChunkAccordion
          title="Recording Chunks"
          subtitle="Free speaking chunk"
          items={chunkItems}
        />
      ) : null}
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
    if (nextSessionId === selectedSessionId) {
      return;
    }

    const nextParams = new URLSearchParams(searchParams.toString());
    if (nextSessionId) {
      nextParams.set('session', nextSessionId);
    } else {
      nextParams.delete('session');
    }

    const nextUrl = nextParams.toString() ? `/replays?${nextParams.toString()}` : '/replays';
    setSelectedSessionId(nextSessionId);
    startTransition(() => {
      router.replace(nextUrl, { scroll: false });
    });
  }, [router, searchParams, selectedSessionId]);

  const selectedModeMeta = useMemo(() => {
    if (!selectedSession) {
      return null;
    }
    return MODE_META[selectedSession.mode];
  }, [selectedSession]);

  const dialogTitle = selectedSession?.mode_label ?? 'Replay details';
  const dialogDescription = selectedSession
    ? formatDateLabel(selectedSession.completed_at || selectedSession.updated_at || selectedSession.created_at)
    : selectedSessionLoading
      ? 'Loading replay details.'
      : selectedSessionError
        ? 'Replay details could not be loaded.'
        : 'Select a session to review its replay.';

  useEffect(() => {
    if (!selectedSessionId) {
      return;
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        updateSelectedSessionId(null);
      }
    };

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    window.addEventListener('keydown', handleKeyDown);

    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [selectedSessionId, updateSelectedSessionId]);

  return (
    <div className="mx-auto max-w-4xl">
      <div className="mb-8">
        <h1 className="font-serif text-2xl font-semibold text-slate-900">
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
              <p className="font-serif text-2xl font-semibold text-slate-900">
                No sessions yet
              </p>
              <p className="mt-2 text-sm text-slate-500">
                Complete a practice session to see its persisted replay here.
              </p>
            </div>
          )}
        </div>
      )}

      {selectedSessionId && (
        <div className="fixed inset-0 z-[90]">
          <button
            type="button"
            aria-label="Close replay"
            className="absolute inset-0 bg-black/45"
            onClick={() => updateSelectedSessionId(null)}
          />

          <div className="absolute inset-x-4 top-1/2 z-[91] mx-auto flex max-h-[88vh] w-full max-w-5xl -translate-y-1/2 flex-col overflow-hidden rounded-[28px] border border-cream-300 bg-cream-50 shadow-2xl">
            <div className="flex items-start justify-between gap-4 border-b border-cream-200 px-6 py-5 text-left">
              <div className="flex items-center gap-3">
                {selectedModeMeta && (
                  <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-cream-100">
                    <selectedModeMeta.icon size={20} className={selectedModeMeta.iconClassName} />
                  </div>
                )}
                <div>
                  <h2 className="font-serif text-2xl text-slate-900">
                    {dialogTitle}
                  </h2>
                  <p className="mt-1 text-sm text-slate-500">{dialogDescription}</p>
                </div>
              </div>

              <button
                type="button"
                onClick={() => updateSelectedSessionId(null)}
                className="rounded-full bg-white p-2 text-slate-500 transition-colors hover:text-slate-900"
              >
                <X size={18} />
              </button>
            </div>

            <div className="overflow-y-auto p-6">
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
          </div>
        </div>
      )}
    </div>
  );
}
