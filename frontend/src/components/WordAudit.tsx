'use client';

import { useMemo, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { BookOpenText, X } from 'lucide-react';

import type { TranscriptWord } from '@/lib/phase-c-api';

/** Filler words that should be colored amber. */
const STRICT_FILLER_WORDS = new Set([
  'um', 'uh',
]);

const CONTEXTUAL_FILLER_WORDS = new Set([
  'like', 'so', 'actually', 'basically', 'literally',
]);

/** Multi-word fillers checked by scanning consecutive tokens. */
const FILLER_PHRASES = ['you know', 'i would say', 'sort of'];
const PAUSE_FILLER_THRESHOLD_MS = 250;

/** Strong words that should be colored green. */
const STRONG_WORDS = new Set([
  'leverage', 'achieved', 'led', 'directly', 'committed',
  'delivered', 'drove', 'improved', 'launched', 'built',
  'executed', 'resolved', 'optimized', 'exceeded', 'transformed',
]);

type ChipCategory = 'filler' | 'repeated' | 'strong' | 'plain';

type AuditChip = {
  word: string;
  normalized: string;
  category: ChipCategory;
  count: number;
  timestampMs: number;
  endMs: number;
  index: number;
};

type WordAuditProps = {
  transcriptWords: TranscriptWord[];
  fillerWordsFound: string[];
};

function formatTimestamp(ms: number) {
  const totalSeconds = Math.max(0, Math.floor(ms / 1000));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, '0')}`;
}

function normalize(word: string) {
  return word.trim().toLowerCase().replace(/[.,!?;:"'()[\]{}]/g, '');
}

function pauseBeforeMs(words: TranscriptWord[], index: number) {
  if (index <= 0) {
    return 0;
  }
  return Math.max(0, words[index].start_ms - words[index - 1].end_ms);
}

function pauseAfterMs(words: TranscriptWord[], index: number) {
  if (index + 1 >= words.length) {
    return 0;
  }
  return Math.max(0, words[index + 1].start_ms - words[index].end_ms);
}

function looksLikeContextualFiller(words: TranscriptWord[], normalizedTokens: string[], index: number) {
  const token = normalizedTokens[index];
  const raw = words[index]?.word?.trim() ?? '';
  const prevRaw = words[index - 1]?.word?.trim() ?? '';
  const prevPrevRaw = words[index - 2]?.word?.trim() ?? '';
  const commaNeighbor = [prevPrevRaw, prevRaw, raw].some((value) => value.endsWith(','));
  const sentenceOpener = index === 0 || /[.!?]$/.test(prevRaw);
  const sandwichedPause =
    pauseBeforeMs(words, index) >= PAUSE_FILLER_THRESHOLD_MS &&
    pauseAfterMs(words, index) >= PAUSE_FILLER_THRESHOLD_MS;
  const openerPause = sentenceOpener && pauseAfterMs(words, index) >= PAUSE_FILLER_THRESHOLD_MS;

  if (token === 'like') {
    return commaNeighbor || sandwichedPause;
  }
  if (token === 'actually' || token === 'basically' || token === 'literally') {
    return commaNeighbor || openerPause;
  }
  if (token === 'so') {
    return sentenceOpener && (commaNeighbor || openerPause || sandwichedPause);
  }
  return false;
}

function isFillerToken(words: TranscriptWord[], normalizedTokens: string[], index: number) {
  const token = normalizedTokens[index];
  if (STRICT_FILLER_WORDS.has(token)) {
    return true;
  }
  if (CONTEXTUAL_FILLER_WORDS.has(token)) {
    return looksLikeContextualFiller(words, normalizedTokens, index);
  }
  return false;
}

function getTip(category: ChipCategory, word: string, count: number): string {
  switch (category) {
    case 'filler':
      return `This use of "${word}" reads as filler-like — used ${count} time${count !== 1 ? 's' : ''} in this session. Try replacing it with a brief pause to sound more confident.`;
    case 'repeated':
      return `"${word}" appeared ${count} times in this session. Consider varying your vocabulary for a more polished delivery.`;
    case 'strong':
      return `"${word}" is a strong, confident word choice. Great job using intentional language.`;
    default:
      return '';
  }
}

const CHIP_STYLES: Record<ChipCategory, string> = {
  filler:
    'bg-amber-50 text-amber-800 border-amber-200 hover:bg-amber-100 cursor-pointer shadow-sm',
  repeated:
    'bg-rose-50 text-rose-800 border-rose-200 hover:bg-rose-100 cursor-pointer shadow-sm',
  strong:
    'bg-emerald-50 text-emerald-800 border-emerald-200 hover:bg-emerald-100 cursor-pointer shadow-sm',
  plain:
    'bg-cream-50 text-slate-500 border-cream-200',
};

export function WordAudit({ transcriptWords, fillerWordsFound }: WordAuditProps) {
  const [selectedChipIndex, setSelectedChipIndex] = useState<number | null>(null);

  const chips = useMemo(() => {
    if (!transcriptWords.length) {
      return [];
    }

    const normalizedTokens = transcriptWords.map((tw) => normalize(tw.word));

    // Total frequency of every word (for display counts on all chip types)
    const totalWordFreq = new Map<string, number>();
    for (const token of normalizedTokens) {
      if (!token) continue;
      totalWordFreq.set(token, (totalWordFreq.get(token) ?? 0) + 1);
    }

    // Count word frequencies for repeated detection (skip common stopwords and fillers)
    const STOPWORDS = new Set([
      'a', 'an', 'and', 'are', 'as', 'at', 'be', 'but', 'by', 'for', 'from',
      'has', 'he', 'i', 'if', 'in', 'is', 'it', 'its', 'me', 'my', 'of', 'on',
      'or', 'our', 'she', 'so', 'that', 'the', 'their', 'them', 'they', 'this',
      'to', 'was', 'we', 'were', 'with', 'you', 'your',
    ]);

    // Count individual word freq (excluding stopwords, fillers — used only for repeat detection)
    const wordFreq = new Map<string, number>();
    for (const token of normalizedTokens) {
      if (!token || STOPWORDS.has(token) || STRICT_FILLER_WORDS.has(token)) {
        continue;
      }
      wordFreq.set(token, (wordFreq.get(token) ?? 0) + 1);
    }

    // Count phrase frequencies (2-3 word sliding window)
    const phraseFreq = new Map<string, number>();
    for (let size = 2; size <= 3; size++) {
      for (let i = 0; i <= normalizedTokens.length - size; i++) {
        const phraseTokens = normalizedTokens.slice(i, i + size);
        if (phraseTokens.some((t) => STOPWORDS.has(t) || !t)) {
          continue;
        }
        const phrase = phraseTokens.join(' ');
        phraseFreq.set(phrase, (phraseFreq.get(phrase) ?? 0) + 1);
      }
    }

    // Build repeated phrase set (phrases appearing 3+ times)
    const repeatedPhrases = new Set<string>();
    for (const [phrase, count] of phraseFreq) {
      if (count >= 3) {
        repeatedPhrases.add(phrase);
      }
    }

    // Build multi-word filler index — mark which token indices are part of multi-word fillers
    const fillerMultiIndices = new Set<number>();
    for (const filler of FILLER_PHRASES) {
      const fillerTokens = filler.split(' ');
      for (let i = 0; i <= normalizedTokens.length - fillerTokens.length; i++) {
        if (normalizedTokens.slice(i, i + fillerTokens.length).join(' ') === filler) {
          for (let j = 0; j < fillerTokens.length; j++) {
            fillerMultiIndices.add(i + j);
          }
        }
      }
    }

    // Build chips — only highlight first occurrence of each repeated word
    const result: AuditChip[] = [];
    const seenRepeated = new Set<string>();
    for (let i = 0; i < transcriptWords.length; i++) {
      const tw = transcriptWords[i];
      const norm = normalizedTokens[i];

      // Skip empty or whitespace-only tokens
      if (!tw.word.trim()) {
        continue;
      }

      let category: ChipCategory = 'plain';

      // Check filler (single-word or part of multi-word)
      if (isFillerToken(transcriptWords, normalizedTokens, i) || fillerMultiIndices.has(i)) {
        category = 'filler';
      }
      // Check strong words
      else if (STRONG_WORDS.has(norm)) {
        category = 'strong';
      }
      // Check repeated (word freq >= 3, excluding stopwords) — first occurrence only
      else if ((wordFreq.get(norm) ?? 0) >= 3 && !STOPWORDS.has(norm) && norm) {
        if (!seenRepeated.has(norm)) {
          category = 'repeated';
          seenRepeated.add(norm);
        }
      }
      // Check if this word starts a repeated phrase — first occurrence only
      else {
        for (let size = 2; size <= 3; size++) {
          if (i + size <= normalizedTokens.length) {
            const phraseStr = normalizedTokens.slice(i, i + size).join(' ');
            if (repeatedPhrases.has(phraseStr) && !seenRepeated.has(phraseStr)) {
              category = 'repeated';
              seenRepeated.add(phraseStr);
              break;
            }
          }
        }
      }

      result.push({
        word: tw.word,
        normalized: norm,
        category,
        count: totalWordFreq.get(norm) ?? 1,
        timestampMs: tw.start_ms,
        endMs: tw.end_ms,
        index: i,
      });
    }

    return result;
  }, [transcriptWords]);

  const selectedChip = selectedChipIndex !== null ? chips.find((c) => c.index === selectedChipIndex) ?? null : null;
  const hasColoredChips = chips.some((c) => c.category !== 'plain');

  if (!chips.length) {
    return (
      <div className="rounded-2xl border border-cream-300 bg-cream-50 p-6 shadow-sm">
        <div className="flex items-center gap-2 text-slate-700">
          <BookOpenText size={16} className="text-navy-500" />
          <p className="text-xs uppercase tracking-widest text-slate-400">Word Audit</p>
        </div>
        <p className="mt-4 text-sm leading-6 text-slate-500">
          No transcript data is available for word-level analysis.
        </p>
      </div>
    );
  }

  const fillerCount = chips.filter((c) => c.category === 'filler').length;
  const repeatedCount = chips.filter((c) => c.category === 'repeated').length;
  const strongCount = chips.filter((c) => c.category === 'strong').length;

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
            <BookOpenText size={16} className="text-navy-500" />
            <p className="text-xs uppercase tracking-widest text-slate-400">Word Audit</p>
          </div>
          <h3 className="mt-2 font-serif text-2xl font-semibold text-slate-900">
            Color-coded transcript
          </h3>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {fillerCount > 0 && (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-50 px-3 py-1.5 text-xs font-medium text-amber-700">
              <span className="h-2 w-2 rounded-full bg-amber-400" />
              {fillerCount} filler{fillerCount !== 1 ? 's' : ''}
            </span>
          )}
          {repeatedCount > 0 && (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-rose-50 px-3 py-1.5 text-xs font-medium text-rose-700">
              <span className="h-2 w-2 rounded-full bg-rose-400" />
              {repeatedCount} repeated
            </span>
          )}
          {strongCount > 0 && (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-3 py-1.5 text-xs font-medium text-emerald-700">
              <span className="h-2 w-2 rounded-full bg-emerald-500" />
              {strongCount} strong
            </span>
          )}
        </div>
      </div>

      <div className="mt-5 flex flex-wrap gap-1.5">
        {chips.map((chip) => {
          const isColored = chip.category !== 'plain';
          const isSelected = selectedChipIndex === chip.index;

          return (
            <button
              key={chip.index}
              type="button"
              onClick={() => {
                if (!isColored) return;
                setSelectedChipIndex(isSelected ? null : chip.index);
              }}
              className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-medium transition-all duration-150 ${
                CHIP_STYLES[chip.category]
              } ${isSelected ? 'ring-2 ring-navy-500/30 ring-offset-1' : ''}`}
            >
              {chip.word}
            </button>
          );
        })}
      </div>

      <AnimatePresence>
        {selectedChip && selectedChip.category !== 'plain' && (
          <motion.div
            key={selectedChip.index}
            initial={{ opacity: 0, height: 0, marginTop: 0 }}
            animate={{ opacity: 1, height: 'auto', marginTop: 20 }}
            exit={{ opacity: 0, height: 0, marginTop: 0 }}
            transition={{ duration: 0.22 }}
            className="overflow-hidden"
          >
            <div className={`rounded-xl border p-5 ${
              selectedChip.category === 'filler'
                ? 'border-amber-200 bg-amber-50/50'
                : selectedChip.category === 'repeated'
                  ? 'border-rose-200 bg-rose-50/50'
                  : 'border-emerald-200 bg-emerald-50/50'
            }`}>
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-3">
                  <span className={`inline-flex h-8 w-8 items-center justify-center rounded-full text-xs font-bold text-white ${
                    selectedChip.category === 'filler'
                      ? 'bg-amber-400'
                      : selectedChip.category === 'repeated'
                        ? 'bg-rose-400'
                        : 'bg-emerald-500'
                  }`}>
                    {selectedChip.word[0]?.toUpperCase()}
                  </span>
                  <div>
                    <p className="text-sm font-semibold text-slate-900">
                      &ldquo;{selectedChip.word}&rdquo;
                    </p>
                    <p className="mt-0.5 text-xs text-slate-500">
                      Used {selectedChip.count} time{selectedChip.count !== 1 ? 's' : ''} · at {formatTimestamp(selectedChip.timestampMs)}
                    </p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setSelectedChipIndex(null)}
                  className="rounded-full p-1.5 text-slate-400 transition-colors hover:bg-white hover:text-slate-700"
                >
                  <X size={14} />
                </button>
              </div>
              <p className="mt-3 text-sm leading-6 text-slate-600">
                {getTip(selectedChip.category, selectedChip.word, selectedChip.count)}
              </p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {!hasColoredChips && (
        <div className="mt-5 rounded-xl bg-emerald-50 px-4 py-4 text-sm text-emerald-800">
          Your transcript is clean — no filler words, repetition, or notable patterns were flagged.
        </div>
      )}

      {/* Legend */}
      <div className="mt-5 flex flex-wrap items-center gap-4 border-t border-cream-200 pt-4">
        <span className="inline-flex items-center gap-1.5 text-xs text-slate-500">
          <span className="h-2.5 w-2.5 rounded-full bg-amber-400" />
          Filler words
        </span>
        <span className="inline-flex items-center gap-1.5 text-xs text-slate-500">
          <span className="h-2.5 w-2.5 rounded-full bg-rose-400" />
          Repeated 3+ times
        </span>
        <span className="inline-flex items-center gap-1.5 text-xs text-slate-500">
          <span className="h-2.5 w-2.5 rounded-full bg-emerald-500" />
          Strong, confident words
        </span>
        <span className="inline-flex items-center gap-1.5 text-xs text-slate-500">
          <span className="h-2.5 w-2.5 rounded-full bg-cream-300" />
          Neutral
        </span>
      </div>
    </motion.div>
  );
}
