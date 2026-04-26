'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { Loader2, Mic, Power, RotateCcw, Square, Video } from 'lucide-react';
import {
  type ConversationTurn,
  type FinalReport,
  type TurnAnalysis,
  usePhaseBConversation,
} from '@/hooks/usePhaseBConversation';
import { useVoiceSettings } from '@/context/VoiceSettingsContext';

const MIN_RECORDING_SECONDS = 2;

export default function ConversationPage() {
  const { selectedVoiceId, speechRate } = useVoiceSettings();
  const [isRecording, setIsRecording] = useState(false);
  const [secondsRemaining, setSecondsRemaining] = useState(45);
  const [localError, setLocalError] = useState('');
  const previewRef = useRef<HTMLVideoElement | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const videoRecorderRef = useRef<MediaRecorder | null>(null);
  const audioCaptureRef = useRef<TurnAudioCapture | null>(null);
  const videoChunksRef = useRef<Blob[]>([]);
  const startedAtRef = useRef<number>(0);
  const timerRef = useRef<number | null>(null);
  const chatEndRef = useRef<HTMLDivElement | null>(null);
  const {
    status,
    scenario,
    peerProfile,
    starterTopic,
    currentTurn,
    turns,
    finalReport,
    processingStage,
    errorMessage,
    maxRecordingSeconds,
    isPeerSpeaking,
    startSession,
    submitTurn,
    endSession,
    resetAll,
  } = usePhaseBConversation({
    voiceId: selectedVoiceId,
    speechRate,
  });

  const activeError = localError || errorMessage;
  const conversationTurns = useMemo(() => {
    return currentTurn ? [...turns, currentTurn] : turns;
  }, [currentTurn, turns]);
  const showPeerTypingBubble =
    status === 'starting' ||
    (status === 'processing' && processingStage === 'Generating the next step');

  async function handleStart() {
    setLocalError('');
    try {
      await startSession();
    } catch (error) {
      setLocalError(getErrorMessage(error, 'Failed to start the conversation.'));
    }
  }

  async function handleEnd() {
    setLocalError('');
    try {
      await endSession();
    } catch {
      setLocalError('Could not finish the session cleanly.');
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
      const stream = await ensurePreviewStream();
      videoChunksRef.current = [];
      const videoRecorder = new MediaRecorder(stream, {
        mimeType: getSupportedMimeType(['video/webm;codecs=vp8,opus', 'video/webm']),
      });
      const audioCapture = createTurnAudioCapture(stream);

      videoRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          videoChunksRef.current.push(event.data);
        }
      };

      videoRecorderRef.current = videoRecorder;
      audioCaptureRef.current = audioCapture;
      startedAtRef.current = window.performance.now();
      setSecondsRemaining(maxRecordingSeconds);
      setIsRecording(true);
      videoRecorder.start();
      audioCapture.start();
      startCountdown();
    } catch {
      setLocalError('Camera or microphone access was blocked. Allow access and try again.');
    }
  }

  async function stopRecording() {
    stopTimer();
    setIsRecording(false);
    const durationMs = window.performance.now() - startedAtRef.current;
    const durationSeconds = durationMs / 1000;

    if (durationSeconds < MIN_RECORDING_SECONDS) {
      stopRecordersWithoutUpload(videoRecorderRef.current, audioCaptureRef.current);
      videoRecorderRef.current = null;
      audioCaptureRef.current = null;
      videoChunksRef.current = [];
      stopTracks();
      setLocalError('That recording was too short. Try again with a full response.');
      return;
    }

    const [videoBlob, audioResult] = await Promise.all([
      stopRecorder(videoRecorderRef.current, videoChunksRef.current, 'video/webm'),
      stopAudioCapture(audioCaptureRef.current),
    ]);

    videoRecorderRef.current = null;
    audioCaptureRef.current = null;
    videoChunksRef.current = [];
    stopTracks();
    try {
      await submitTurn(
        videoBlob,
        audioResult.primaryBlob,
        durationMs,
        audioResult.fallbackTranscriptBlob,
      );
    } catch (error) {
      setLocalError(getErrorMessage(error, 'Could not submit that turn. Please try again.'));
    }
  }

  async function ensurePreviewStream() {
    const existingStream = mediaStreamRef.current;
    if (existingStream) {
      if (previewRef.current) {
        previewRef.current.srcObject = existingStream;
      }
      return existingStream;
    }

    const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
    mediaStreamRef.current = stream;
    if (previewRef.current) {
      previewRef.current.srcObject = stream;
    }
    return stream;
  }

  function startCountdown() {
    stopTimer();
    timerRef.current = window.setInterval(() => {
      const elapsed = Math.floor((window.performance.now() - startedAtRef.current) / 1000);
      const remaining = Math.max(maxRecordingSeconds - elapsed, 0);
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
  }

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [conversationTurns, processingStage, status]);

  useEffect(() => {
    setSecondsRemaining(maxRecordingSeconds);
  }, [maxRecordingSeconds]);

  useEffect(() => {
    return () => {
      stopTimer();
      audioCaptureRef.current?.discard();
      stopTracks();
    };
  }, []);

  if (status === 'setup') {
    return (
      <div className="mx-auto max-w-5xl space-y-6">
        <div>
          <h1 className="font-['Playfair_Display'] text-2xl font-semibold text-slate-900">
            Conversation Practice
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            Talk with a generated peer, respond on camera, and get a balanced conversation report.
          </p>
        </div>

        <section className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
          <div className="rounded-3xl border border-cream-200 bg-white p-8 shadow-sm">
            <h2 className="text-sm font-semibold uppercase tracking-widest text-navy-500">
              Session Shape
            </h2>
            <p className="mt-3 text-sm leading-6 text-slate-600">
              We generate the peer and topic automatically. Each turn is one short camera response, fast
              transcription drives the next reply, and video analysis keeps running in the background.
            </p>

            <div className="mt-8 space-y-3 rounded-2xl border border-cream-200 bg-cream-50 p-4 text-sm text-slate-600">
              <p>One peer persona is generated for the full session, then each response shapes the next turn.</p>
              <p>Voice playback follows your selected Settings voice when one is configured.</p>
              <p>Sessions end naturally after enough momentum has been established or when you end them manually.</p>
            </div>

            <div className="mt-8 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-900">
              Camera video and microphone audio are uploaded for analysis during the session. Media is stored
              as session-linked files rather than inside the session document itself.
            </div>

            <button
              type="button"
              onClick={handleStart}
              className="mt-8 rounded-full bg-navy-500 px-6 py-3 text-sm font-medium text-white shadow-md transition hover:bg-navy-600"
            >
              Start Conversation
            </button>
          </div>

          <div className="rounded-3xl border border-cream-200 bg-white p-8 shadow-sm">
            <h2 className="text-sm font-semibold uppercase tracking-widest text-navy-500">
              What Gets Scored
            </h2>
            <div className="mt-4 space-y-3 text-sm text-slate-600">
              <MetricRow label="Conversation momentum" />
              <MetricRow label="Content quality" />
              <MetricRow label="Emotional delivery" />
              <MetricRow label="Energy matching" />
              <MetricRow label="Authenticity" />
              <MetricRow label="Follow-up invitation" />
            </div>
          </div>
        </section>
      </div>
    );
  }

  return (
    <div className="grid h-[calc(100vh-64px)] gap-4 lg:grid-cols-[1.25fr_0.75fr]">
      <section className="flex min-h-0 flex-col overflow-hidden rounded-3xl border border-cream-200 bg-white shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-4 border-b border-cream-200 px-5 py-4">
          <div>
            <h1 className="font-['Playfair_Display'] text-2xl font-semibold text-slate-900">
              {peerProfile ? `${peerProfile.name} is on the line` : 'Starting the conversation'}
            </h1>
            <p className="mt-1 text-sm text-slate-500">
              {peerProfile
                ? `${peerProfile.role} • ${scenario ?? peerProfile.scenario} • topic: ${starterTopic ?? 'loading'}`
                : 'Generating a peer and opening topic.'}
            </p>
          </div>

          <div className="flex items-center gap-2">
            <StatusPill
              label={
                status === 'processing'
                  ? processingStage || 'Processing'
                  : status === 'recording'
                    ? 'Your turn'
                    : status === 'listening'
                      ? 'Peer speaking'
                      : status === 'complete'
                        ? 'Session complete'
                        : 'Starting'
              }
              tone={status === 'error' ? 'error' : status === 'complete' ? 'success' : 'default'}
            />
            <button
              type="button"
              onClick={handleEnd}
              disabled={status === 'complete' || status === 'starting'}
              className="inline-flex items-center gap-2 rounded-full border border-cream-300 px-4 py-2 text-sm text-slate-700 transition hover:bg-cream-100 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Power className="h-4 w-4" />
              End
            </button>
          </div>
        </div>

        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-5 py-5">
          {conversationTurns.map((turn) => (
            <TurnTranscript key={turn.turn_index} turn={turn} />
          ))}
          {showPeerTypingBubble && <PeerTypingBubble />}
          {status === 'processing' && (
            <div className="flex justify-center">
              <div className="inline-flex items-center gap-2 rounded-full bg-cream-100 px-4 py-2 text-sm text-slate-600">
                <Loader2 className="h-4 w-4 animate-spin" />
                {processingStage || 'Processing your turn'}
              </div>
            </div>
          )}
          <div ref={chatEndRef} />
        </div>

        <div className="border-t border-cream-200 px-5 py-4">
          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={toggleRecording}
              disabled={status !== 'recording' && !isRecording}
              className={`inline-flex h-12 min-w-[160px] items-center justify-center gap-2 rounded-full px-5 text-sm font-medium transition ${
                isRecording
                  ? 'bg-red-500 text-white hover:bg-red-600'
                  : 'bg-navy-500 text-white hover:bg-navy-600 disabled:bg-slate-300'
              }`}
            >
              {isRecording ? <Square className="h-4 w-4" /> : <Mic className="h-4 w-4" />}
              {isRecording ? 'Stop recording' : 'Record response'}
            </button>

            <p className="text-sm text-slate-500">
              {isRecording
                ? `${secondsRemaining}s remaining`
                : status === 'recording'
                  ? `Keep it between ${MIN_RECORDING_SECONDS} and ${maxRecordingSeconds} seconds.`
                  : isPeerSpeaking
                    ? 'Wait for the peer audio to finish.'
                    : 'The next recording window will open automatically.'}
            </p>
          </div>

          {activeError && (
            <p className="mt-3 rounded-2xl bg-red-50 px-4 py-3 text-sm text-red-600">{activeError}</p>
          )}
        </div>
      </section>

      <aside className="flex min-h-0 flex-col gap-4">
        <section className="rounded-3xl border border-cream-200 bg-white p-4 shadow-sm">
          <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-900">
            <Video className="h-4 w-4 text-navy-500" />
            Camera Preview
          </div>
          <video
            ref={previewRef}
            autoPlay
            muted
            playsInline
            className="aspect-[4/3] w-full rounded-2xl bg-slate-100 object-cover"
          />
        </section>

        <section className="rounded-3xl border border-cream-200 bg-white p-5 shadow-sm">
          <h2 className="text-sm font-semibold uppercase tracking-widest text-navy-500">Peer Profile</h2>
          {peerProfile ? (
            <div className="mt-4 space-y-3 text-sm text-slate-600">
              <InfoPair label="Name" value={peerProfile.name} />
              <InfoPair label="Role" value={peerProfile.role} />
              <InfoPair label="Vibe" value={peerProfile.vibe} />
              <InfoPair label="Energy" value={peerProfile.energy} />
              <InfoPair label="Goal" value={peerProfile.conversation_goal} />
            </div>
          ) : (
            <p className="mt-3 text-sm text-slate-500">Generating the peer and topic.</p>
          )}
        </section>

        {status === 'complete' && finalReport ? (
          <FinalReportCard finalReport={finalReport} onReset={resetAll} />
        ) : (
          <section className="rounded-3xl border border-cream-200 bg-white p-5 shadow-sm">
            <h2 className="text-sm font-semibold uppercase tracking-widest text-navy-500">Latest Turn</h2>
            {turns.length === 0 ? (
              <p className="mt-3 text-sm text-slate-500">
                Once you complete a few turns, the local analysis will show up here.
              </p>
            ) : (
              <TurnAnalysisCard turnAnalysis={turns[turns.length - 1].turn_analysis ?? null} />
            )}
          </section>
        )}

        {status === 'error' && (
          <button
            type="button"
            onClick={resetAll}
            className="inline-flex items-center justify-center gap-2 rounded-full bg-navy-500 px-5 py-3 text-sm font-medium text-white transition hover:bg-navy-600"
          >
            <RotateCcw className="h-4 w-4" />
            Restart
          </button>
        )}
      </aside>
    </div>
  );
}

function TurnTranscript({ turn }: { turn: ConversationTurn }) {
  return (
    <div className="space-y-3">
      <div className="flex justify-start">
        <div className="max-w-[80%] rounded-2xl rounded-bl-md border border-cream-200 bg-cream-50 px-4 py-3 text-sm leading-6 text-slate-700">
          {turn.prompt_text}
        </div>
      </div>
      {turn.transcript ? (
        <div className="flex justify-end">
          <div className="max-w-[80%] rounded-2xl rounded-br-md bg-navy-500 px-4 py-3 text-sm leading-6 text-white">
            {turn.transcript}
          </div>
        </div>
      ) : (
        <div className="flex justify-end">
          <div className="max-w-[80%] rounded-2xl rounded-br-md border border-dashed border-cream-300 bg-white px-4 py-3 text-sm text-slate-400">
            Your response is being captured.
          </div>
        </div>
      )}
    </div>
  );
}

function PeerTypingBubble() {
  return (
    <div className="flex justify-start">
      <div className="max-w-[80%] rounded-2xl rounded-bl-md border border-cream-200 bg-cream-50 px-4 py-3">
        <div className="flex items-center gap-1.5">
          <span className="h-2 w-2 animate-bounce rounded-full bg-slate-400" />
          <span
            className="h-2 w-2 animate-bounce rounded-full bg-slate-400"
            style={{ animationDelay: '0.15s' }}
          />
          <span
            className="h-2 w-2 animate-bounce rounded-full bg-slate-400"
            style={{ animationDelay: '0.3s' }}
          />
        </div>
      </div>
    </div>
  );
}

function TurnAnalysisCard({ turnAnalysis }: { turnAnalysis: TurnAnalysis | null }) {
  if (!turnAnalysis) {
    return <p className="mt-3 text-sm text-slate-500">Turn analysis is still processing.</p>;
  }

  return (
    <div className="mt-4 space-y-4">
      <p className="text-sm leading-6 text-slate-700">{turnAnalysis.summary}</p>
      <div className="grid grid-cols-2 gap-3">
        <ScoreTile label="Momentum" value={turnAnalysis.momentum_score} />
        <ScoreTile label="Content" value={turnAnalysis.content_quality_score} />
        <ScoreTile label="Delivery" value={turnAnalysis.emotional_delivery_score} />
        <ScoreTile label="Energy" value={turnAnalysis.energy_match_score} />
      </div>
      <BulletList title="Strengths" items={turnAnalysis.strengths} />
      <BulletList title="Next tweak" items={turnAnalysis.growth_edges} />
    </div>
  );
}

function FinalReportCard({
  finalReport,
  onReset,
}: {
  finalReport: FinalReport;
  onReset: () => void;
}) {
  return (
    <section className="rounded-3xl border border-cream-200 bg-white p-5 shadow-sm">
      <h2 className="text-sm font-semibold uppercase tracking-widest text-navy-500">Final Report</h2>
      <p className="mt-4 text-sm leading-6 text-slate-700">{finalReport.summary}</p>

      <div className="mt-4 grid grid-cols-2 gap-3">
        <ScoreTile label="Momentum" value={finalReport.conversation_momentum_score} />
        <ScoreTile label="Content" value={finalReport.content_quality_score} />
        <ScoreTile label="Delivery" value={finalReport.emotional_delivery_score} />
        <ScoreTile label="Energy" value={finalReport.energy_match_score} />
        <ScoreTile label="Authentic" value={finalReport.authenticity_score} />
        <ScoreTile label="Follow-up" value={finalReport.follow_up_invitation_score} />
      </div>

      <div className="mt-4 rounded-2xl bg-cream-50 p-4 text-sm text-slate-600">
        <p className="font-semibold text-slate-900">Why it ended</p>
        <p className="mt-1">{finalReport.natural_ending_reason}</p>
      </div>

      <BulletList title="Strengths" items={finalReport.strengths} />
      <BulletList title="Growth edges" items={finalReport.growth_edges} />

      <div className="mt-4 rounded-2xl border border-navy-100 bg-navy-50 p-4 text-sm text-navy-900">
        <p className="font-semibold">Next focus</p>
        <p className="mt-1">{finalReport.next_focus}</p>
      </div>

      <button
        type="button"
        onClick={onReset}
        className="mt-5 inline-flex items-center gap-2 rounded-full bg-navy-500 px-5 py-3 text-sm font-medium text-white transition hover:bg-navy-600"
      >
        <RotateCcw className="h-4 w-4" />
        Start another session
      </button>
    </section>
  );
}

function MetricRow({ label }: { label: string }) {
  return (
    <div className="flex items-center justify-between rounded-2xl bg-cream-50 px-4 py-3">
      <span>{label}</span>
      <span className="rounded-full bg-white px-3 py-1 text-xs font-medium text-slate-500">0-100</span>
    </div>
  );
}

function StatusPill({
  label,
  tone,
}: {
  label: string;
  tone: 'default' | 'success' | 'error';
}) {
  const toneClass =
    tone === 'success'
      ? 'bg-emerald-50 text-emerald-700'
      : tone === 'error'
        ? 'bg-red-50 text-red-600'
        : 'bg-cream-100 text-slate-600';
  return <span className={`rounded-full px-3 py-1.5 text-xs font-medium ${toneClass}`}>{label}</span>;
}

function InfoPair({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-widest text-slate-400">{label}</p>
      <p className="mt-1 text-sm text-slate-700">{value}</p>
    </div>
  );
}

function ScoreTile({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-2xl bg-cream-50 p-3">
      <p className="text-xs font-semibold uppercase tracking-widest text-slate-400">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-slate-900">{Math.round(value)}</p>
    </div>
  );
}

function BulletList({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="mt-4">
      <p className="text-xs font-semibold uppercase tracking-widest text-slate-400">{title}</p>
      <div className="mt-2 space-y-2">
        {items.map((item) => (
          <div key={item} className="rounded-2xl bg-cream-50 px-3 py-2 text-sm text-slate-700">
            {item}
          </div>
        ))}
      </div>
    </div>
  );
}

function getSupportedMimeType(candidates: string[]) {
  if (typeof MediaRecorder === 'undefined') {
    return '';
  }
  return candidates.find((candidate) => MediaRecorder.isTypeSupported(candidate)) ?? '';
}

function stopRecordersWithoutUpload(
  videoRecorder: MediaRecorder | null,
  audioCapture: TurnAudioCapture | null,
) {
  if (videoRecorder?.state === 'recording') {
    videoRecorder.stop();
  }
  audioCapture?.discard();
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

type TurnAudioRecorder = {
  mode: 'webm' | 'wav';
  start: () => void;
  stop: () => Promise<Blob>;
  discard: () => void;
};

type TurnAudioCapture = {
  start: () => void;
  stop: () => Promise<{ primaryBlob: Blob; fallbackTranscriptBlob: Blob | null }>;
  discard: () => void;
};

type WavAudioRecorder = {
  start: () => void;
  stop: () => Promise<Blob>;
  discard: () => void;
};

function createTurnAudioRecorder(stream: MediaStream): TurnAudioRecorder {
  const audioMimeType = getSupportedMimeType(['audio/webm;codecs=opus', 'audio/webm']);
  if (audioMimeType) {
    try {
      return createWebmAudioRecorder(stream, audioMimeType);
    } catch {
      return createWavFallbackRecorder(stream);
    }
  }
  return createWavFallbackRecorder(stream);
}

function createTurnAudioCapture(stream: MediaStream): TurnAudioCapture {
  const primaryRecorder = createTurnAudioRecorder(stream);
  const fallbackRecorder =
    primaryRecorder.mode === 'webm' ? createWavAudioRecorder(stream) : null;

  return {
    start: () => {
      primaryRecorder.start();
      fallbackRecorder?.start();
    },
    stop: async () => {
      const [primaryBlob, fallbackTranscriptBlob] = await Promise.all([
        primaryRecorder.stop(),
        fallbackRecorder ? fallbackRecorder.stop() : Promise.resolve(null),
      ]);
      return { primaryBlob, fallbackTranscriptBlob };
    },
    discard: () => {
      primaryRecorder.discard();
      fallbackRecorder?.discard();
    },
  };
}

function createWebmAudioRecorder(stream: MediaStream, mimeType: string): TurnAudioRecorder {
  const audioChunks: Blob[] = [];
  const recorder = new MediaRecorder(new MediaStream(stream.getAudioTracks()), {
    mimeType,
  });

  recorder.ondataavailable = (event) => {
    if (event.data.size > 0) {
      audioChunks.push(event.data);
    }
  };

  return {
    mode: 'webm',
    start: () => recorder.start(),
    stop: () =>
      new Promise<Blob>((resolve) => {
        recorder.onstop = () => {
          resolve(new Blob(audioChunks, { type: 'audio/webm' }));
        };

        if (recorder.state === 'recording') {
          recorder.stop();
        } else {
          resolve(new Blob(audioChunks, { type: 'audio/webm' }));
        }
      }),
    discard: () => {
      if (recorder.state === 'recording') {
        recorder.stop();
      }
    },
  };
}

function createWavFallbackRecorder(stream: MediaStream): TurnAudioRecorder {
  const recorder = createWavAudioRecorder(stream);
  return {
    mode: 'wav',
    start: recorder.start,
    stop: recorder.stop,
    discard: recorder.discard,
  };
}

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
      isCapturing = false;
      if (!isStopped) {
        isStopped = true;
        disconnectAudioNodes(source, processor);
        void audioContext.close();
      }
    },
  };
}

async function stopAudioCapture(capture: TurnAudioCapture | null) {
  if (!capture) {
    return {
      primaryBlob: new Blob([], { type: 'audio/webm' }),
      fallbackTranscriptBlob: null,
    };
  }
  return capture.stop();
}

function disconnectAudioNodes(
  source: MediaStreamAudioSourceNode,
  processor: ScriptProcessorNode,
) {
  try {
    source.disconnect();
  } catch {
    return;
  }
  try {
    processor.disconnect();
  } catch {
    return;
  }
}

function encodeWav(chunks: Float32Array[], sampleRate: number) {
  const audioData = flattenFloat32Arrays(chunks);
  const buffer = new ArrayBuffer(44 + audioData.length * 2);
  const view = new DataView(buffer);

  writeAscii(view, 0, 'RIFF');
  view.setUint32(4, 36 + audioData.length * 2, true);
  writeAscii(view, 8, 'WAVE');
  writeAscii(view, 12, 'fmt ');
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeAscii(view, 36, 'data');
  view.setUint32(40, audioData.length * 2, true);

  let offset = 44;
  for (const sample of audioData) {
    const clamped = Math.max(-1, Math.min(1, sample));
    view.setInt16(offset, clamped < 0 ? clamped * 0x8000 : clamped * 0x7FFF, true);
    offset += 2;
  }

  return new Blob([buffer], { type: 'audio/wav' });
}

function flattenFloat32Arrays(chunks: Float32Array[]) {
  const length = chunks.reduce((sum, chunk) => sum + chunk.length, 0);
  const merged = new Float32Array(length);
  let offset = 0;
  for (const chunk of chunks) {
    merged.set(chunk, offset);
    offset += chunk.length;
  }
  return merged;
}

function writeAscii(view: DataView, offset: number, text: string) {
  for (let index = 0; index < text.length; index += 1) {
    view.setUint8(offset + index, text.charCodeAt(index));
  }
}

function getErrorMessage(error: unknown, fallback: string) {
  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }
  if (typeof error === 'string' && error.trim()) {
    return error;
  }
  if (error && typeof error === 'object') {
    try {
      return JSON.stringify(error);
    } catch {
      return fallback;
    }
  }
  return fallback;
}
