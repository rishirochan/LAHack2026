'use client';

import { startTransition, useEffect, useRef, useState } from 'react';
import { Loader2, Mic, RefreshCw, Square, Volume2 } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
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
      <div className="mx-auto max-w-4xl">
        <div className="mb-8">
          <h1 className="font-['Playfair_Display'] text-2xl font-semibold text-slate-900">
            Emotion Sprint
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            Pick one emotion, respond to a short prompt, and get feedback on how well you expressed it.
          </p>
        </div>

        <div className="rounded-3xl border border-cream-200 bg-white p-8 shadow-sm">
          <h2 className="mb-4 text-lg font-bold text-slate-900">Choose an emotion to practice</h2>
          <div className="mb-8 flex flex-wrap gap-3">
            {emotionOptions.map((emotion) => (
              <button
                key={emotion}
                onClick={() => setSetup((current) => ({ ...current, targetEmotion: emotion }))}
                className={`rounded-full px-4 py-2 text-sm font-medium transition-all duration-200 ${
                  setup.targetEmotion === emotion
                    ? 'bg-navy-500 text-white shadow-md'
                    : 'bg-cream-200 text-slate-600 hover:bg-cream-300'
                }`}
              >
                {emotion}
              </button>
            ))}
          </div>

          <button
            onClick={handleStart}
            disabled={!setup.targetEmotion}
            className="rounded-full bg-navy-500 px-6 py-3 text-sm font-medium text-white shadow-md transition-all hover:bg-navy-600 disabled:cursor-not-allowed disabled:bg-slate-300 disabled:shadow-none"
          >
            Generate prompt →
          </button>

          {shownError && <p className="mt-4 text-sm text-red-600">{shownError}</p>}
        </div>
      </div>
    );
  }

  if (status === 'summary') {
    const fillerEntries = Object.entries(summary?.filler_words ?? {});
    const matchScoreData = (summary?.match_scores ?? []).map((score, index) => ({
      round: `R${index + 1}`,
      score: Math.round(score * 100),
      fill: '#153e75',
    }));
    const fillerChartData = fillerEntries
      .map(([word, count]) => ({
        word,
        count: Number(count),
      }))
      .sort((left, right) => right.count - left.count);

    return (
      <div className="mx-auto max-w-5xl space-y-6">
        <div>
          <h1 className="font-['Playfair_Display'] text-2xl font-semibold text-slate-900">
            Session Summary
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            Review your critiques, emotion-match trend, and filler-word totals.
          </p>
        </div>

        <div className="grid gap-6 lg:grid-cols-2">
          <section className="rounded-2xl border border-cream-300 bg-white p-6 shadow-sm">
            <h2 className="mb-4 text-sm font-semibold uppercase tracking-widest text-navy-500">
              Critiques
            </h2>
            <div className="space-y-4">
              {(summary?.critiques ?? []).map((item, index) => (
                <div key={`${item}-${index}`} className="rounded-2xl bg-cream-100 p-4">
                  <p className="mb-1 text-xs font-semibold uppercase tracking-widest text-slate-400">
                    Round {index + 1}
                  </p>
                  <MarkdownCritique content={item} />
                </div>
              ))}
            </div>
          </section>

          <section className="rounded-2xl border border-cream-300 bg-white p-6 shadow-sm">
            <h2 className="mb-4 text-sm font-semibold uppercase tracking-widest text-navy-500">
              Match Score Trend
            </h2>
            <div className="h-52 rounded-2xl bg-cream-100 p-4">
              {matchScoreData.length ? (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={matchScoreData} margin={{ top: 8, right: 8, bottom: 0, left: 8 }}>
                    <CartesianGrid vertical={false} stroke="#eadcc2" />
                    <XAxis dataKey="round" tick={{ fill: '#64748b', fontSize: 12 }} tickLine={false} axisLine={false} />
                    <YAxis
                      domain={[0, 100]}
                      tick={{ fill: '#64748b', fontSize: 12 }}
                      tickLine={false}
                      axisLine={false}
                      width={40}
                    />
                    <Tooltip
                      cursor={{ fill: 'rgba(21, 62, 117, 0.08)' }}
                      formatter={(value) => [`${value}%`, 'Match score']}
                    />
                    <Bar dataKey="score" radius={[12, 12, 0, 0]}>
                      {matchScoreData.map((entry) => (
                        <Cell key={entry.round} fill={entry.fill} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex h-full items-center justify-center text-sm text-slate-500">
                  No rounds recorded yet.
                </div>
              )}
            </div>

            <h2 className="mb-4 mt-6 text-sm font-semibold uppercase tracking-widest text-navy-500">
              Filler Words
            </h2>
            <div className="rounded-2xl bg-cream-100 p-4">
              {fillerChartData.length ? (
                <div className="h-44">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={fillerChartData}
                      layout="vertical"
                      margin={{ top: 0, right: 8, bottom: 0, left: 8 }}
                    >
                      <CartesianGrid horizontal={false} stroke="#eadcc2" />
                      <XAxis
                        type="number"
                        tick={{ fill: '#64748b', fontSize: 12 }}
                        tickLine={false}
                        axisLine={false}
                        allowDecimals={false}
                      />
                      <YAxis
                        type="category"
                        dataKey="word"
                        tick={{ fill: '#64748b', fontSize: 12 }}
                        tickLine={false}
                        axisLine={false}
                        width={72}
                      />
                      <Tooltip formatter={(value) => [value, 'Count']} cursor={{ fill: 'rgba(21, 62, 117, 0.08)' }} />
                      <Bar dataKey="count" radius={[0, 12, 12, 0]} fill="#4f46e5" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <span className="text-sm text-slate-500">No filler words detected.</span>
              )}
            </div>
          </section>
        </div>

        <button
          onClick={handleResetAll}
          className="rounded-full bg-navy-500 px-6 py-3 text-sm font-semibold text-white shadow-sm transition-all hover:bg-navy-600"
        >
          Start new session
        </button>
      </div>
    );
  }

  if (status === 'error') {
    return (
      <div className="mx-auto max-w-2xl rounded-2xl border border-red-200 bg-white p-8 text-center shadow-sm">
        <h1 className="font-['Playfair_Display'] text-2xl font-semibold text-slate-900">
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
    <div className="space-y-6">
      <section className="rounded-2xl border border-cream-300 bg-white p-6 shadow-sm">
        <div className="flex min-h-[140px] flex-col justify-between gap-2">
          <div>
            <p className="mb-2 text-sm font-semibold uppercase tracking-widest text-navy-500">Emotion Prompt</p>
            <p className="min-h-20 text-2xl font-semibold leading-relaxed text-slate-900">
              {scenarioPrompt || 'Generating your 2-sentence prompt...'}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => {
                void toggleScenarioTextToSpeech();
              }}
              disabled={!scenarioPrompt}
              className={`inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${
                isScenarioAudioPlaying
                  ? 'bg-navy-500 text-white hover:bg-navy-600'
                  : 'text-slate-500 hover:bg-cream-100 hover:text-slate-700'
              }`}
            >
              {isScenarioAudioPlaying ? <Square size={14} /> : <Volume2 size={14} />}
              {isScenarioAudioPlaying ? 'Stop audio' : 'Listen'}
            </button>
            <button
              onClick={handleRegenerate}
              disabled={status === 'processing'}
              className="inline-flex w-fit items-center gap-2 rounded-full px-4 py-2 text-sm text-slate-500 transition-colors hover:bg-cream-100 hover:text-slate-700"
            >
              <RefreshCw size={14} /> Regenerate
            </button>
          </div>
        </div>
      </section>

      {(status === 'critique' || roundResult) && (
        <section className="grid gap-6 lg:grid-cols-[1fr_280px]">
          <div className="rounded-3xl border border-cream-200 bg-white p-6">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <p className="text-sm font-semibold uppercase tracking-widest text-navy-500">Coach Critique</p>
              <button
                type="button"
                onClick={() => {
                  void toggleCritiqueTextToSpeech();
                }}
                disabled={!critique}
                className={`inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${
                  isCritiqueAudioPlaying
                    ? 'bg-navy-500 text-white hover:bg-navy-600'
                    : 'text-slate-500 hover:bg-cream-100 hover:text-slate-700'
                }`}
              >
                {isCritiqueAudioPlaying ? <Square size={14} /> : <Volume2 size={14} />}
                {isCritiqueAudioPlaying ? 'Stop audio' : 'Listen'}
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
                className="rounded-full bg-navy-500 px-5 py-3 text-sm font-medium text-white shadow-md transition-all hover:bg-navy-600"
              >
                {isEnding ? 'Finishing...' : 'Next Exercise'}
              </button>
              <button
                onClick={() => {
                  void chooseContinue(false).catch((error: unknown) => {
                    setLocalError(error instanceof Error ? error.message : 'Could not send session decision.');
                  });
                }}
                disabled={isEnding}
                className="rounded-full border border-cream-300 px-5 py-3 text-sm font-medium text-slate-700 transition-all hover:bg-cream-100"
              >
                {isEnding ? 'Finishing...' : 'End Session'}
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

      {!(status === 'critique' || roundResult) && (
        <section className={`grid gap-6 ${status === 'processing' ? 'lg:grid-cols-1' : 'lg:grid-cols-[1fr_260px]'}`}>
          <div className="flex min-h-[340px] flex-col items-center justify-center rounded-3xl border border-cream-200 bg-white p-8">
            {status === 'processing' ? (
              <ProcessingStages activeStage={processingStage} />
            ) : (
              <>
                <button
                  type="button"
                  disabled={!canRecord}
                  onClick={toggleRecording}
                  className={`flex h-36 w-36 items-center justify-center rounded-full transition ${
                    isRecording
                      ? 'animate-pulse bg-red-500 text-white'
                      : 'bg-blue-600 text-white hover:bg-blue-700 disabled:bg-slate-300'
                  }`}
                >
                  {isRecording ? <Square className="h-10 w-10" /> : <Mic className="h-12 w-12" />}
                </button>
                <p className="mt-5 text-sm font-semibold text-slate-900">
                  {isRecording ? 'Recording...' : isPreparingPreview ? 'Preparing camera...' : 'Click to start recording'}
                </p>
                <p className={`mt-2 text-sm ${secondsRemaining <= 5 ? 'text-red-500' : 'text-slate-500'}`}>
                  {isRecording
                    ? `${secondsRemaining}s remaining`
                    : isPreparingPreview
                      ? 'Loading the selected camera mode.'
                      : 'You will have 20 seconds to answer.'}
                </p>
              </>
            )}

            {shownError && (
              <p className="mt-4 rounded-2xl bg-red-50 px-4 py-3 text-sm text-red-600">{shownError}</p>
            )}
          </div>

          {status !== 'processing' && (
            <div className="rounded-3xl border border-cream-200 bg-white p-4">
              <div className="mb-4 flex items-start justify-between gap-4">
                <div>
                  <p className="text-sm font-semibold text-slate-900">Webcam preview</p>
                  <p className="mt-1 text-xs text-slate-500">{captureModeDescription}</p>
                </div>
                <div className="flex items-center gap-3 rounded-2xl bg-cream-100 px-3 py-2">
                  <div className="text-right">
                    <p className="text-xs font-semibold uppercase tracking-widest text-slate-400">Analysis mode</p>
                    <p className="text-sm font-semibold text-slate-900">{isPowerfulMode ? 'Powerful' : 'Fast'}</p>
                  </div>
                  <Switch
                    checked={isPowerfulMode}
                    onCheckedChange={(checked) => setCaptureMode(checked ? POWERFUL_CAPTURE_MODE : FAST_CAPTURE_MODE)}
                    disabled={isRecording || isPreparingPreview}
                    aria-label={`Analysis mode: ${isPowerfulMode ? 'Powerful' : 'Fast'}`}
                  />
                </div>
              </div>
              <video
                ref={previewRef}
                autoPlay
                muted
                playsInline
                className="aspect-[4/3] w-full rounded-2xl bg-slate-100 object-cover"
              />
              {!hasPreviewStream && (
                <div className="mt-3 rounded-2xl bg-cream-50 px-4 py-3 text-sm text-slate-500">
                  {isPreparingPreview
                    ? 'Preparing the selected camera mode...'
                    : 'Camera preview appears here when the selected mode is ready.'}
                </div>
              )}
            </div>
          )}
        </section>
      )}
    </div>
  );
}

function MarkdownCritique({ content }: { content: string }) {
  return (
    <ReactMarkdown
      components={{
        h1: ({ children }) => <h1 className="mb-3 text-2xl font-semibold leading-snug text-slate-900">{children}</h1>,
        h2: ({ children }) => <h2 className="mb-3 text-xl font-semibold leading-snug text-slate-900">{children}</h2>,
        h3: ({ children }) => <h3 className="mb-3 text-lg font-semibold leading-snug text-slate-900">{children}</h3>,
        p: ({ children }) => <p className="mb-3 text-lg leading-relaxed text-slate-700 last:mb-0">{children}</p>,
        strong: ({ children }) => <strong className="font-semibold text-slate-900">{children}</strong>,
        em: ({ children }) => <em className="italic">{children}</em>,
        ul: ({ children }) => <ul className="mb-3 list-disc space-y-2 pl-5 text-lg leading-relaxed text-slate-700">{children}</ul>,
        ol: ({ children }) => <ol className="mb-3 list-decimal space-y-2 pl-5 text-lg leading-relaxed text-slate-700">{children}</ol>,
        li: ({ children }) => <li>{children}</li>,
        code: ({ children }) => (
          <code className="rounded-md bg-cream-100 px-1.5 py-0.5 text-base text-slate-800">{children}</code>
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
