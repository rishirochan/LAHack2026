'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import { Loader2, Mic, RotateCcw, Square, Video } from 'lucide-react';

import { EmotionTimeline } from '@/components/EmotionTimeline';
import { PhaseCScorecard } from '@/components/PhaseCScorecard';
import { usePhaseCSession } from '@/hooks/usePhaseCSession';
import { getPhaseCMergedChunks, useSession } from '@/hooks/useSessions';

const focusOptions = [
  'Filler words',
  'Emotion shifts',
  'Pace changes',
  'Eye contact',
  'Word repetition',
];

function formatTime(totalSeconds: number) {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, '0')}`;
}

export default function FreePage() {
  const router = useRouter();
  const [activeFocus, setActiveFocus] = useState<string[]>([]);
  const {
    status,
    sessionId,
    scorecard,
    writtenSummary,
    processingStage,
    errorMessage,
    recordSeconds,
    maxSeconds,
    waveformBars,
    chunkUploads,
    recordedVideoUrl,
    transcriptPreview,
    previewRef,
    startSession,
    beginRecording,
    restartRecording,
    stopRecording,
    retryRecording,
    resetAll,
  } = usePhaseCSession();
  const {
    data: persistedSession,
    loading: persistedSessionLoading,
    error: persistedSessionError,
    refetch: refetchPersistedSession,
  } = useSession(status === 'results' && sessionId ? sessionId : null);
  const mergedChunks = getPhaseCMergedChunks(persistedSession);

  const toggleFocus = (option: string) => {
    setActiveFocus((current) =>
      current.includes(option)
        ? current.filter((item) => item !== option)
        : [...current, option],
    );
  };

  const beginSession = async () => {
    await startSession();
  };

  useEffect(() => {
    if (status === 'results' && sessionId) {
      const retryDelaysMs = [0, 700, 2000];
      const timeoutIds = retryDelaysMs.map((delayMs) =>
        window.setTimeout(() => {
          void refetchPersistedSession();
        }, delayMs),
      );

      return () => {
        timeoutIds.forEach((timeoutId) => window.clearTimeout(timeoutId));
      };
    }
  }, [refetchPersistedSession, sessionId, status]);

  const showSetup = status === 'setup';
  const showActiveSession =
    status === 'preparing' ||
    status === 'ready' ||
    status === 'recording' ||
    status === 'uploading' ||
    status === 'processing' ||
    status === 'error';
  const isPreparing = status === 'preparing';
  const isRecording = status === 'recording';
  const isBusy = status === 'uploading' || status === 'processing';
  const captureStepActive = status !== 'setup';
  const transcribeStepActive = status === 'processing' || status === 'results';
  const scorecardStepActive = status === 'processing' || status === 'results';
  const resultsStepActive = status === 'results';

  return (
    <div className="mx-auto max-w-5xl">
      <div className="mb-6">
        <h1 className="font-['Playfair_Display'] text-2xl font-semibold text-slate-900">
          Free Speaking
        </h1>
        <p className="mt-1 text-sm text-slate-500">
          Record one uninterrupted speaking session and get a full broker scorecard.
        </p>
      </div>

      <AnimatePresence>
        {showSetup && (
          <motion.div
            key="setup"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -16 }}
            className="space-y-6"
          >
            <div className="grid gap-6 lg:grid-cols-[1.25fr_0.95fr]">
              <div className="rounded-2xl border border-cream-300 bg-white p-8 shadow-sm">
                <p className="text-xs uppercase tracking-[0.18em] text-slate-400">
                  Session Setup
                </p>
                <h2 className="mt-3 font-['Playfair_Display'] text-3xl font-semibold text-slate-900">
                  Speak freely for up to 45 seconds
                </h2>
                <p className="mt-3 max-w-xl text-sm leading-6 text-slate-500">
                  Phase C scores pacing, filler words, repetition, and emotional steadiness across
                  five-second chunks. Start the camera, choose the delivery cues you want to keep in
                  mind, and talk through any topic you want.
                </p>

                <div className="mt-8">
                  <p className="mb-3 text-xs font-medium uppercase tracking-[0.18em] text-slate-400">
                    Focus Areas
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {focusOptions.map((option) => (
                      <button
                        key={option}
                        type="button"
                        onClick={() => toggleFocus(option)}
                        className={`rounded-full px-4 py-2 text-sm font-medium transition-colors ${
                          activeFocus.includes(option)
                            ? 'bg-navy-500 text-white shadow-sm'
                            : 'bg-cream-100 text-slate-600 hover:bg-cream-200'
                        }`}
                      >
                        {option}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              <div className="overflow-hidden rounded-2xl border border-cream-300 bg-[linear-gradient(135deg,#0f172a_0%,#19345f_55%,#f4c978_140%)] p-8 text-white shadow-sm">
                <p className="text-xs uppercase tracking-[0.18em] text-white/65">What to expect</p>
                <div className="mt-6 grid gap-4">
                  <div className="rounded-2xl border border-white/15 bg-white/8 p-4 backdrop-blur-sm">
                    <p className="text-sm font-semibold">Live recording</p>
                    <p className="mt-1 text-sm text-white/75">
                      Camera preview, microphone waveform, and automatic five-second chunk uploads.
                    </p>
                  </div>
                  <div className="rounded-2xl border border-white/15 bg-white/8 p-4 backdrop-blur-sm">
                    <p className="text-sm font-semibold">Realtime processing</p>
                    <p className="mt-1 text-sm text-white/75">
                      Chunks are analyzed in the background while the full recording is transcribed.
                    </p>
                  </div>
                  <div className="rounded-2xl border border-white/15 bg-white/8 p-4 backdrop-blur-sm">
                    <p className="text-sm font-semibold">Final output</p>
                    <p className="mt-1 text-sm text-white/75">
                      You get an overall score, pacing analysis, repetition flags, and a coaching summary.
                    </p>
                  </div>
                </div>

                <button
                  type="button"
                  onClick={() => void beginSession()}
                  className="mt-8 inline-flex items-center gap-2 rounded-full bg-white px-6 py-3 text-sm font-semibold text-slate-900 transition-transform hover:-translate-y-0.5"
                >
                  <Video size={16} />
                  Start Session
                </button>
              </div>
            </div>
          </motion.div>
        )}

        {showActiveSession && (
          <motion.div
            key="active-session"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -16 }}
            className="grid gap-6 lg:grid-cols-[1.15fr_0.85fr]"
          >
            <div className="overflow-hidden rounded-2xl border border-cream-300 bg-white shadow-sm">
              <div className="border-b border-cream-200 px-6 py-4">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Camera Feed</p>
                    <p className="mt-1 text-sm text-slate-500">
                      {isPreparing
                        ? 'Turning on your camera and finishing session setup…'
                        : isRecording
                          ? 'Live preview while the session is recording.'
                          : isBusy
                            ? 'Your recording has stopped. Processing is underway.'
                            : 'When you are ready, click Start recording below. Your camera stays on for preview.'}
                    </p>
                  </div>
                  <div className="rounded-full bg-cream-100 px-3 py-1 text-xs font-medium text-slate-600">
                    Max {formatTime(maxSeconds)}
                  </div>
                </div>
              </div>

              <div className="p-6">
                <div className="relative aspect-video overflow-hidden rounded-[24px] bg-slate-950">
                  {recordedVideoUrl && !isRecording ? (
                    <video
                      src={recordedVideoUrl}
                      controls
                      playsInline
                      className="h-full w-full object-cover"
                    />
                  ) : (
                    <video
                      ref={previewRef}
                      autoPlay
                      muted
                      playsInline
                      className="h-full w-full object-cover"
                    />
                  )}

                  <div className="pointer-events-none absolute inset-x-0 bottom-0 bg-gradient-to-t from-slate-950/85 to-transparent px-5 pb-5 pt-16">
                    <div className="flex items-center justify-between gap-3">
                      <div className="inline-flex items-center gap-2 rounded-full bg-white/12 px-3 py-2 text-xs font-medium text-white backdrop-blur-sm">
                        <span
                          className={`h-2.5 w-2.5 rounded-full ${
                            isRecording ? 'animate-pulse bg-rose-400' : 'bg-white/50'
                          }`}
                        />
                        {isPreparing
                          ? 'Setting up'
                          : isRecording
                            ? 'Recording'
                            : isBusy
                              ? 'Processing'
                              : status === 'error'
                                ? 'Needs retry'
                                : 'Ready'}
                      </div>
                      <div className="rounded-full bg-black/35 px-3 py-2 font-mono text-sm text-white backdrop-blur-sm">
                        {formatTime(recordSeconds)}
                      </div>
                    </div>
                  </div>
                </div>

                <div className="mt-5">
                  <div className="mb-3 flex items-center justify-between">
                    <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Mic Activity</p>
                    <p className="text-xs text-slate-500">
                      {isPreparing
                        ? 'Connecting…'
                        : isRecording
                          ? 'Live analyser'
                          : isBusy
                            ? processingStage || 'Preparing results'
                            : 'Waiting'}
                    </p>
                  </div>
                  <div className="flex h-28 items-end justify-center gap-[3px] rounded-[22px] bg-cream-50 px-4 py-5">
                    {waveformBars.map((barHeight, index) => (
                      <motion.div
                        key={index}
                        animate={{ height: `${barHeight * 2.2}px` }}
                        transition={{ duration: 0.12 }}
                        className={`w-1.5 rounded-full ${
                          isRecording ? 'bg-navy-500' : 'bg-cream-300'
                        }`}
                      />
                    ))}
                  </div>
                </div>
              </div>
            </div>

            <div className="space-y-6">
              <div className="rounded-2xl border border-cream-300 bg-white p-6 shadow-sm">
                <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Session Status</p>
                <div className="mt-4 space-y-4">
                  <div className="flex items-center justify-between rounded-2xl bg-cream-50 px-4 py-3">
                    <span className="text-sm font-medium text-slate-700">Time elapsed</span>
                    <span className="font-mono text-sm text-slate-900">
                      {formatTime(recordSeconds)} / {formatTime(maxSeconds)}
                    </span>
                  </div>
                  <div className="flex items-center justify-between rounded-2xl bg-cream-50 px-4 py-3">
                    <span className="text-sm font-medium text-slate-700">Chunk uploads</span>
                    <div className="flex items-center gap-2">
                      {chunkUploads.length === 0 && (
                        <span className="text-xs text-slate-400">No completed chunks yet</span>
                      )}
                      {chunkUploads.map((chunk) => (
                        <span
                          key={chunk.chunkIndex}
                          title={`Chunk ${chunk.chunkIndex + 1}: ${chunk.status}`}
                          className={`h-3 w-3 rounded-full ${
                            chunk.status === 'uploaded'
                              ? 'bg-emerald-500'
                              : chunk.status === 'failed'
                              ? 'bg-rose-500'
                              : 'bg-amber-400'
                          }`}
                        />
                      ))}
                      {isRecording && <span className="h-3 w-3 animate-pulse rounded-full bg-navy-500" />}
                    </div>
                  </div>
                </div>

                {errorMessage && (
                  <div className="mt-4 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-600">
                    {errorMessage}
                  </div>
                )}

                {transcriptPreview && (
                  <div className="mt-4 rounded-2xl border border-cream-200 bg-cream-50 px-4 py-3">
                    <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Transcript Preview</p>
                    <p className="mt-2 text-sm leading-6 text-slate-600">{transcriptPreview}</p>
                  </div>
                )}

                <div className="mt-6 flex flex-wrap gap-3">
                  {isRecording && (
                    <button
                      type="button"
                      onClick={() => void stopRecording()}
                      className="inline-flex items-center gap-2 rounded-full bg-rose-500 px-5 py-3 text-sm font-semibold text-white transition-colors hover:bg-rose-600"
                    >
                      <Square size={16} />
                      Stop recording
                    </button>
                  )}

                  {isRecording && (
                    <button
                      type="button"
                      onClick={() => void restartRecording()}
                      className="inline-flex items-center gap-2 rounded-full bg-navy-500 px-5 py-3 text-sm font-semibold text-white transition-colors hover:bg-navy-600"
                    >
                      <RotateCcw size={16} />
                      Restart take
                    </button>
                  )}

                  {!isRecording && !isBusy && (
                    <button
                      type="button"
                      disabled={isPreparing}
                      onClick={() => {
                        if (isPreparing) {
                          return;
                        }
                        if (status === 'error') {
                          void retryRecording();
                          return;
                        }
                        void beginRecording();
                      }}
                      className={`inline-flex items-center gap-2 rounded-full px-5 py-3 text-sm font-semibold transition-colors ${
                        isPreparing
                          ? 'cursor-not-allowed bg-cream-200 text-slate-400'
                          : 'bg-navy-500 text-white hover:bg-navy-600'
                      }`}
                    >
                      {isPreparing ? (
                        <>
                          <Loader2 size={16} className="animate-spin" />
                          Setting up…
                        </>
                      ) : status === 'error' ? (
                        <>
                          <Mic size={16} />
                          Try again
                        </>
                      ) : (
                        <>
                          <Mic size={16} />
                          Start recording
                        </>
                      )}
                    </button>
                  )}

                  {(status === 'preparing' || status === 'error' || status === 'ready') && !isRecording && !isBusy && (
                    <button
                      type="button"
                      onClick={resetAll}
                      className="inline-flex items-center gap-2 rounded-full bg-cream-100 px-5 py-3 text-sm font-semibold text-slate-700 transition-colors hover:bg-cream-200"
                    >
                      <RotateCcw size={16} />
                      Start over
                    </button>
                  )}
                </div>
              </div>

              <div className="overflow-hidden rounded-2xl border border-cream-300 bg-[linear-gradient(135deg,#fff8eb_0%,#fef6dc_50%,#fffdf6_100%)] p-6 shadow-sm">
                <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Processing Flow</p>
                <div className="mt-5 space-y-3">
                  {[
                    { label: 'Capture chunks', active: captureStepActive },
                    { label: 'Transcribe audio', active: transcribeStepActive },
                    { label: 'Run scorecard', active: scorecardStepActive },
                    { label: 'Return results', active: resultsStepActive },
                  ].map((step, index) => (
                    <div key={step.label} className="flex items-center gap-3">
                      <div
                        className={`flex h-8 w-8 items-center justify-center rounded-full text-xs font-semibold ${
                          step.active ? 'bg-navy-500 text-white' : 'bg-white text-slate-400'
                        }`}
                      >
                        {index + 1}
                      </div>
                      <div className="flex-1 rounded-2xl bg-white/80 px-4 py-3 text-sm text-slate-600">
                        {step.label}
                      </div>
                    </div>
                  ))}
                </div>

                {isBusy && (
                  <div className="mt-5 inline-flex items-center gap-3 rounded-full bg-white px-4 py-3 text-sm text-slate-700 shadow-sm">
                    <Loader2 size={16} className="animate-spin text-navy-500" />
                    {processingStage || 'Working through the session analysis'}
                  </div>
                )}
              </div>
            </div>
          </motion.div>
        )}

        {status === 'results' && (
          <motion.div
            key="results"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -16 }}
            className="space-y-6"
          >
            <div className="grid gap-6 lg:grid-cols-[0.95fr_1.05fr]">
              <div className="overflow-hidden rounded-2xl border border-cream-300 bg-white shadow-sm">
                <div className="border-b border-cream-200 px-6 py-4">
                  <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Recorded Session</p>
                  <h2 className="mt-2 font-['Playfair_Display'] text-2xl font-semibold text-slate-900">
                    Final analysis
                  </h2>
                </div>
                <div className="p-6">
                  {recordedVideoUrl ? (
                    <video
                      src={recordedVideoUrl}
                      controls
                      playsInline
                      className="aspect-video w-full rounded-[24px] bg-slate-950 object-cover"
                    />
                  ) : (
                    <div className="flex aspect-video items-center justify-center rounded-[24px] bg-cream-50 text-sm text-slate-400">
                      Recording preview unavailable
                    </div>
                  )}

                  <div className="mt-5 grid gap-4">
                    <div className="rounded-2xl bg-cream-50 px-4 py-4">
                      <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Transcript</p>
                      <p className="mt-2 text-sm leading-6 text-slate-600">
                        {transcriptPreview || 'Transcript preview unavailable for this session.'}
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              <div className="space-y-6">
                <EmotionTimeline
                  chunks={mergedChunks}
                  loading={persistedSessionLoading}
                  errorMessage={persistedSessionError}
                />
                {persistedSessionLoading && (
                  <div className="inline-flex items-center gap-3 rounded-full bg-white px-4 py-3 text-sm text-slate-700 shadow-sm">
                    <Loader2 size={16} className="animate-spin text-navy-500" />
                    Loading persisted chunk analysis
                  </div>
                )}
              </div>
            </div>

            <PhaseCScorecard scorecard={scorecard} writtenSummary={writtenSummary} />

            <div className="flex flex-wrap gap-3">
              <button
                type="button"
                onClick={resetAll}
                className="inline-flex items-center gap-2 rounded-full bg-navy-500 px-5 py-3 text-sm font-semibold text-white transition-colors hover:bg-navy-600"
              >
                <RotateCcw size={16} />
                Record Again
              </button>
              <button
                type="button"
                onClick={() => router.push('/home')}
                className="rounded-full bg-cream-100 px-5 py-3 text-sm font-semibold text-slate-700 transition-colors hover:bg-cream-200"
              >
                Back to Home
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
