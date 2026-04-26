'use client';

import { useRef, useState } from 'react';

import { useSessionsContext } from '@/context/SessionsContext';

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
  targetEmotion: TargetEmotion | null;
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
  filler_word_breakdown: Record<string, number>;
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
    filler_word_breakdown: Record<string, number>;
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
  const { refetch: refetchSessions } = useSessionsContext();
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [status, setStatus] = useState<SessionStatus>('setup');
  const [scenarioPrompt, setScenarioPrompt] = useState('');
  const [critique, setCritique] = useState('');
  const [processingStage, setProcessingStage] = useState('');
  const [roundResult, setRoundResult] = useState<RoundResult | null>(null);
  const [summary, setSummary] = useState<SessionSummary | null>(null);
  const [errorMessage, setErrorMessage] = useState('');
  const [activeTtsKind, setActiveTtsKind] = useState<'scenario' | 'critique' | null>(null);
  const [isEnding, setIsEnding] = useState(false);
  const websocketRef = useRef<WebSocket | null>(null);
  const audioElementRef = useRef<HTMLAudioElement | null>(null);
  const ttsAbortControllerRef = useRef<AbortController | null>(null);
  const ttsTokenRef = useRef(0);

  async function startSession(setup: SessionSetup) {
    clearSessionSurface();
    setIsEnding(false);
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

    stopActiveAudio();
    setErrorMessage('');
    setIsEnding(!continueSession);
    const response = await fetch(`${API_URL}/api/phase-a/sessions/${sessionId}/continue`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ continue_session: continueSession }),
    });

    if (!response.ok) {
      setIsEnding(false);
      const errorDetail = await response
        .json()
        .then((payload) => String(payload.detail ?? ''))
        .catch(() => '');
      throw new Error(errorDetail || 'Could not send session decision.');
    }

    if (continueSession) {
      setIsEnding(false);
      setStatus('scenario');
      setScenarioPrompt('');
      setCritique('');
      setRoundResult(null);
      setProcessingStage('');
      setErrorMessage('');
      return;
    }
  }

  async function toggleTextToSpeech(kind: 'scenario' | 'critique', text: string) {
    const trimmedText = text.trim();
    if (!trimmedText) {
      return;
    }

    if (activeTtsKind === kind) {
      stopActiveAudio();
      return;
    }

    stopActiveAudio();
    setErrorMessage('');
    setActiveTtsKind(kind);

    const controller = new AbortController();
    ttsAbortControllerRef.current = controller;
    const playbackToken = ttsTokenRef.current;

    try {
      const response = await fetch(`${API_URL}/api/phase-a/tts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: trimmedText }),
        signal: controller.signal,
      });

      if (!response.ok) {
        const errorDetail = await response
          .json()
          .then((payload) => String(payload.detail ?? ''))
          .catch(() => '');
        throw new Error(errorDetail || 'Could not play the audio.');
      }

      const audioBlob = await response.blob();
      if (controller.signal.aborted || playbackToken !== ttsTokenRef.current) {
        return;
      }

      playAudioBlob(audioBlob, playbackToken);
    } catch (error) {
      if (controller.signal.aborted) {
        return;
      }
      setActiveTtsKind(null);
      setErrorMessage(error instanceof Error ? error.message : 'Could not play the audio.');
    } finally {
      if (ttsAbortControllerRef.current === controller) {
        ttsAbortControllerRef.current = null;
      }
    }
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
      case 'round_result':
        setRoundResult(event.payload as unknown as RoundResult);
        setCritique(String(event.payload.critique ?? ''));
        setIsEnding(false);
        setStatus('critique');
        break;
      case 'retry_recording':
        setStatus('recording');
        setIsEnding(false);
        setErrorMessage(String(event.payload.message ?? 'Try recording again.'));
        break;
      case 'session_summary':
        setSummary(event.payload as unknown as SessionSummary);
        setIsEnding(false);
        setStatus('summary');
        void refetchSessions();
        break;
      case 'error':
        setIsEnding(false);
        setStatus('error');
        setErrorMessage(String(event.payload.message ?? 'Something went wrong.'));
        break;
      default:
        break;
    }
  }

  function clearSessionSurface() {
    stopActiveAudio();
    setScenarioPrompt('');
    setCritique('');
    setProcessingStage('');
    setRoundResult(null);
    setSummary(null);
    setErrorMessage('');
    setActiveTtsKind(null);
  }

  function playAudioBlob(blob: Blob, playbackToken: number) {
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    audioElementRef.current = audio;
    audio.onended = () => {
      URL.revokeObjectURL(url);
      if (audioElementRef.current === audio) {
        audioElementRef.current = null;
      }
      if (playbackToken === ttsTokenRef.current) {
        setActiveTtsKind(null);
      }
    };
    void audio.play().catch(() => {
      URL.revokeObjectURL(url);
      if (audioElementRef.current === audio) {
        audioElementRef.current = null;
      }
      if (playbackToken === ttsTokenRef.current) {
        setActiveTtsKind(null);
      }
    });
  }

  function stopActiveAudio() {
    ttsTokenRef.current += 1;
    ttsAbortControllerRef.current?.abort();
    ttsAbortControllerRef.current = null;
    setActiveTtsKind(null);
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
    setIsEnding(false);
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
    isScenarioAudioPlaying: activeTtsKind === 'scenario',
    isCritiqueAudioPlaying: activeTtsKind === 'critique',
    isEnding,
    startSession,
    uploadRecording,
    chooseContinue,
    toggleScenarioTextToSpeech: () => toggleTextToSpeech('scenario', scenarioPrompt),
    toggleCritiqueTextToSpeech: () => toggleTextToSpeech('critique', critique),
    resetAll,
  };
}

function getAudioFilename(audioBlob: Blob) {
  return audioBlob.type === 'audio/wav' ? 'phase-a-audio.wav' : 'phase-a-audio.webm';
}
