'use client';

import { useMemo, useState } from 'react';
import { motion } from 'framer-motion';

import type { PhaseCMergedAnalysisChunk } from '@/lib/phase-c-api';

type EmotionTimelineProps = {
  chunks: PhaseCMergedAnalysisChunk[];
  loading?: boolean;
  errorMessage?: string;
};

const EMOTION_COLORS: Record<string, string> = {
  neutral: 'bg-slate-300',
  confidence: 'bg-emerald-500',
  joy: 'bg-amber-400',
  happiness: 'bg-amber-400',
  surprise: 'bg-orange-400',
  sadness: 'bg-sky-500',
  fear: 'bg-rose-400',
  nervousness: 'bg-rose-500',
  anger: 'bg-red-500',
  disgust: 'bg-lime-600',
  contempt: 'bg-violet-500',
};

function formatTimestamp(milliseconds: number) {
  const totalSeconds = Math.max(0, Math.floor(milliseconds / 1000));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, '0')}`;
}

function toTitleCase(value: string | null | undefined) {
  if (!value) {
    return 'Unknown';
  }

  return value
    .replaceAll('_', ' ')
    .split(' ')
    .filter(Boolean)
    .map((part) => part[0]?.toUpperCase() + part.slice(1))
    .join(' ');
}

function getSegmentColor(emotion: string | null | undefined) {
  if (!emotion) {
    return 'bg-cream-200';
  }

  return EMOTION_COLORS[emotion.toLowerCase()] ?? 'bg-navy-500';
}

export function EmotionTimeline({ chunks, loading = false, errorMessage = '' }: EmotionTimelineProps) {
  const [activeIndex, setActiveIndex] = useState(0);

  const normalizedChunks = useMemo(
    () =>
      chunks
        .filter((chunk) => typeof chunk.t_start === 'number' && typeof chunk.t_end === 'number')
        .map((chunk) => {
          const dominantEmotion = chunk.dominant_video_emotion || chunk.dominant_audio_emotion;
          const confidence = chunk.video_confidence ?? chunk.audio_confidence ?? null;
          return {
            ...chunk,
            dominantEmotion,
            confidence,
            durationMs: Math.max(1, chunk.t_end - chunk.t_start),
          };
        }),
    [chunks],
  );

  const totalDurationMs = normalizedChunks.reduce((total, chunk) => total + chunk.durationMs, 0);
  const activeChunk = normalizedChunks[activeIndex] ?? normalizedChunks[0] ?? null;

  const visibleLegend = useMemo(() => {
    const entries: { key: string; emotion: string | null }[] = [];
    const seen = new Set<string>();
    for (const chunk of normalizedChunks) {
      const emotion = chunk.dominantEmotion;
      const dedupeKey = emotion ?? '__null__';
      if (seen.has(dedupeKey)) {
        continue;
      }
      seen.add(dedupeKey);
      entries.push({
        key: emotion ?? `no-emotion-${chunk.chunk_index}`,
        emotion,
      });
      if (entries.length >= 6) {
        break;
      }
    }
    return entries;
  }, [normalizedChunks]);

  if (loading) {
    return (
      <div className="rounded-[28px] border border-cream-300 bg-white p-6 shadow-sm">
        <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Emotion Timeline</p>
        <p className="mt-4 text-sm leading-6 text-slate-500">
          Loading persisted chunk analysis...
        </p>
      </div>
    );
  }

  if (errorMessage) {
    return (
      <div className="rounded-[28px] border border-cream-300 bg-white p-6 shadow-sm">
        <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Emotion Timeline</p>
        <p className="mt-4 text-sm leading-6 text-rose-600">
          {errorMessage}
        </p>
      </div>
    );
  }

  if (!normalizedChunks.length) {
    return (
      <div className="rounded-[28px] border border-cream-300 bg-white p-6 shadow-sm">
        <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Emotion Timeline</p>
        <p className="mt-4 text-sm leading-6 text-slate-500">
          Chunk-level emotion data is not available for this session yet.
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-[28px] border border-cream-300 bg-white p-6 shadow-sm">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Emotion Timeline</p>
          <h3 className="mt-2 font-serif text-2xl font-semibold text-slate-900">
            Chunk-by-chunk delivery shifts
          </h3>
        </div>
        <div className="rounded-full bg-cream-100 px-4 py-2 text-xs font-medium text-slate-600">
          {normalizedChunks.length} chunks
        </div>
      </div>

      <div className="mt-6 flex overflow-hidden rounded-full border border-cream-200 bg-cream-100">
        {normalizedChunks.map((chunk, index) => {
          const widthPercent = (chunk.durationMs / totalDurationMs) * 100;
          return (
            <motion.button
              key={`${chunk.chunk_index}-${chunk.t_start}`}
              type="button"
              initial={{ opacity: 0, scaleX: 0.94 }}
              animate={{ opacity: 1, scaleX: 1 }}
              transition={{ duration: 0.25, delay: index * 0.04 }}
              onMouseEnter={() => setActiveIndex(index)}
              onFocus={() => setActiveIndex(index)}
              className={`h-10 transition-opacity hover:opacity-100 focus:opacity-100 focus:outline-none ${
                activeIndex === index ? 'opacity-100' : 'opacity-85'
              } ${getSegmentColor(chunk.dominantEmotion)}`}
              style={{ width: `${widthPercent}%` }}
              aria-label={`Chunk ${chunk.chunk_index + 1}: ${toTitleCase(chunk.dominantEmotion)}`}
            />
          );
        })}
      </div>

      {activeChunk && (
        <div className="mt-5 rounded-[24px] border border-cream-200 bg-cream-50 p-5">
          <div className="flex flex-wrap items-center gap-3">
            <span className="rounded-full bg-white px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
              Chunk {activeChunk.chunk_index + 1}
            </span>
            <span className="text-sm font-medium text-slate-700">
              {formatTimestamp(activeChunk.t_start)} - {formatTimestamp(activeChunk.t_end)}
            </span>
            <span className="text-sm text-slate-500">
              {toTitleCase(activeChunk.dominantEmotion)}
              {typeof activeChunk.confidence === 'number'
                ? ` (${Math.round(activeChunk.confidence * 100)}% confidence)`
                : ''}
            </span>
          </div>
          <p className="mt-3 text-sm leading-6 text-slate-600">
            {activeChunk.transcript_segment || 'No transcript segment was available for this chunk.'}
          </p>
        </div>
      )}

      <div className="mt-5 flex flex-wrap gap-2">
        {visibleLegend.map(({ key, emotion }) => (
          <div
            key={key}
            className="inline-flex items-center gap-2 rounded-full bg-cream-50 px-3 py-1.5 text-xs text-slate-600"
          >
            <span className={`h-2.5 w-2.5 rounded-full ${getSegmentColor(emotion)}`} />
            {toTitleCase(emotion)}
          </div>
        ))}
      </div>
    </div>
  );
}
