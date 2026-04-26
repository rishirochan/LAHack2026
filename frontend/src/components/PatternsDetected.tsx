'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Brain, ChevronDown, ChevronUp } from 'lucide-react';

import type { PatternBadge, PatternSeverity, WordCorrelation } from '@/lib/phase-c-api';

type PatternsDetectedProps = {
  patterns: PatternBadge[];
  wordCorrelations: WordCorrelation[];
};

function formatTimestamp(ms: number) {
  const totalSeconds = Math.max(0, Math.floor(ms / 1000));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, '0')}`;
}

const SEVERITY_BADGE: Record<PatternSeverity, { bg: string; text: string; border: string }> = {
  critical: {
    bg: 'bg-rose-50',
    text: 'text-rose-700',
    border: 'border-rose-200',
  },
  warning: {
    bg: 'bg-amber-50',
    text: 'text-amber-700',
    border: 'border-amber-200',
  },
  positive: {
    bg: 'bg-emerald-50',
    text: 'text-emerald-700',
    border: 'border-emerald-200',
  },
  informational: {
    bg: 'bg-sky-50',
    text: 'text-sky-700',
    border: 'border-sky-200',
  },
};

const INSIGHT_DOT: Record<string, string> = {
  face_voice_correlated: 'bg-rose-500',
  face_voice_mismatch: 'bg-amber-400',
  nervousness_signal: 'bg-rose-400',
  strength_moment: 'bg-emerald-500',
  filler_pattern: 'bg-amber-400',
  neutral: 'bg-slate-400',
};

const INSIGHT_LABEL: Record<string, string> = {
  face_voice_correlated: 'face + voice correlated',
  face_voice_mismatch: 'face–voice mismatch',
  nervousness_signal: 'nervousness signal',
  strength_moment: 'strength moment',
  filler_pattern: 'filler pattern',
};

export function PatternsDetected({ patterns, wordCorrelations }: PatternsDetectedProps) {
  const [isExpanded, setIsExpanded] = useState(true);
  const [visibleInsightCount, setVisibleInsightCount] = useState(5);

  const hasData = patterns.length > 0 || wordCorrelations.length > 0;

  if (!hasData) {
    return (
      <div className="rounded-2xl border border-cream-300 bg-cream-50 p-6 shadow-sm">
        <div className="flex items-center gap-2 text-slate-700">
          <Brain size={16} className="text-navy-500" />
          <p className="text-xs uppercase tracking-widest text-slate-400">
            Patterns Detected by Feedback Broker
          </p>
        </div>
        <p className="mt-4 text-sm leading-6 text-slate-500">
          No pattern data is available for this session yet.
        </p>
      </div>
    );
  }

  const sortedCorrelations = [...wordCorrelations].sort((a, b) => {
    // Sort chronologically by timestamp ascending
    return a.timestamp_ms - b.timestamp_ms;
  });

  const visibleCorrelations = sortedCorrelations.slice(0, visibleInsightCount);
  const hasMoreInsights = sortedCorrelations.length > visibleInsightCount;

  return (
    <motion.div
      initial={{ opacity: 0, y: 18 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.32 }}
      className="rounded-2xl border border-cream-300 bg-cream-50 p-6 shadow-sm"
    >
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-slate-700">
            <Brain size={16} className="text-navy-500" />
            <p className="text-xs uppercase tracking-widest text-slate-400">
              Patterns Detected by Feedback Broker
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={() => setIsExpanded((prev) => !prev)}
          className="flex items-center gap-1 rounded-lg bg-cream-200 px-3 py-1.5 text-xs font-medium text-slate-600 transition-colors hover:bg-cream-300"
        >
          {isExpanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
          {isExpanded ? 'Collapse' : 'Expand'}
        </button>
      </div>

      {/* Pattern Badges */}
      {patterns.length > 0 && (
        <div className="mt-5 flex flex-wrap gap-2">
          {patterns.map((pattern, index) => {
            const style = SEVERITY_BADGE[pattern.severity] ?? SEVERITY_BADGE.informational;
            return (
              <motion.span
                key={`${pattern.category}-${index}`}
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.2, delay: index * 0.04 }}
                className={`inline-flex items-center gap-1.5 rounded-full border px-3.5 py-2 text-xs font-medium ${style.bg} ${style.text} ${style.border}`}
              >
                {pattern.label}
              </motion.span>
            );
          })}
        </div>
      )}

      {/* Timestamped Insights */}
      <AnimatePresence>
        {isExpanded && visibleCorrelations.length > 0 && (
          <motion.div
            key="insights"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.25 }}
            className="overflow-hidden"
          >
            <div className="mt-6 space-y-4">
              {visibleCorrelations.map((correlation, index) => {
                const dotColor = INSIGHT_DOT[correlation.insight_type] ?? 'bg-slate-400';
                const insightLabel = INSIGHT_LABEL[correlation.insight_type] ?? correlation.insight_type;

                return (
                  <motion.div
                    key={`${correlation.word}-${correlation.timestamp_ms}-${index}`}
                    initial={{ opacity: 0, x: -8 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.2, delay: index * 0.04 }}
                    className="flex gap-3"
                  >
                    <div className="mt-1.5 flex flex-col items-center">
                      <span className={`h-3 w-3 rounded-full ${dotColor}`} />
                      {index < visibleCorrelations.length - 1 && (
                        <div className="mt-1 w-px flex-1 bg-cream-200" />
                      )}
                    </div>
                    <div className="flex-1 pb-1">
                      <p className="text-sm leading-6 text-slate-700">
                        {correlation.message
                          ? correlation.message
                          : `At ${formatTimestamp(correlation.timestamp_ms)} when you said "${correlation.word}".`}
                      </p>
                      <div className="mt-1.5 flex flex-wrap items-center gap-2 text-xs text-slate-400">
                        <span>{formatTimestamp(correlation.timestamp_ms)}</span>
                        <span>·</span>
                        <span>&ldquo;{correlation.word}&rdquo;</span>
                        <span>·</span>
                        <span>{insightLabel}</span>
                      </div>
                    </div>
                  </motion.div>
                );
              })}
            </div>

            {hasMoreInsights && (
              <button
                type="button"
                onClick={() => setVisibleInsightCount((prev) => prev + 10)}
                className="mt-4 inline-flex items-center gap-2 rounded-lg bg-cream-200 px-4 py-2 text-xs font-medium text-slate-600 transition-colors hover:bg-cream-300"
              >
                Show {Math.min(sortedCorrelations.length - visibleInsightCount, 10)} more insights
              </button>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {isExpanded && visibleCorrelations.length === 0 && patterns.length > 0 && (
        <div className="mt-5 rounded-xl bg-cream-200 px-4 py-4 text-sm text-slate-500">
          No word-level correlations were generated — patterns above are based on aggregate session data.
        </div>
      )}
    </motion.div>
  );
}
