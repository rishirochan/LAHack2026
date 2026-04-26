'use client';

import { startTransition, useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Loader2, Mic, RefreshCw, Square, Volume2 } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import {
  emotionOptions,
  type DisplayMetric,
  type PhaseADerivedMetrics,
  type SessionSetup,
  type SessionSummary,
  usePhaseASession,
} from '@/hooks/usePhaseASession';
import { Switch } from '@/components/ui/switch';

const MAX_RECORDING_SECONDS = 20;
const MIN_RECORDING_SECONDS = 2;
const FAST_CAPTURE_MODE = 'fast';
const POWERFUL_CAPTURE_MODE = 'powerful';
const processingStages = [
  'Uploading recording',
  'Analyzing facial and vocal emotion',
  'Transcribing speech',
  'Generating critique',
  'Preparing playback',
];

const defaultSetup: SessionSetup = {
  targetEmotion: null,
};

type CaptureMode = typeof FAST_CAPTURE_MODE | typeof POWERFUL_CAPTURE_MODE;

export default function SprintPage() {
  const [setup, setSetup] = useState<SessionSetup>(defaultSetup);
  const [captureMode, setCaptureMode] = useState<CaptureMode>(FAST_CAPTURE_MODE);
  const [isPreparingPreview, setIsPreparingPreview] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [hasPreviewStream, setHasPreviewStream] = useState(false);
  const [secondsRemaining, setSecondsRemaining] = useState(MAX_RECORDING_SECONDS);
  const [localError, setLocalError] = useState('');
  const previewRef = useRef<HTMLVideoElement | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const videoRecorderRef = useRef<MediaRecorder | null>(null);
  const wavAudioRecorderRef = useRef<WavAudioRecorder | null>(null);
  const videoChunksRef = useRef<Blob[]>([]);
  const startedAtRef = useRef<number>(0);
  const timerRef = useRef<number | null>(null);
  const {
    status,
    scenarioPrompt,
    critique,
    processingStage,
    roundResult,
    summary,
    errorMessage,
    isScenarioAudioPlaying,
    isCritiqueAudioPlaying,
    isEnding,
    startSession,
    uploadRecording,
    chooseContinue,
    toggleScenarioTextToSpeech,
    toggleCritiqueTextToSpeech,
    resetAll,
  } = usePhaseASession();

  async function handleStart() {
    if (!setup.targetEmotion) {
      setLocalError('Choose an emotion before generating a prompt.');
      return;
    }

    setLocalError('');
    try {
      await startSession(setup);
    } catch {
      setLocalError('Failed to start the drill. Confirm the backend is running and try again.');
    }
  }

  async function handleRegenerate() {
    if (!setup.targetEmotion) {
      setLocalError('Choose an emotion before generating a prompt.');
      return;
    }

    setLocalError('');
    try {
      await startSession(setup);
    } catch {
      setLocalError('Could not regenerate the prompt right now.');
    }
  }

  async function toggleRecording() {
    if (isRecording) {
      await stopRecording();
      return;
    }
    await startRecording();
  }

  async function requestCaptureStream(mode: CaptureMode) {
    return navigator.mediaDevices.getUserMedia(buildCaptureConstraints(mode));
  }

  function attachPreviewStream(stream: MediaStream) {
    mediaStreamRef.current = stream;
    if (previewRef.current) {
      previewRef.current.srcObject = stream;
    }
    setHasPreviewStream(true);
  }

  async function startRecording() {
    try {
      setLocalError('');
      const stream = mediaStreamRef.current ?? (await requestCaptureStream(captureMode));
      attachPreviewStream(stream);

      videoChunksRef.current = [];
      const videoRecorder = new MediaRecorder(stream, {
        mimeType: getSupportedMimeType(['video/webm;codecs=vp8,opus', 'video/webm']),
      });
      const wavAudioRecorder = createWavAudioRecorder(stream);

      videoRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          videoChunksRef.current.push(event.data);
        }
      };

      videoRecorderRef.current = videoRecorder;
      wavAudioRecorderRef.current = wavAudioRecorder;
      startedAtRef.current = window.performance.now();
      setSecondsRemaining(MAX_RECORDING_SECONDS);
      setIsRecording(true);
      videoRecorder.start();
      wavAudioRecorder.start();
      startCountdown();
    } catch {
      setLocalError('Camera or microphone access was blocked. Allow access and try again.');
    }
  }

  async function stopRecording() {
    stopTimer();
    setIsRecording(false);
    const durationSeconds = (window.performance.now() - startedAtRef.current) / 1000;

    if (durationSeconds < MIN_RECORDING_SECONDS) {
      stopRecordersWithoutUpload(videoRecorderRef.current, wavAudioRecorderRef.current);
      stopTracks();
      setLocalError('That recording was too short. Try again with a full response.');
      return;
    }

    const [videoBlob, audioBlob] = await Promise.all([
      stopRecorder(videoRecorderRef.current, videoChunksRef.current, 'video/webm'),
      stopWavAudioRecorder(wavAudioRecorderRef.current),
    ]);
    wavAudioRecorderRef.current = null;
    stopTracks();
    try {
      await uploadRecording(videoBlob, audioBlob, durationSeconds);
    } catch {
      setLocalError('Could not upload the recording. Please try again.');
    }
  }

  function startCountdown() {
    stopTimer();
    timerRef.current = window.setInterval(() => {
      const elapsed = Math.floor((window.performance.now() - startedAtRef.current) / 1000);
      const remaining = Math.max(MAX_RECORDING_SECONDS - elapsed, 0);
      setSecondsRemaining(remaining);
      if (remaining === 0) {
        void stopRecording();
      }
    }, 250);
  }

  function stopTimer() {
    if (timerRef.current) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }

  function stopTracks() {
    mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
    mediaStreamRef.current = null;
    if (previewRef.current) {
      previewRef.current.srcObject = null;
    }
    setHasPreviewStream(false);
  }

  function handleResetAll() {
    stopTracks();
    setCaptureMode(FAST_CAPTURE_MODE);
    resetAll();
  }

  useEffect(() => {
    return () => {
      stopTimer();
      wavAudioRecorderRef.current?.discard();
      stopTracks();
    };
  }, []);

  useEffect(() => {
    if (status !== 'recording' || isRecording) {
      startTransition(() => {
        setIsPreparingPreview(false);
      });
      return;
    }

    let isCancelled = false;

    async function syncPreviewStream() {
      try {
        setLocalError('');
        setIsPreparingPreview(true);
        stopTracks();
        const stream = await requestCaptureStream(captureMode);
        if (isCancelled) {
          stream.getTracks().forEach((track) => track.stop());
          return;
        }
        attachPreviewStream(stream);
        setIsPreparingPreview(false);
      } catch {
        if (isCancelled) {
          return;
        }
        stopTracks();
        setIsPreparingPreview(false);
        setLocalError('Camera or microphone access was blocked. Allow access and try again.');
      }
    }

    void syncPreviewStream();

    return () => {
      isCancelled = true;
    };
  }, [captureMode, isRecording, status]);

  const canRecord = (status === 'recording' || isRecording) && !isPreparingPreview;
  const shownError = localError || errorMessage;
  const isPowerfulMode = captureMode === POWERFUL_CAPTURE_MODE;
  const captureModeDescription = isPowerfulMode
    ? 'Powerful: slower analysis, maximum webcam quality'
    : 'Fast: quicker analysis, lower webcam quality';

  if (status === 'setup') {
    return (
      <div className="mx-auto max-w-2xl py-8">
        {/* Page header */}
        <div className="mb-12 text-center">
          <p className="mb-5 text-xs font-semibold uppercase tracking-[0.18em] text-navy-500">
            Emotion Sprint
          </p>
          <h1 className="font-serif text-[3rem] font-semibold leading-[1.1] text-slate-900 sm:text-[3.5rem]">
            Choose your intent.
          </h1>
          <p className="mx-auto mt-5 max-w-md text-base leading-relaxed text-slate-500">
            Pick one. We'll generate a 2-sentence scenario. You have 20 seconds to deliver it in that tone.
          </p>
        </div>

        {/* Emotion grid */}
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {emotionOptions.map((emotion) => {
            const isSelected = setup.targetEmotion === emotion;
            const displayName = emotion.replace(' (Neutral)', '');
            return (
              <button
                key={emotion}
                onClick={() => setSetup((current) => ({ ...current, targetEmotion: emotion }))}
                className={`relative rounded-xl px-4 py-5 text-left transition-all duration-150 ${
                  isSelected
                    ? 'bg-navy-500 text-white shadow-lg'
                    : 'bg-cream-200 text-slate-700 hover:bg-cream-300 hover:shadow-sm'
                }`}
              >
                {isSelected && (
                  <span className="absolute right-3 top-3 flex h-4 w-4 items-center justify-center rounded-full bg-white/20">
                    <svg width="8" height="6" viewBox="0 0 8 6" fill="none">
                      <path d="M1 3l2 2 4-4" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  </span>
                )}
                <span className={`block text-sm font-semibold leading-tight ${isSelected ? 'text-white' : 'text-slate-900'}`}>
                  {displayName}
                </span>
              </button>
            );
          })}
        </div>

        {/* CTA area */}
        <div className="mt-10">
          <AnimatePresence mode="wait">
            {setup.targetEmotion ? (
              <motion.div
                key="selected"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 6 }}
                transition={{ duration: 0.22, ease: [0.25, 1, 0.5, 1] }}
              >
                <div className="mb-6 flex items-center gap-3">
                  <div className="h-px flex-1 bg-cream-300" />
                  <p className="text-[0.6875rem] font-semibold uppercase tracking-[0.12em] text-slate-400">
                    Practicing
                  </p>
                  <div className="h-px flex-1 bg-cream-300" />
                </div>
                <p className="mb-6 text-center font-serif text-2xl font-semibold text-slate-900">
                  {setup.targetEmotion.replace(' (Neutral)', '')}
                </p>
                <button
                  onClick={handleStart}
                  className="w-full rounded-xl bg-navy-500 py-4 text-sm font-semibold text-white shadow-md transition-all hover:bg-navy-600 active:scale-[0.99]"
                >
                  Generate prompt →
                </button>
              </motion.div>
            ) : (
              <motion.p
                key="hint"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.2 }}
                className="text-center text-sm text-slate-400"
              >
                Select an emotion above to continue.
              </motion.p>
            )}
          </AnimatePresence>

          {shownError && (
            <p className="mt-4 text-sm text-red-600">{shownError}</p>
          )}
        </div>
      </div>
    );
  }

  if (status === 'summary' && summary) {
    return <SummaryView summary={summary} onReset={handleResetAll} />;
  }

  if (status === 'error') {
    return (
      <div className="mx-auto max-w-2xl rounded-2xl border border-red-200 bg-white p-8 text-center shadow-sm">
        <h1 className="font-serif text-2xl font-semibold text-slate-900">
          Something went wrong
        </h1>
        <p className="mt-3 text-sm text-slate-600">{shownError || 'Try starting the drill again.'}</p>
        <button
          onClick={handleResetAll}
          className="mt-6 rounded-full bg-navy-500 px-6 py-3 text-sm font-semibold text-white shadow-sm transition-all hover:bg-navy-600"
        >
          Restart
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Emotion Prompt */}
      <section className="rounded-2xl border border-cream-300 bg-cream-100 px-6 py-5">
        <p className="mb-3 text-xs font-semibold uppercase tracking-[0.12em] text-navy-500">Emotion Prompt</p>
        <p className="min-h-[3.5rem] text-[1.375rem] font-semibold leading-snug text-slate-900">
          {scenarioPrompt || 'Generating your scenario…'}
        </p>
        <div className="mt-4 flex items-center gap-1">
          <button
            type="button"
            onClick={() => { void toggleScenarioTextToSpeech(); }}
            disabled={!scenarioPrompt}
            className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${
              isScenarioAudioPlaying
                ? 'bg-navy-500 text-white'
                : 'text-slate-500 hover:bg-cream-200 hover:text-slate-800'
            }`}
          >
            {isScenarioAudioPlaying ? <Square size={13} /> : <Volume2 size={13} />}
            {isScenarioAudioPlaying ? 'Stop' : 'Listen'}
          </button>
          <button
            onClick={handleRegenerate}
            disabled={status === 'processing'}
            className="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm text-slate-500 transition-colors hover:bg-cream-200 hover:text-slate-800 disabled:cursor-not-allowed disabled:opacity-40"
          >
            <RefreshCw size={13} /> Regenerate
          </button>
        </div>
      </section>

      {/* Critique view */}
      {(status === 'critique' || roundResult) && (
        <section className="grid gap-4 lg:grid-cols-[1fr_280px]">
          <div className="rounded-2xl border border-cream-200 bg-white p-6">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <p className="text-xs font-semibold uppercase tracking-[0.12em] text-navy-500">Coach Critique</p>
              <button
                type="button"
                onClick={() => { void toggleCritiqueTextToSpeech(); }}
                disabled={!critique}
                className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${
                  isCritiqueAudioPlaying
                    ? 'bg-navy-500 text-white'
                    : 'text-slate-500 hover:bg-cream-100 hover:text-slate-800'
                }`}
              >
                {isCritiqueAudioPlaying ? <Square size={13} /> : <Volume2 size={13} />}
                {isCritiqueAudioPlaying ? 'Stop' : 'Listen'}
              </button>
            </div>
            <MarkdownCritique content={critique} />
            <div className="mt-6 flex flex-wrap gap-3">
              <button
                onClick={() => {
                  void chooseContinue(true).catch((error: unknown) => {
                    setLocalError(error instanceof Error ? error.message : 'Could not send session decision.');
                  });
                }}
                disabled={isEnding}
                className="rounded-xl bg-navy-500 px-5 py-3 text-sm font-semibold text-white shadow-sm transition-all hover:bg-navy-600"
              >
                {isEnding ? 'Finishing…' : 'Next exercise'}
              </button>
              <button
                onClick={() => {
                  void chooseContinue(false).catch((error: unknown) => {
                    setLocalError(error instanceof Error ? error.message : 'Could not send session decision.');
                  });
                }}
                disabled={isEnding}
                className="rounded-xl border border-cream-300 px-5 py-3 text-sm font-medium text-slate-700 transition-all hover:bg-cream-100"
              >
                {isEnding ? 'Finishing…' : 'End session'}
              </button>
            </div>
          </div>

          <MeasuredSignalsCard
            score={roundResult?.derived_metrics?.overall_match_score ?? roundResult?.match_score ?? 0}
            displayMetrics={roundResult?.display_metrics ?? []}
            derivedMetrics={roundResult?.derived_metrics}
            fillerWordCount={roundResult?.filler_word_count ?? 0}
            fillerWordBreakdown={roundResult?.filler_word_breakdown ?? {}}
          />
        </section>
      )}

      {/* Recording view */}
      {!(status === 'critique' || roundResult) && (
        <section className={`grid gap-4 ${status === 'processing' ? '' : 'lg:grid-cols-[1fr_280px]'}`}>
          {/* Recording controls */}
          <div className="flex min-h-[300px] flex-col items-center justify-center rounded-2xl border border-cream-200 bg-white p-8">
            {status === 'processing' ? (
              <ProcessingStages activeStage={processingStage} />
            ) : (
              <div className="flex flex-col items-center gap-5">
                {/* Mic button */}
                <div className="relative">
                  {isRecording && (
                    <span className="absolute inset-0 animate-ping rounded-full bg-red-400/25" />
                  )}
                  <button
                    type="button"
                    disabled={!canRecord}
                    onClick={toggleRecording}
                    className={`relative flex h-28 w-28 items-center justify-center rounded-full shadow-md transition-all duration-200 active:scale-95 ${
                      isRecording
                        ? 'bg-red-500 text-white shadow-red-200'
                        : 'bg-navy-500 text-white hover:bg-navy-600 shadow-navy-200/60 disabled:bg-slate-200 disabled:shadow-none disabled:text-slate-400'
                    }`}
                  >
                    {isRecording ? <Square className="h-9 w-9" /> : <Mic className="h-10 w-10" />}
                  </button>
                </div>

                {/* State label + timer */}
                <div className="text-center">
                  <p className="text-sm font-semibold text-slate-900">
                    {isRecording ? 'Recording' : isPreparingPreview ? 'Preparing camera' : 'Click to record'}
                  </p>
                  <p className={`mt-1 text-sm tabular-nums ${isRecording && secondsRemaining <= 5 ? 'font-semibold text-red-500' : 'text-slate-400'}`}>
                    {isRecording
                      ? `${secondsRemaining}s remaining`
                      : isPreparingPreview
                        ? 'Loading camera…'
                        : '20 second limit'}
                  </p>
                </div>

                {shownError && (
                  <p className="rounded-xl bg-red-50 px-4 py-2.5 text-sm text-red-600">{shownError}</p>
                )}
              </div>
            )}
          </div>

          {/* Webcam panel */}
          {status !== 'processing' && (
            <div className="flex flex-col gap-3 rounded-2xl border border-cream-200 bg-white p-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.08em] text-slate-400">Analysis mode</p>
                  <p className="mt-0.5 text-sm font-semibold text-slate-900">{isPowerfulMode ? 'Powerful' : 'Fast'}</p>
                </div>
                <Switch
                  checked={isPowerfulMode}
                  onCheckedChange={(checked) => setCaptureMode(checked ? POWERFUL_CAPTURE_MODE : FAST_CAPTURE_MODE)}
                  disabled={isRecording || isPreparingPreview}
                  aria-label={`Analysis mode: ${isPowerfulMode ? 'Powerful' : 'Fast'}`}
                />
              </div>
              <video
                ref={previewRef}
                autoPlay
                muted
                playsInline
                className="aspect-[4/3] w-full rounded-xl bg-cream-200 object-cover"
              />
              {!hasPreviewStream && (
                <p className="text-center text-xs text-slate-400">
                  {isPreparingPreview ? 'Preparing camera…' : 'Camera preview appears here.'}
                </p>
              )}
            </div>
          )}
        </section>
      )}
    </div>
  );
}

function SummaryView({ summary, onReset }: { summary: SessionSummary; onReset: () => void }) {
  const [activeIndex, setActiveIndex] = useState(0);

  const critiques = summary.critiques ?? [];
  const matchScores = summary.match_scores ?? [];
  const fillerEntries = Object.entries(summary.filler_words ?? {}).sort((a, b) => b[1] - a[1]);
  const matchScoreData = matchScores.map((score, i) => ({
    round: `R${i + 1}`,
    score: Math.round(score * 100),
  }));
  const roundCount = critiques.length;
  const activePct = Math.round((matchScores[activeIndex] ?? 0) * 100);

  function scorePillClass(pct: number) {
    return pct >= 70
      ? 'bg-emerald-50 text-emerald-700'
      : pct >= 40
        ? 'bg-amber-50 text-amber-700'
        : 'bg-rose-50 text-rose-700';
  }

  function scoreTextClass(pct: number) {
    return pct >= 70 ? 'text-emerald-600' : pct >= 40 ? 'text-amber-600' : 'text-rose-500';
  }

  return (
    <div className="mx-auto max-w-5xl space-y-10">
      {/* Header */}
      <div>
        <p className="text-xs font-semibold uppercase tracking-widest text-navy-500">Emotion Sprint</p>
        <h1 className="mt-2 font-serif text-3xl font-semibold leading-tight text-slate-900">
          Session Summary
        </h1>
        <p className="mt-1.5 text-sm text-slate-500">
          {roundCount} round{roundCount !== 1 ? 's' : ''} completed
        </p>
      </div>

      {/* Critique carousel */}
      <section className="space-y-3">
        <p className="text-xs font-semibold uppercase tracking-widest text-slate-400">Round Critiques</p>

        {/* Tab strip — spans full width, equal columns */}
        {roundCount > 0 && (
          <div
            className="grid overflow-hidden rounded-xl border border-cream-300 bg-cream-300"
            style={{ gridTemplateColumns: `repeat(${roundCount}, 1fr)`, gap: '1px' }}
          >
            {critiques.map((_, i) => {
              const pct = Math.round((matchScores[i] ?? 0) * 100);
              const isActive = i === activeIndex;
              return (
                <button
                  key={i}
                  type="button"
                  onClick={() => setActiveIndex(i)}
                  className={`flex flex-col items-center gap-0.5 py-3.5 px-3 text-center transition-colors duration-150 ${
                    isActive ? 'bg-navy-500' : 'bg-cream-50 hover:bg-cream-200'
                  }`}
                >
                  <span
                    className={`text-[10px] font-semibold uppercase tracking-widest ${
                      isActive ? 'text-white/60' : 'text-slate-400'
                    }`}
                  >
                    Round {i + 1}
                  </span>
                  <span
                    className={`text-base font-bold tabular-nums ${
                      isActive ? 'text-white' : scoreTextClass(pct)
                    }`}
                  >
                    {pct}%
                  </span>
                </button>
              );
            })}
          </div>
        )}

        {/* Active critique panel */}
        <div className="min-h-[180px] rounded-2xl border border-cream-300 bg-cream-50 p-6">
          <AnimatePresence mode="wait">
            <motion.div
              key={activeIndex}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.18, ease: [0.25, 1, 0.5, 1] }}
            >
              <div className="mb-4 flex items-center justify-between gap-3">
                <span className="text-xs font-semibold uppercase tracking-widest text-slate-400">
                  Round {activeIndex + 1}
                </span>
                <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${scorePillClass(activePct)}`}>
                  {activePct}% match
                </span>
              </div>
              <MarkdownCritique content={critiques[activeIndex] ?? ''} compact />
            </motion.div>
          </AnimatePresence>
        </div>

        {/* Dot navigation */}
        {roundCount > 1 && (
          <div className="flex items-center justify-center gap-2 pt-1">
            {critiques.map((_, i) => (
              <button
                key={i}
                type="button"
                onClick={() => setActiveIndex(i)}
                aria-label={`Round ${i + 1}`}
                className={`rounded-full transition-all duration-200 ${
                  i === activeIndex
                    ? 'h-2.5 w-2.5 bg-navy-500'
                    : 'h-2 w-2 bg-cream-300 hover:bg-slate-300'
                }`}
              />
            ))}
          </div>
        )}
      </section>

      {/* Data row — bottom */}
      <div className="grid gap-6 md:grid-cols-2">
        <section className="rounded-2xl border border-cream-300 bg-cream-50 p-6">
          <p className="mb-1 text-xs font-semibold uppercase tracking-widest text-slate-400">Match Score Trend</p>
          <p className="mb-5 font-serif text-xl font-semibold text-slate-900">Round by round</p>
          <div className="h-48">
            {matchScoreData.length ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={matchScoreData} margin={{ top: 8, right: 4, bottom: 0, left: -12 }}>
                  <CartesianGrid vertical={false} stroke="#EDE3CC" />
                  <XAxis
                    dataKey="round"
                    tick={{ fill: '#94a3b8', fontSize: 11 }}
                    tickLine={false}
                    axisLine={false}
                  />
                  <YAxis
                    domain={[0, 100]}
                    tick={{ fill: '#94a3b8', fontSize: 11 }}
                    tickLine={false}
                    axisLine={false}
                    width={32}
                  />
                  <Tooltip
                    cursor={{ fill: 'rgba(36, 55, 99, 0.06)' }}
                    formatter={(value) => [`${value}%`, 'Match']}
                  />
                  <Bar dataKey="score" radius={[6, 6, 0, 0]} fill="#243763" />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex h-full items-center justify-center text-sm text-slate-400">
                No rounds recorded.
              </div>
            )}
          </div>
        </section>

        <section className="rounded-2xl border border-cream-300 bg-cream-50 p-6">
          <p className="mb-1 text-xs font-semibold uppercase tracking-widest text-slate-400">Filler Words</p>
          <p className="mb-5 font-serif text-xl font-semibold text-slate-900">Session totals</p>
          {fillerEntries.length ? (
            <div className="flex flex-wrap gap-2">
              {fillerEntries.map(([word, count]) => (
                <div key={word} className="flex items-center gap-2 rounded-xl bg-cream-200 px-3.5 py-2.5">
                  <span className="text-sm font-semibold text-slate-700">{word}</span>
                  <span className="rounded-full bg-cream-50 px-2 py-0.5 text-xs font-semibold text-slate-500">
                    {count}×
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-xl bg-emerald-50 px-4 py-4">
              <p className="text-sm text-emerald-800">No filler words detected across all rounds.</p>
            </div>
          )}
        </section>
      </div>

      <button
        onClick={onReset}
        className="rounded-lg bg-navy-500 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-navy-600"
      >
        New session
      </button>
    </div>
  );
}

function MarkdownCritique({ content, compact = false }: { content: string; compact?: boolean }) {
  const prose = compact
    ? 'mb-2 text-sm leading-6 text-slate-700 last:mb-0'
    : 'mb-3 text-lg leading-relaxed text-slate-700 last:mb-0';
  const list = compact
    ? 'mb-2 list-disc space-y-1 pl-4 text-sm leading-6 text-slate-700'
    : 'mb-3 list-disc space-y-2 pl-5 text-lg leading-relaxed text-slate-700';

  return (
    <ReactMarkdown
      components={{
        h1: ({ children }) => <h1 className={`mb-2 font-semibold leading-snug text-slate-900 ${compact ? 'text-base' : 'text-2xl'}`}>{children}</h1>,
        h2: ({ children }) => <h2 className={`mb-2 font-semibold leading-snug text-slate-900 ${compact ? 'text-sm' : 'text-xl'}`}>{children}</h2>,
        h3: ({ children }) => <h3 className={`mb-2 font-semibold leading-snug text-slate-900 ${compact ? 'text-sm' : 'text-lg'}`}>{children}</h3>,
        p: ({ children }) => <p className={prose}>{children}</p>,
        strong: ({ children }) => <strong className="font-semibold text-slate-900">{children}</strong>,
        em: ({ children }) => <em className="italic">{children}</em>,
        ul: ({ children }) => <ul className={list}>{children}</ul>,
        ol: ({ children }) => <ol className={`${list} list-decimal`}>{children}</ol>,
        li: ({ children }) => <li>{children}</li>,
        code: ({ children }) => (
          <code className={`rounded bg-cream-200 px-1.5 py-0.5 text-slate-800 ${compact ? 'text-xs' : 'text-base'}`}>{children}</code>
        ),
      }}
    >
      {content}
    </ReactMarkdown>
  );
}

function ProcessingStages({ activeStage }: { activeStage: string }) {
  const activeIndex = Math.max(processingStages.indexOf(activeStage), 0);

  return (
    <div className="w-full max-w-md">
      <div className="mb-6 flex items-center justify-center gap-3 text-navy-500">
        <Loader2 className="h-6 w-6 animate-spin" />
        <span className="text-sm font-semibold">{activeStage || 'Processing recording'}</span>
      </div>
      <div className="space-y-3">
        {processingStages.map((stage, index) => (
          <div
            key={stage}
            className={`flex items-center gap-3 rounded-2xl px-4 py-3 text-sm ${
              index <= activeIndex ? 'bg-navy-100 text-navy-700' : 'bg-cream-100 text-slate-400'
            }`}
          >
            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-white text-xs font-bold">
              {index + 1}
            </span>
            {stage}
          </div>
        ))}
      </div>
    </div>
  );
}

function MeasuredSignalsCard({
  score,
  displayMetrics,
  derivedMetrics,
  fillerWordCount,
  fillerWordBreakdown,
}: {
  score: number;
  displayMetrics: DisplayMetric[];
  derivedMetrics?: PhaseADerivedMetrics;
  fillerWordCount: number;
  fillerWordBreakdown: Record<string, number>;
}) {
  const mismatchMoments = derivedMetrics?.top_mismatch_moments ?? [];
  const fillerEntries = Object.entries(fillerWordBreakdown).sort((left, right) => right[1] - left[1]);
  const visibleMetrics = displayMetrics.filter((metric) => metric.key !== 'overall_match_score');

  return (
    <div className="space-y-4">
      <ScoreCard score={score} />
      <div className="rounded-2xl border border-cream-300 bg-white p-6 shadow-sm">
        <p className="mb-4 text-sm font-semibold uppercase tracking-widest text-navy-500">Measured Signals</p>
        <div className="space-y-3">
          {visibleMetrics.map((metric) => (
            <div key={metric.key} className="rounded-2xl bg-cream-100 p-4">
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm font-semibold text-slate-900">{metric.label}</p>
                <span className="text-sm font-semibold text-navy-600">{metric.display_value}</span>
              </div>
              <p className="mt-1 text-xs leading-relaxed text-slate-500">{metric.description}</p>
            </div>
          ))}
        </div>

        <div className="mt-5 rounded-2xl bg-cream-100 p-4">
          <div className="flex items-center justify-between gap-3">
            <p className="text-sm font-semibold text-slate-900">Filler words this round</p>
            <span className="text-sm font-semibold text-navy-600">{fillerWordCount}</span>
          </div>
          {fillerEntries.length ? (
            <div className="mt-3 flex flex-wrap gap-2">
              {fillerEntries.map(([word, count]) => (
                <span key={word} className="rounded-full bg-white px-3 py-1 text-xs font-medium text-slate-600">
                  {word} x{count}
                </span>
              ))}
            </div>
          ) : (
            <p className="mt-2 text-xs leading-relaxed text-slate-500">No filler words were detected in this response.</p>
          )}
        </div>

        {mismatchMoments.length > 0 && (
          <div className="mt-5 space-y-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-widest text-slate-400">Notable mismatches</p>
              <div className="mt-2 space-y-2">
                {mismatchMoments.map((moment, index) => (
                  <p key={`${moment.timestamp_ms}-${moment.word}-${index}`} className="text-sm text-slate-600">
                    {formatTimestamp(moment.timestamp_ms)} on "{moment.word}": face read {moment.face_emotion_type}, voice read{' '}
                    {moment.voice_emotion_type}
                  </p>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function ScoreCard({ score }: { score: number }) {
  const percentage = Math.round(score * 100);
  const accentClass =
    score > 0.6 ? 'text-emerald-600 stroke-emerald-500' : score >= 0.3 ? 'text-amber-500 stroke-amber-400' : 'text-red-500 stroke-red-400';
  const circumference = 2 * Math.PI * 42;
  const dashOffset = circumference * (1 - Math.min(Math.max(score, 0), 1));

  return (
    <div className="rounded-2xl border border-cream-300 bg-white p-6 shadow-sm">
      <p className="mb-4 text-sm font-semibold uppercase tracking-widest text-navy-500">Emotion Match</p>
      <div className="relative mx-auto h-28 w-28">
        <svg className="-rotate-90" viewBox="0 0 100 100">
          <circle cx="50" cy="50" r="42" fill="none" strokeWidth="10" className="stroke-cream-200" />
          <circle
            cx="50"
            cy="50"
            r="42"
            fill="none"
            strokeWidth="10"
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={dashOffset}
            className={accentClass}
          />
        </svg>
        <div className={`absolute inset-0 flex items-center justify-center text-2xl font-bold ${accentClass.split(' ')[0]}`}>
          {percentage}%
        </div>
      </div>
      <p className="mt-4 text-center text-sm text-slate-500">
        Based on the overall response trend, not just one peak emotion spike.
      </p>
    </div>
  );
}

function formatTimestamp(timestampMs: number) {
  return `${(timestampMs / 1000).toFixed(1)}s`;
}

function getSupportedMimeType(candidates: string[]) {
  return candidates.find((candidate) => MediaRecorder.isTypeSupported(candidate)) ?? '';
}

function buildCaptureConstraints(mode: CaptureMode): MediaStreamConstraints {
  if (mode === FAST_CAPTURE_MODE) {
    return {
      video: {
        width: { ideal: 4096 },
        height: { ideal: 2160 },
        frameRate: { ideal: 30 },
        facingMode: 'user',
      },
      audio: true,
    };
  }

  return {
    video: {
      width: { ideal: 640, max: 640 },
      height: { ideal: 480, max: 480 },
      frameRate: { ideal: 10, max: 10 },
      facingMode: 'user',
    },
    audio: true,
  };
}

function stopRecordersWithoutUpload(
  videoRecorder: MediaRecorder | null,
  audioRecorder: WavAudioRecorder | null,
) {
  if (videoRecorder?.state === 'recording') {
    videoRecorder.stop();
  }
  audioRecorder?.discard();
}

function stopRecorder(recorder: MediaRecorder | null, chunks: Blob[], fallbackType: string) {
  return new Promise<Blob>((resolve) => {
    if (!recorder) {
      resolve(new Blob([], { type: fallbackType }));
      return;
    }

    recorder.onstop = () => {
      resolve(new Blob(chunks, { type: recorder.mimeType || fallbackType }));
    };

    if (recorder.state === 'recording') {
      recorder.stop();
    } else {
      resolve(new Blob(chunks, { type: recorder.mimeType || fallbackType }));
    }
  });
}

type WavAudioRecorder = {
  start: () => void;
  stop: () => Promise<Blob>;
  discard: () => void;
};

function createWavAudioRecorder(stream: MediaStream): WavAudioRecorder {
  const AudioContextCtor =
    window.AudioContext ??
    (window as typeof window & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;

  if (!AudioContextCtor) {
    throw new Error('Audio recording is not supported in this browser.');
  }

  const audioContext = new AudioContextCtor();
  const audioStream = new MediaStream(stream.getAudioTracks());
  const source = audioContext.createMediaStreamSource(audioStream);
  const processor = audioContext.createScriptProcessor(4096, 1, 1);
  const chunks: Float32Array[] = [];
  let isCapturing = false;
  let isStopped = false;

  processor.onaudioprocess = (event) => {
    event.outputBuffer.getChannelData(0).fill(0);
    if (!isCapturing) {
      return;
    }
    chunks.push(new Float32Array(event.inputBuffer.getChannelData(0)));
  };

  return {
    start: () => {
      isCapturing = true;
      source.connect(processor);
      processor.connect(audioContext.destination);
      void audioContext.resume();
    },
    stop: async () => {
      if (isStopped) {
        return encodeWav(chunks, audioContext.sampleRate);
      }
      isStopped = true;
      isCapturing = false;
      disconnectAudioNodes(source, processor);
      await audioContext.close();
      return encodeWav(chunks, audioContext.sampleRate);
    },
    discard: () => {
      if (isStopped) {
        return;
      }
      isStopped = true;
      isCapturing = false;
      disconnectAudioNodes(source, processor);
      void audioContext.close();
    },
  };
}

async function stopWavAudioRecorder(recorder: WavAudioRecorder | null) {
  if (!recorder) {
    return new Blob([], { type: 'audio/wav' });
  }
  return recorder.stop();
}

function disconnectAudioNodes(source: MediaStreamAudioSourceNode, processor: ScriptProcessorNode) {
  try {
    source.disconnect();
  } catch {
    // The node may already be disconnected during cleanup.
  }
  try {
    processor.disconnect();
  } catch {
    // The node may already be disconnected during cleanup.
  }
}

function encodeWav(chunks: Float32Array[], sampleRate: number) {
  const samples = mergeAudioChunks(chunks);
  const bytesPerSample = 2;
  const wavHeaderBytes = 44;
  const dataBytes = samples.length * bytesPerSample;
  const buffer = new ArrayBuffer(wavHeaderBytes + dataBytes);
  const view = new DataView(buffer);

  writeAscii(view, 0, 'RIFF');
  view.setUint32(4, 36 + dataBytes, true);
  writeAscii(view, 8, 'WAVE');
  writeAscii(view, 12, 'fmt ');
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * bytesPerSample, true);
  view.setUint16(32, bytesPerSample, true);
  view.setUint16(34, 8 * bytesPerSample, true);
  writeAscii(view, 36, 'data');
  view.setUint32(40, dataBytes, true);

  let offset = wavHeaderBytes;
  samples.forEach((sample) => {
    const clamped = Math.max(-1, Math.min(1, sample));
    view.setInt16(offset, clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff, true);
    offset += bytesPerSample;
  });

  return new Blob([view], { type: 'audio/wav' });
}

function mergeAudioChunks(chunks: Float32Array[]) {
  const sampleCount = chunks.reduce((total, chunk) => total + chunk.length, 0);
  const samples = new Float32Array(sampleCount);
  let offset = 0;

  chunks.forEach((chunk) => {
    samples.set(chunk, offset);
    offset += chunk.length;
  });

  return samples;
}

function writeAscii(view: DataView, offset: number, value: string) {
  for (let index = 0; index < value.length; index += 1) {
    view.setUint8(offset + index, value.charCodeAt(index));
  }
}
