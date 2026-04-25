'use client';

import { useRef, useState } from 'react';

export const emotionOptions = [
  'Anger',
  'Contempt',
  'Disgust',
  'Fear',
  'Happiness',
  'Neutrality (Neutral)',
  'Sadness',
  'Surprise',
] as const;

export type TargetEmotion = (typeof emotionOptions)[number];
export type SessionStatus =
  | 'setup'
  | 'scenario'
  | 'recording'
  | 'processing'
  | 'critique'
  | 'summary'
  | 'error';

export type SessionSetup = {
  targetEmotion: TargetEmotion;
};

export type DisplayMetric = {
  key: string;
  label: string;
  value?: number | string | null;
  display_value: string;
  description: string;
};

export type PhaseADerivedMetrics = {
  match_score?: number;
  overall_match_score?: number;
  peak_match_score?: number;
  filler_word_count?: number;
  filler_rate?: number;
  target_frame_ratio?: number;
  target_presence_score?: number;
  average_target_confidence?: number;
  face_voice_alignment_ratio?: number;
  aggregate_face_voice_alignment_ratio?: number;
  emotion_stability_score?: number;
  top_target_moments?: Array<{
    timestamp_ms: number | null;
    emotion_type: string;
    confidence: number;
    is_aggregate?: boolean;
    source?: string | null;
  }>;
  top_mismatch_moments?: Array<{
    timestamp_ms: number;
    word: string;
    face_emotion_type: string;
    voice_emotion_type: string;
    face_confidence: number;
    voice_confidence: number;
  }>;
  data_quality_flags?: string[];
};

export type RoundResult = {
  critique: string;
  match_score: number;
  filler_words_found: string[];
  filler_word_count: number;
  derived_metrics?: PhaseADerivedMetrics;
  display_metrics?: DisplayMetric[];
};

export type SessionSummary = {
  session_id: string;
  critiques: string[];
  match_scores: number[];
  filler_words: Record<string, number>;
  rounds: Array<{
    scenario_prompt: string;
    critique: string;
    match_score: number;
    filler_words_found: string[];
    filler_word_count: number;
    derived_metrics?: PhaseADerivedMetrics;
    display_metrics?: DisplayMetric[];
  }>;
};

type WebsocketEvent = {
  type: string;
  payload: Record<string, unknown>;
};

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
const WS_URL = process.env.NEXT_PUBLIC_WS_URL ?? 'ws://localhost:8000';

export function usePhaseASession() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [status, setStatus] = useState<SessionStatus>('setup');
  const [scenarioPrompt, setScenarioPrompt] = useState('');
  const [critique, setCritique] = useState('');
  const [processingStage, setProcessingStage] = useState('');
  const [roundResult, setRoundResult] = useState<RoundResult | null>(null);
  const [summary, setSummary] = useState<SessionSummary | null>(null);
  const [errorMessage, setErrorMessage] = useState('');
  const websocketRef = useRef<WebSocket | null>(null);
  const audioElementRef = useRef<HTMLAudioElement | null>(null);

  async function startSession(setup: SessionSetup) {
    clearSessionSurface();
    setStatus('scenario');

    const response = await fetch(`${API_URL}/api/phase-a/sessions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        target_emotion: setup.targetEmotion,
      }),
    });

    if (!response.ok) {
      throw new Error('Could not start the emotion drill session.');
    }

    const data = (await response.json()) as { session_id: string };
    setSessionId(data.session_id);
    connectWebsocket(data.session_id);
  }

  async function uploadRecording(videoBlob: Blob, audioBlob: Blob, durationSeconds: number) {
    if (!sessionId) {
      throw new Error('No active session.');
    }

    setStatus('processing');
    setProcessingStage('Uploading recording');
    setErrorMessage('');

    const formData = new FormData();
    formData.append('video_file', videoBlob, 'phase-a-video.webm');
    formData.append('audio_file', audioBlob, getAudioFilename(audioBlob));
    formData.append('duration_seconds', String(durationSeconds));

    const response = await fetch(`${API_URL}/api/phase-a/sessions/${sessionId}/recording`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      throw new Error('Could not upload the recording.');
    }

    const data = (await response.json()) as { status: string };
    if (data.status === 'retry') {
      setStatus('recording');
    }
  }

  async function chooseContinue(continueSession: boolean) {
    if (!sessionId) {
      return;
    }

    setErrorMessage('');
    const response = await fetch(`${API_URL}/api/phase-a/sessions/${sessionId}/continue`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ continue_session: continueSession }),
    });

    if (!response.ok) {
      const errorDetail = await response
        .json()
        .then((payload) => String(payload.detail ?? ''))
        .catch(() => '');
      throw new Error(errorDetail || 'Could not send session decision.');
    }

    if (continueSession) {
      setStatus('scenario');
      setScenarioPrompt('');
      setCritique('');
      setRoundResult(null);
      setProcessingStage('');
      setErrorMessage('');
      return;
    }

    setStatus('summary');
  }

  function connectWebsocket(id: string) {
    websocketRef.current?.close();
    const socket = new WebSocket(`${WS_URL}/api/phase-a/ws/${id}`);
    websocketRef.current = socket;

    socket.onmessage = (message) => {
      const event = JSON.parse(message.data) as WebsocketEvent;
      handleEvent(event);
    };

    socket.onerror = () => {
      setStatus('error');
      setErrorMessage('Realtime connection failed. Refresh and try again.');
    };
  }

  function handleEvent(event: WebsocketEvent) {
    switch (event.type) {
      case 'scenario':
        setScenarioPrompt(String(event.payload.scenario_prompt ?? ''));
        setStatus('scenario');
        break;
      case 'recording_ready':
        setStatus('recording');
        break;
      case 'processing_stage':
        setStatus('processing');
        setProcessingStage(String(event.payload.stage ?? ''));
        break;
      case 'tts_start':
        stopActiveAudio();
        if (event.payload.audio_type === 'critique') {
          setCritique(String(event.payload.text ?? ''));
          setStatus('critique');
        }
        break;
      case 'audio_blob':
        playAudioBlob(
          String(event.payload.audio ?? ''),
          String(event.payload.mime_type ?? 'audio/mpeg'),
        );
        break;
      case 'round_result':
        setRoundResult(event.payload as unknown as RoundResult);
        setCritique(String(event.payload.critique ?? ''));
        break;
      case 'retry_recording':
        setStatus('recording');
        setErrorMessage(String(event.payload.message ?? 'Try recording again.'));
        break;
      case 'session_summary':
        setSummary(event.payload as unknown as SessionSummary);
        setStatus('summary');
        break;
      case 'error':
        setStatus('error');
        setErrorMessage(String(event.payload.message ?? 'Something went wrong.'));
        break;
      default:
        break;
    }
  }

  function clearSessionSurface() {
    setScenarioPrompt('');
    setCritique('');
    setProcessingStage('');
    setRoundResult(null);
    setSummary(null);
    setErrorMessage('');
  }

  function playAudioBlob(base64Audio: string, mimeType: string) {
    if (!base64Audio) {
      return;
    }

    stopActiveAudio();
    const binary = window.atob(base64Audio);
    const bytes = new Uint8Array(binary.length);
    for (let index = 0; index < binary.length; index += 1) {
      bytes[index] = binary.charCodeAt(index);
    }

    const blob = new Blob([bytes], { type: mimeType || 'audio/mpeg' });
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    audioElementRef.current = audio;
    audio.onended = () => {
      URL.revokeObjectURL(url);
      if (audioElementRef.current === audio) {
        audioElementRef.current = null;
      }
    };
    void audio.play().catch(() => {
      URL.revokeObjectURL(url);
      if (audioElementRef.current === audio) {
        audioElementRef.current = null;
      }
    });
  }

  function stopActiveAudio() {
    const audio = audioElementRef.current;
    if (!audio) {
      return;
    }

    audio.pause();
    audio.currentTime = 0;
    if (audio.src.startsWith('blob:')) {
      URL.revokeObjectURL(audio.src);
    }
    audioElementRef.current = null;
  }

  function resetAll() {
    stopActiveAudio();
    websocketRef.current?.close();
    websocketRef.current = null;
    setSessionId(null);
    setStatus('setup');
    clearSessionSurface();
  }

  return {
    status,
    sessionId,
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
  };
}

function getAudioFilename(audioBlob: Blob) {
  return audioBlob.type === 'audio/wav' ? 'phase-a-audio.wav' : 'phase-a-audio.webm';
}

