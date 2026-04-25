'use client';

import { useEffect, useRef, useState } from 'react';
import { Loader2, Mic, RefreshCw, Square } from 'lucide-react';
import {
  emotionOptions,
  type SessionSetup,
  usePhaseASession,
} from '@/hooks/usePhaseASession';

const MAX_RECORDING_SECONDS = 20;
const MIN_RECORDING_SECONDS = 2;
const processingStages = [
  'Uploading recording',
  'Analyzing facial emotion',
  'Analyzing vocal emotion',
  'Transcribing speech',
  'Generating critique',
  'Preparing playback',
];

const defaultSetup: SessionSetup = {
  targetEmotion: 'Happiness',
};

export default function SprintPage() {
  const [setup, setSetup] = useState<SessionSetup>(defaultSetup);
  const [isRecording, setIsRecording] = useState(false);
  const [secondsRemaining, setSecondsRemaining] = useState(MAX_RECORDING_SECONDS);
  const [localError, setLocalError] = useState('');
  const previewRef = useRef<HTMLVideoElement | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const videoRecorderRef = useRef<MediaRecorder | null>(null);
  const audioRecorderRef = useRef<MediaRecorder | null>(null);
  const videoChunksRef = useRef<Blob[]>([]);
  const audioChunksRef = useRef<Blob[]>([]);
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
    startSession,
    uploadRecording,
    chooseContinue,
    resetAll,
  } = usePhaseASession();

  async function handleStart() {
    setLocalError('');
    try {
      await startSession(setup);
    } catch {
      setLocalError('Failed to start the drill. Confirm the backend is running and try again.');
    }
  }

  async function handleRegenerate() {
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

  async function startRecording() {
    try {
      setLocalError('');
      const stream =
        mediaStreamRef.current ??
        (await navigator.mediaDevices.getUserMedia({ video: true, audio: true }));
      mediaStreamRef.current = stream;
      if (previewRef.current) {
        previewRef.current.srcObject = stream;
      }

      videoChunksRef.current = [];
      audioChunksRef.current = [];
      const audioOnlyStream = new MediaStream(stream.getAudioTracks());
      const videoRecorder = new MediaRecorder(stream, {
        mimeType: getSupportedMimeType(['video/webm;codecs=vp8,opus', 'video/webm']),
      });
      const audioRecorder = new MediaRecorder(audioOnlyStream, {
        mimeType: getSupportedMimeType(['audio/webm;codecs=opus', 'audio/webm']),
      });

      videoRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          videoChunksRef.current.push(event.data);
        }
      };
      audioRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      videoRecorderRef.current = videoRecorder;
      audioRecorderRef.current = audioRecorder;
      startedAtRef.current = window.performance.now();
      setSecondsRemaining(MAX_RECORDING_SECONDS);
      setIsRecording(true);
      videoRecorder.start();
      audioRecorder.start();
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
      stopRecordersWithoutUpload(videoRecorderRef.current, audioRecorderRef.current);
      setLocalError('That recording was too short. Try again with a full response.');
      return;
    }

    const [videoBlob, audioBlob] = await Promise.all([
      stopRecorder(videoRecorderRef.current, videoChunksRef.current, 'video/webm'),
      stopRecorder(audioRecorderRef.current, audioChunksRef.current, 'audio/webm'),
    ]);
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
  }

  useEffect(() => {
    return () => {
      stopTimer();
      stopTracks();
    };
  }, []);

  const canRecord = status === 'recording' || isRecording;
  const shownError = localError || errorMessage;

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
          <h2 className="mb-4 text-sm font-medium text-slate-700">Choose an emotion to practice</h2>
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
            className="rounded-full bg-navy-500 px-6 py-3 text-sm font-medium text-white shadow-md transition-all hover:bg-navy-600"
          >
            Generate prompt →
          </button>
        </div>
      </div>
    );
  }

  if (status === 'summary') {
    const fillerEntries = Object.entries(summary?.filler_words ?? {});

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
          <section className="rounded-3xl border border-cream-200 bg-white p-6">
            <h2 className="mb-4 text-sm font-semibold uppercase tracking-widest text-navy-500">
              Critiques
            </h2>
            <div className="space-y-4">
              {(summary?.critiques ?? []).map((item, index) => (
                <div key={`${item}-${index}`} className="rounded-2xl bg-cream-100 p-4">
                  <p className="mb-1 text-xs font-semibold uppercase tracking-widest text-slate-400">
                    Round {index + 1}
                  </p>
                  <p className="text-sm leading-relaxed text-slate-700">{item}</p>
                </div>
              ))}
            </div>
          </section>

          <section className="rounded-3xl border border-cream-200 bg-white p-6">
            <h2 className="mb-4 text-sm font-semibold uppercase tracking-widest text-navy-500">
              Match Score Trend
            </h2>
            <div className="flex h-44 items-end gap-3 rounded-2xl bg-cream-100 p-4">
              {(summary?.match_scores ?? []).map((score, index) => (
                <div key={`${score}-${index}`} className="flex flex-1 flex-col items-center gap-2">
                  <div
                    className="w-full rounded-t-xl bg-navy-500"
                    style={{ height: `${Math.max(Math.round(score * 100), 8)}%` }}
                  />
                  <span className="text-xs font-semibold text-slate-500">{Math.round(score * 100)}%</span>
                </div>
              ))}
            </div>

            <h2 className="mb-4 mt-6 text-sm font-semibold uppercase tracking-widest text-navy-500">
              Filler Words
            </h2>
            <div className="flex flex-wrap gap-2">
              {fillerEntries.length ? (
                fillerEntries.map(([word, count]) => (
                  <span key={word} className="rounded-full bg-cream-100 px-3 py-1 text-sm text-slate-700">
                    {word}: {count}
                  </span>
                ))
              ) : (
                <span className="text-sm text-slate-500">No filler words detected.</span>
              )}
            </div>
          </section>
        </div>

        <button
          onClick={resetAll}
          className="rounded-full bg-navy-500 px-6 py-3 text-sm font-medium text-white shadow-md transition-all hover:bg-navy-600"
        >
          Start new session
        </button>
      </div>
    );
  }

  if (status === 'error') {
    return (
      <div className="mx-auto max-w-2xl rounded-3xl border border-red-200 bg-white p-8 text-center shadow-sm">
        <h1 className="font-['Playfair_Display'] text-2xl font-semibold text-slate-900">
          Something went wrong
        </h1>
        <p className="mt-3 text-sm text-slate-600">{shownError || 'Try starting the drill again.'}</p>
        <button
          onClick={resetAll}
          className="mt-6 rounded-full bg-navy-500 px-6 py-3 text-sm font-medium text-white shadow-md transition-all hover:bg-navy-600"
        >
          Restart
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <section className="rounded-3xl border border-cream-200 bg-white p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="mb-2 text-sm font-semibold uppercase tracking-widest text-navy-500">Emotion Prompt</p>
            <p className="min-h-20 text-2xl font-semibold leading-relaxed text-slate-900">
              {scenarioPrompt || 'Generating your 2-sentence prompt...'}
            </p>
          </div>
          <button
            onClick={handleRegenerate}
            disabled={status === 'processing'}
            className="inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm text-slate-500 transition-colors hover:bg-cream-100 hover:text-slate-700"
          >
            <RefreshCw size={14} /> Regenerate
          </button>
        </div>
      </section>

      <section className="grid gap-6 lg:grid-cols-[1fr_260px]">
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
                {isRecording ? 'Recording...' : 'Click to start recording'}
              </p>
              <p className={`mt-2 text-sm ${secondsRemaining <= 5 ? 'text-red-500' : 'text-slate-500'}`}>
                {isRecording ? `${secondsRemaining}s remaining` : 'You will have 20 seconds to answer.'}
              </p>
            </>
          )}

          {shownError && (
            <p className="mt-4 rounded-2xl bg-red-50 px-4 py-3 text-sm text-red-600">{shownError}</p>
          )}
        </div>

        <div className="rounded-3xl border border-cream-200 bg-white p-4">
          <p className="mb-3 text-sm font-semibold text-slate-900">Webcam preview</p>
          <video
            ref={previewRef}
            autoPlay
            muted
            playsInline
            className="aspect-[4/3] w-full rounded-2xl bg-slate-100 object-cover"
          />
        </div>
      </section>

      {(status === 'critique' || roundResult) && (
        <section className="grid gap-6 lg:grid-cols-[1fr_240px]">
          <div className="rounded-3xl border border-cream-200 bg-white p-6">
            <p className="mb-2 text-sm font-semibold uppercase tracking-widest text-navy-500">Coach Critique</p>
            <p className="text-lg leading-relaxed text-slate-700">{critique}</p>
            <div className="mt-6 flex flex-wrap gap-3">
              <button
                onClick={() => void chooseContinue(true)}
                className="rounded-full bg-navy-500 px-5 py-3 text-sm font-medium text-white shadow-md transition-all hover:bg-navy-600"
              >
                Try Again
              </button>
              <button
                onClick={() => void chooseContinue(false)}
                className="rounded-full border border-cream-300 px-5 py-3 text-sm font-medium text-slate-700 transition-all hover:bg-cream-100"
              >
                End Session
              </button>
            </div>
          </div>

          <ScoreCard score={roundResult?.match_score ?? 0} />
        </section>
      )}
    </div>
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

function ScoreCard({ score }: { score: number }) {
  const percentage = Math.round(score * 100);
  const accentClass =
    score > 0.6 ? 'text-emerald-600 stroke-emerald-500' : score >= 0.3 ? 'text-amber-500 stroke-amber-400' : 'text-red-500 stroke-red-400';
  const circumference = 2 * Math.PI * 42;
  const dashOffset = circumference * (1 - Math.min(Math.max(score, 0), 1));

  return (
    <div className="rounded-3xl border border-cream-200 bg-white p-6">
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
        Based on the strongest matching facial emotion event.
      </p>
    </div>
  );
}

function getSupportedMimeType(candidates: string[]) {
  return candidates.find((candidate) => MediaRecorder.isTypeSupported(candidate)) ?? '';
}

function stopRecordersWithoutUpload(
  videoRecorder: MediaRecorder | null,
  audioRecorder: MediaRecorder | null,
) {
  [videoRecorder, audioRecorder].forEach((recorder) => {
    if (recorder?.state === 'recording') {
      recorder.stop();
    }
  });
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
