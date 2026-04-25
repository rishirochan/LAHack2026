'use client';

import { motion } from 'framer-motion';
import {
  AlertTriangle,
  Gauge,
  ListChecks,
  MessageSquareQuote,
  Repeat2,
  Sparkles,
} from 'lucide-react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ReferenceArea,
  XAxis,
  YAxis,
} from 'recharts';

import { Badge } from '@/components/ui/badge';
import { ChartContainer, ChartTooltip, ChartTooltipContent } from '@/components/ui/chart';
import type { PhaseCRepeatedPhrase, PhaseCRepeatedWord, PhaseCScorecard } from '@/lib/phase-c-api';

type PhaseCScorecardProps = {
  scorecard: PhaseCScorecard | null;
  writtenSummary?: string | null;
};

type ScoreTone = {
  valueClassName: string;
  badgeClassName: string;
};

const CARD_MOTION = {
  initial: { opacity: 0, y: 18 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.32 },
};

function getScoreTone(score: number): ScoreTone {
  if (score >= 80) {
    return {
      valueClassName: 'text-emerald-600',
      badgeClassName: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    };
  }

  if (score >= 60) {
    return {
      valueClassName: 'text-amber-500',
      badgeClassName: 'bg-amber-50 text-amber-700 border-amber-200',
    };
  }

  return {
    valueClassName: 'text-rose-500',
    badgeClassName: 'bg-rose-50 text-rose-700 border-rose-200',
  };
}

function formatTrend(trend: string) {
  switch (trend) {
    case 'speeding_up':
      return 'Speeding up';
    case 'slowing_down':
      return 'Slowing down';
    case 'stable':
      return 'Stable';
    default:
      return 'Mixed';
  }
}

function repeatedPills(
  repeatedWords: PhaseCRepeatedWord[],
  repeatedPhrases: PhaseCRepeatedPhrase[],
): Array<{ label: string; count: number }> {
  return [
    ...repeatedWords.map((item) => ({ label: item.word, count: item.count })),
    ...repeatedPhrases.map((item) => ({ label: item.phrase, count: item.count })),
  ].slice(0, 6);
}

export function PhaseCScorecard({ scorecard, writtenSummary }: PhaseCScorecardProps) {
  if (!scorecard) {
    return (
      <div className="rounded-[28px] border border-cream-300 bg-white p-6 shadow-sm">
        <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Scorecard</p>
        <p className="mt-4 text-sm leading-6 text-slate-500">
          Scorecard data is not available for this session yet.
        </p>
      </div>
    );
  }

  const scoreTone = getScoreTone(scorecard.overall_score);
  const pacingData = scorecard.wpm_by_chunk.map((chunk) => ({
    chunk: `C${Number(chunk.chunk_index) + 1}`,
    wpm: Number(chunk.wpm ?? 0),
  }));
  const fillerData = Object.entries(scorecard.filler_word_breakdown ?? {})
    .map(([word, count]) => ({ word, count: Number(count) }))
    .sort((left, right) => right.count - left.count);
  const repeatedItems = repeatedPills(
    scorecard.repetition?.top_repeated_words ?? [],
    scorecard.repetition?.top_repeated_phrases ?? [],
  );
  const flatness = scorecard.emotion_flags?.emotional_flatness;
  const nervousness = scorecard.emotion_flags?.nervousness_persistence;
  const targetBand = scorecard.pacing_drift?.target_band ?? [120, 170];

  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <motion.div
          {...CARD_MOTION}
          className="rounded-[28px] border border-cream-300 bg-white p-6 shadow-sm"
        >
          <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Overall Score</p>
          <div className="mt-4 flex items-end justify-between gap-4">
            <div>
              <p className={`font-['Playfair_Display'] text-6xl font-semibold ${scoreTone.valueClassName}`}>
                {scorecard.overall_score}
              </p>
              <p className="mt-2 text-sm text-slate-500">
                {scorecard.duration_seconds.toFixed(1)} seconds analyzed
              </p>
            </div>
            <Badge className={scoreTone.badgeClassName}>Broker score</Badge>
          </div>
        </motion.div>

        <motion.div
          {...CARD_MOTION}
          transition={{ duration: 0.32, delay: 0.04 }}
          className="rounded-[28px] border border-cream-300 bg-white p-6 shadow-sm"
        >
          <div className="flex items-center gap-2 text-slate-700">
            <Gauge size={16} className="text-navy-500" />
            <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Pacing</p>
          </div>
          <div className="mt-4 flex items-center justify-between gap-4">
            <div>
              <p className="text-3xl font-semibold text-slate-900">{scorecard.average_wpm}</p>
              <p className="mt-1 text-sm text-slate-500">
                Target {targetBand[0]}-{targetBand[1]} WPM
              </p>
            </div>
            <Badge className="border-cream-200 bg-cream-50 text-slate-700">
              {formatTrend(scorecard.pacing_drift?.trend ?? 'mixed')}
            </Badge>
          </div>
        </motion.div>

        <motion.div
          {...CARD_MOTION}
          transition={{ duration: 0.32, delay: 0.08 }}
          className="rounded-[28px] border border-cream-300 bg-white p-6 shadow-sm"
        >
          <div className="flex items-center gap-2 text-slate-700">
            <AlertTriangle size={16} className="text-amber-500" />
            <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Filler Words</p>
          </div>
          <p className="mt-4 text-3xl font-semibold text-slate-900">{scorecard.filler_word_count}</p>
          <p className="mt-1 text-sm text-slate-500">
            {fillerData.length ? 'Most common fillers are charted below.' : 'No filler words were detected.'}
          </p>
        </motion.div>
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
        <motion.div
          {...CARD_MOTION}
          transition={{ duration: 0.32, delay: 0.12 }}
          className="rounded-[28px] border border-cream-300 bg-white p-6 shadow-sm"
        >
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Pacing Trend</p>
              <h3 className="mt-2 font-['Playfair_Display'] text-2xl font-semibold text-slate-900">
                WPM across chunks
              </h3>
            </div>
            <div className="rounded-full bg-cream-100 px-4 py-2 text-xs font-medium text-slate-600">
              Fast: {scorecard.pacing_drift.too_fast_chunks} | Slow: {scorecard.pacing_drift.too_slow_chunks}
            </div>
          </div>

          <ChartContainer
            config={{ wpm: { label: 'Words per minute', color: '#153e75' } }}
            className="mt-6 h-52 w-full aspect-auto"
          >
            <LineChart data={pacingData} margin={{ left: 0, right: 0, top: 12, bottom: 0 }}>
              <CartesianGrid vertical={false} stroke="#eadcc2" />
              <XAxis axisLine={false} dataKey="chunk" tickLine={false} />
              <YAxis axisLine={false} tickLine={false} width={36} />
              <ChartTooltip
                content={<ChartTooltipContent labelKey="wpm" formatter={(value) => `${value} WPM`} />}
              />
              <ReferenceArea y1={targetBand[0]} y2={targetBand[1]} fill="#f6efdc" fillOpacity={0.85} />
              <Line
                dataKey="wpm"
                stroke="var(--color-wpm)"
                strokeWidth={3}
                type="monotone"
                dot={{ r: 4, fill: '#153e75' }}
                activeDot={{ r: 5 }}
              />
            </LineChart>
          </ChartContainer>
        </motion.div>

        <motion.div
          {...CARD_MOTION}
          transition={{ duration: 0.32, delay: 0.16 }}
          className="rounded-[28px] border border-cream-300 bg-white p-6 shadow-sm"
        >
          <div className="flex items-center gap-2 text-slate-700">
            <AlertTriangle size={16} className="text-amber-500" />
            <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Filler Breakdown</p>
          </div>

          {fillerData.length ? (
            <ChartContainer
              config={{ count: { label: 'Count', color: '#f0b44c' } }}
              className="mt-6 h-52 w-full aspect-auto"
            >
              <BarChart data={fillerData} layout="vertical" margin={{ top: 0, right: 0, left: 12, bottom: 0 }}>
                <CartesianGrid horizontal={false} stroke="#efe4d0" />
                <XAxis axisLine={false} dataKey="count" tickLine={false} type="number" />
                <YAxis axisLine={false} dataKey="word" tickLine={false} type="category" width={64} />
                <ChartTooltip
                  content={<ChartTooltipContent labelKey="count" formatter={(value) => `${value} hits`} />}
                />
                <Bar dataKey="count" radius={[10, 10, 10, 10]}>
                  {fillerData.map((item) => (
                    <Cell key={item.word} fill="#f0b44c" />
                  ))}
                </Bar>
              </BarChart>
            </ChartContainer>
          ) : (
            <div className="mt-6 rounded-[24px] bg-emerald-50 px-4 py-5 text-sm text-emerald-800">
              No filler words were counted in this recording.
            </div>
          )}
        </motion.div>
      </div>

      <div className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
        <motion.div
          {...CARD_MOTION}
          transition={{ duration: 0.32, delay: 0.2 }}
          className="rounded-[28px] border border-cream-300 bg-white p-6 shadow-sm"
        >
          <div className="flex items-center gap-2 text-slate-700">
            <Repeat2 size={16} className="text-navy-500" />
            <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Repetition</p>
          </div>

          {repeatedItems.length ? (
            <div className="mt-5 flex flex-wrap gap-2">
              {repeatedItems.map((item) => (
                <Badge
                  key={`${item.label}-${item.count}`}
                  className="border-cream-200 bg-cream-50 px-3 py-1.5 text-slate-700"
                >
                  {item.label} x{item.count}
                </Badge>
              ))}
            </div>
          ) : (
            <p className="mt-5 text-sm leading-6 text-slate-500">
              No repeated words or phrases stood out strongly enough to flag.
            </p>
          )}
        </motion.div>

        <motion.div
          {...CARD_MOTION}
          transition={{ duration: 0.32, delay: 0.24 }}
          className="rounded-[28px] border border-cream-300 bg-white p-6 shadow-sm"
        >
          <div className="flex items-center gap-2 text-slate-700">
            <Sparkles size={16} className="text-amber-500" />
            <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Emotion Flags</p>
          </div>

          <div className="mt-5 grid gap-4 md:grid-cols-2">
            <div className="rounded-[24px] bg-cream-50 p-4">
              <p className="text-sm font-semibold text-slate-900">Flatness</p>
              <p className="mt-2 text-sm text-slate-600">
                {flatness?.triggered ? 'Triggered' : 'Not triggered'}
              </p>
              <p className="mt-1 text-xs text-slate-500">
                Longest neutral run: {Number(flatness?.longest_neutral_run_seconds ?? 0).toFixed(1)}s
              </p>
            </div>
            <div className="rounded-[24px] bg-cream-50 p-4">
              <p className="text-sm font-semibold text-slate-900">Nervousness</p>
              <p className="mt-2 text-sm text-slate-600">
                {nervousness?.triggered ? 'Triggered' : 'Not triggered'}
              </p>
              <p className="mt-1 text-xs text-slate-500">
                Nervous chunk ratio: {Math.round(Number(nervousness?.nervous_chunk_ratio ?? 0) * 100)}%
              </p>
            </div>
          </div>
        </motion.div>
      </div>

      <div className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
        <motion.div
          {...CARD_MOTION}
          transition={{ duration: 0.32, delay: 0.28 }}
          className="rounded-[28px] border border-cream-300 bg-white p-6 shadow-sm"
        >
          <div className="flex items-center gap-2 text-slate-700">
            <ListChecks size={16} className="text-emerald-600" />
            <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Strengths & Improvements</p>
          </div>
          <div className="mt-5 grid gap-5 md:grid-cols-2">
            <div>
              <p className="text-sm font-semibold text-slate-900">Strengths</p>
              <div className="mt-3 space-y-2">
                {scorecard.strengths.map((item) => (
                  <div key={item} className="rounded-2xl bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
                    {item}
                  </div>
                ))}
              </div>
            </div>
            <div>
              <p className="text-sm font-semibold text-slate-900">Improvements</p>
              <div className="mt-3 space-y-2">
                {scorecard.improvement_areas.map((item) => (
                  <div key={item} className="rounded-2xl bg-amber-50 px-4 py-3 text-sm text-amber-900">
                    {item}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </motion.div>

        <motion.div
          {...CARD_MOTION}
          transition={{ duration: 0.32, delay: 0.32 }}
          className="rounded-[28px] border border-cream-300 bg-white p-6 shadow-sm"
        >
          <div className="flex items-center gap-2 text-slate-700">
            <MessageSquareQuote size={16} className="text-navy-500" />
            <p className="text-xs uppercase tracking-[0.18em] text-slate-400">AI Coaching Summary</p>
          </div>
          <div className="mt-5 rounded-[24px] border border-cream-200 bg-[linear-gradient(135deg,#fff9ee_0%,#fdf3dd_100%)] p-5">
            <p className="text-sm leading-7 text-slate-700">
              {writtenSummary || 'No written summary was returned for this session.'}
            </p>
          </div>
        </motion.div>
      </div>
    </div>
  );
}
