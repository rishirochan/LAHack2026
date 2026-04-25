'use client';

import { useEffect, useRef, useState } from 'react';
import { RefreshCw, Mic, Square } from 'lucide-react';

const emotions = [
  'Confident',
  'Empathetic',
  'Assertive',
  'Calm',
  'Enthusiastic',
  'Authoritative',
  'Vulnerable',
  'Excited',
  'Neutral',
] as const;

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
const WS_URL = process.env.NEXT_PUBLIC_WS_URL ?? 'ws://localhost:8000';

const emotionMapping: Record<string, 'Confident' | 'Enthusiastic' | 'Calm' | 'Assertive' | 'Passionate'> = {
  Confident: 'Confident',
  Empathetic: 'Passionate',
  Assertive: 'Assertive',
  Calm: 'Calm',
  Enthusiastic: 'Enthusiastic',
  Authoritative: 'Assertive',
  Vulnerable: 'Passionate',
  Excited: 'Enthusiastic',
  Neutral: 'Calm',
};

function formatTime(seconds: number) {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, '0')}`;
}

export default function SprintPage() {
  const [step, setStep] = useState<'setup' | 'record'>('setup');
  const [selectedEmotion, setSelectedEmotion] = useState<string | null>(null);
  const [scenario, setScenario] = useState('');
  const [isRecording, setIsRecording] = useState(false);
  const [recordTime, setRecordTime] = useState(0);
  const [errorMessage, setErrorMessage] = useState('');
  const [isGeneratingScenario, setIsGeneratingScenario] = useState(false);
  const sessionIdRef = useRef<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  const previewRef = useRef<HTMLVideoElement | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const videoRecorderRef = useRef<MediaRecorder | null>(null);
  const audioRecorderRef = useRef<MediaRecorder | null>(null);
  const timerRef = useRef<number | null>(null);

  const openScenarioSocket = (sessionId: string) => {
    wsRef.current?.close();
    const socket = new WebSocket(`${WS_URL}/api/phase-a/ws/${sessionId}`);
    wsRef.current = socket;
    socket.onmessage = (message) => {
      const event = JSON.parse(message.data) as { type: string; payload: Record<string, unknown> };
      if (event.type === 'scenario') {
        setScenario(String(event.payload.scenario_prompt ?? ''));
        setIsGeneratingScenario(false);
        return;
      }
      if (event.type === 'error') {
        setIsGeneratingScenario(false);
        setErrorMessage(String(event.payload.message ?? 'Scenario generation failed.'));
      }
    };
    socket.onclose = () => {
      if (!scenario) {
        setIsGeneratingScenario(false);
      }
    };
    socket.onerror = () => {
      setIsGeneratingScenario(false);
      setErrorMessage('Could not open scenario stream. Please try again.');
    };
  };

  const createScenarioSession = async () => {
    const mappedEmotion = selectedEmotion ? emotionMapping[selectedEmotion] : 'Confident';
    const response = await fetch(`${API_URL}/api/phase-a/sessions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        theme: 'Job Interview',
        target_emotion: mappedEmotion,
        difficulty: 5,
      }),
    });
    if (!response.ok) {
      throw new Error(`Scenario request failed (${response.status})`);
    }
    const data = (await response.json()) as { session_id: string };
    sessionIdRef.current = data.session_id;
    openScenarioSocket(data.session_id);
  };

  const handleGenerateScenario = async () => {
    if (!selectedEmotion) return;
    setScenario('');
    setErrorMessage('');
    setIsGeneratingScenario(true);
    setStep('record');
    try {
      await createScenarioSession();
    } catch {
      setIsGeneratingScenario(false);
      setErrorMessage('Failed to fetch scenario from backend. Confirm backend is running on port 8000.');
    }
  };

  const startRecording = async () => {
    try {
      setErrorMessage('');
      const stream =
        mediaStreamRef.current ??
        (await navigator.mediaDevices.getUserMedia({ video: true, audio: true }));
      mediaStreamRef.current = stream;
      if (previewRef.current) previewRef.current.srcObject = stream;

      const audioOnlyStream = new MediaStream(stream.getAudioTracks());
      videoRecorderRef.current = new MediaRecorder(stream);
      audioRecorderRef.current = new MediaRecorder(audioOnlyStream);

      setIsRecording(true);
      setRecordTime(0);
      videoRecorderRef.current.start();
      audioRecorderRef.current.start();
      timerRef.current = window.setInterval(() => {
        setRecordTime((prev) => prev + 1);
      }, 1000);
    } catch {
      setErrorMessage('Camera or microphone access was blocked. Allow access and try again.');
    }
  };

  const stopRecording = () => {
    setIsRecording(false);
    if (timerRef.current) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }
    if (videoRecorderRef.current?.state === 'recording') videoRecorderRef.current.stop();
    if (audioRecorderRef.current?.state === 'recording') audioRecorderRef.current.stop();
  };

  useEffect(() => {
    return () => {
      if (timerRef.current) window.clearInterval(timerRef.current);
      mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
      wsRef.current?.close();
    };
  }, []);

  if (step === 'setup') {
    return (
      <div className="mx-auto max-w-3xl">
        <div className="mb-8">
          <h1 className="font-['Playfair_Display'] text-2xl font-semibold text-slate-900">
            Emotion Sprint
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            Pick an emotion, deliver the scenario, get instant feedback
          </p>
        </div>

        <h2 className="mb-4 text-sm font-medium text-slate-700">Choose an emotion to practice</h2>
        <div className="mb-8 flex flex-wrap gap-3">
          {emotions.map((emotion) => (
            <button
              key={emotion}
              onClick={() => setSelectedEmotion(emotion)}
              className={`rounded-full px-4 py-2 text-sm font-medium transition-all duration-200 ${
                selectedEmotion === emotion
                  ? 'bg-navy-500 text-white shadow-md'
                  : 'bg-cream-200 text-slate-600 hover:bg-cream-300'
              }`}
            >
              {emotion}
            </button>
          ))}
        </div>

        <button
          disabled={!selectedEmotion}
          onClick={handleGenerateScenario}
          className={`rounded-full px-6 py-3 text-sm font-medium transition-all ${
            selectedEmotion
              ? 'bg-navy-500 text-white shadow-md hover:bg-navy-600'
              : 'cursor-not-allowed bg-cream-200 text-slate-400'
          }`}
        >
          Generate scenario →
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <section className="rounded-3xl border border-cream-200 bg-white p-6">
        <p className="mb-2 text-sm font-semibold uppercase tracking-widest text-blue-600">Scenario</p>
        <p className="min-h-20 text-2xl font-semibold leading-relaxed text-foreground">
          {scenario || 'Generating your 2-sentence prompt...'}
        </p>
        <button
          onClick={handleGenerateScenario}
          disabled={isGeneratingScenario}
          className="mt-4 inline-flex items-center gap-2 text-sm text-slate-500 transition-colors hover:text-slate-700"
        >
          <RefreshCw size={14} /> Regenerate
        </button>
      </section>

      <section className="grid gap-6 lg:grid-cols-[1fr_260px]">
        <div className="flex min-h-[340px] flex-col items-center justify-center rounded-3xl border border-cream-200 bg-white p-8">
          <button
            type="button"
            onClick={isRecording ? stopRecording : startRecording}
            className={`flex h-36 w-36 items-center justify-center rounded-full transition ${
              isRecording ? 'animate-pulse bg-red-500 text-white' : 'bg-blue-600 text-white hover:bg-blue-700'
            }`}
          >
            {isRecording ? <Square className="h-10 w-10" /> : <Mic className="h-12 w-12" />}
          </button>
          <p className="mt-5 text-sm font-semibold text-foreground">
            {isRecording ? 'Recording...' : 'Click to start recording'}
          </p>
          <p className="mt-2 text-sm text-foreground/50">
            {isRecording ? `${formatTime(recordTime)} elapsed` : 'You will have 20 seconds to answer.'}
          </p>
          {errorMessage && (
            <p className="mt-4 rounded-2xl bg-red-50 px-4 py-3 text-sm text-red-600">{errorMessage}</p>
          )}
        </div>

        <div className="rounded-3xl border border-cream-200 bg-white p-4">
          <p className="mb-3 text-sm font-semibold text-foreground">Webcam preview</p>
          <video
            ref={previewRef}
            autoPlay
            muted
            playsInline
            className="aspect-[4/3] w-full rounded-2xl bg-foreground/10 object-cover"
          />
        </div>
      </section>
    </div>
  );
}
