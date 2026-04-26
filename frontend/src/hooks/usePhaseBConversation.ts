'use client';

import { useEffect, useEffectEvent, useRef, useState } from 'react';
import { fetchVoicePreviewAudio } from '@/lib/tts-api';

export type ConversationStatus =
  | 'setup'
  | 'starting'
  | 'listening'
  | 'recording'
  | 'processing'
  | 'complete'
  | 'error';

export type PeerProfile = {
  name: string;
  role: string;
  vibe: string;
  energy: string;
  conversation_goal: string;
  scenario: string;
};

export type TurnAnalysis = {
  analysis_status: 'pending' | 'partial' | 'ready';
  summary: string;
  momentum_score: number;
  content_quality_score: number;
  emotional_delivery_score: number;
  energy_match_score: number;
  authenticity_score: number;
  follow_up_invitation_score: number;
  strengths: string[];
  growth_edges: string[];
};

export type ConversationTurn = {
  turn_index: number;
  prompt_text: string;
  transcript: string | null;
  analysis_status?: 'pending' | 'partial' | 'ready';
  turn_analysis?: TurnAnalysis | null;
  chunks?: Array<{
    chunk_index: number;
    status: string;
  }>;
};

export type FinalReport = {
  summary: string;
  natural_ending_reason: string;
  conversation_momentum_score: number;
  content_quality_score: number;
  emotional_delivery_score: number;
  energy_match_score: number;
  authenticity_score: number;
  follow_up_invitation_score: number;
  strengths: string[];
  growth_edges: string[];
  next_focus: string;
};

type SessionStateResponse = {
  session_id: string;
  practice_prompt: string | null;
  scenario: string | null;
  scenario_preference: string | null;
  peer_profile: PeerProfile | null;
  starter_topic: string | null;
  opening_line: string | null;
  turn_index: number;
  max_turns: number;
  minimum_turns: number;
  conversation_history: Array<{ role: string; content: string }>;
  current_turn: ConversationTurn | null;
  turns: ConversationTurn[];
  momentum_decision: { continue_conversation: boolean; reason: string } | null;
  final_report: FinalReport | null;
  status: 'active' | 'complete' | 'error';
};

type WebsocketEvent = {
  type: string;
  payload: Record<string, unknown>;
};

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
const WS_URL = process.env.NEXT_PUBLIC_WS_URL ?? 'ws://localhost:8000';

export function usePhaseBConversation(options?: {
  voiceId?: string | null;
  speechRate?: number;
  playPeerVoice?: boolean;
}) {
  const voiceId = options?.voiceId ?? null;
  const speechRate = options?.speechRate ?? 1;
  const playPeerVoice = options?.playPeerVoice ?? true;
  const [status, setStatus] = useState<ConversationStatus>('setup');
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [practicePrompt, setPracticePrompt] = useState<string | null>(null);
  const [scenario, setScenario] = useState<string | null>(null);
  const [peerProfile, setPeerProfile] = useState<PeerProfile | null>(null);
  const [starterTopic, setStarterTopic] = useState<string | null>(null);
  const [currentTurn, setCurrentTurn] = useState<ConversationTurn | null>(null);
  const [turns, setTurns] = useState<ConversationTurn[]>([]);
  const [finalReport, setFinalReport] = useState<FinalReport | null>(null);
  const [processingStage, setProcessingStage] = useState('');
  const [errorMessage, setErrorMessage] = useState('');
  const [maxRecordingSeconds, setMaxRecordingSeconds] = useState(45);
  const [isPeerSpeaking, setIsPeerSpeaking] = useState(false);
  const [replayingTurnIndex, setReplayingTurnIndex] = useState<number | null>(null);
  const websocketRef = useRef<WebSocket | null>(null);
  const audioElementRef = useRef<HTMLAudioElement | null>(null);
  const audioChunksRef = useRef<string[]>([]);
  const pendingRecordingReadyRef = useRef(false);
  const peerSpeakingRef = useRef(false);
  const skipPeerAudioRef = useRef(false);
  const playPeerVoiceRef = useRef(playPeerVoice);
  const audioPlaybackTokenRef = useRef(0);
  const stopActiveAudioForLifecycle = useEffectEvent(() => {
    stopActiveAudio();
  });

  playPeerVoiceRef.current = playPeerVoice;

  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.hidden) {
        stopActiveAudioForLifecycle();
      }
    };

    const handlePageHide = () => {
      stopActiveAudioForLifecycle();
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    window.addEventListener('pagehide', handlePageHide);

    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      window.removeEventListener('pagehide', handlePageHide);
      stopActiveAudioForLifecycle();
      websocketRef.current?.close();
      websocketRef.current = null;
    };
  }, []);

  async function startSession(promptText?: string | null) {
    clearSurface();
    setStatus('starting');
    setErrorMessage('');
    const normalizedPrompt = promptText?.trim() ? promptText.trim() : null;

    try {
      const response = await fetch(`${API_URL}/api/phase-b/sessions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          practice_prompt: normalizedPrompt,
          voice_id: voiceId,
        }),
      });

      if (!response.ok) {
        const detail = await safeDetail(response);
        throw new Error(detail || 'Could not start the conversation.');
      }

      const data = (await response.json()) as { session_id: string };
      setSessionId(data.session_id);
      setPracticePrompt(normalizedPrompt);
      connectWebsocket(data.session_id);
      await requestNextTurn(data.session_id);
    } catch (error) {
      stopActiveAudio();
      websocketRef.current?.close();
      websocketRef.current = null;
      setSessionId(null);
      clearSurface();
      setStatus('setup');
      throw error;
    }
  }

  async function requestNextTurn(idOverride?: string) {
    const activeSessionId = idOverride ?? sessionId;
    if (!activeSessionId) {
      throw new Error('No active session.');
    }

    setStatus('starting');
    setProcessingStage('');
    const response = await fetch(`${API_URL}/api/phase-b/sessions/${activeSessionId}/turns/next`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ voice_id: voiceId, speak_peer_message: playPeerVoice }),
    });

    if (!response.ok) {
      const detail = await safeDetail(response);
      throw new Error(detail || 'Could not get the next peer turn.');
    }

    await refreshSession(activeSessionId);
  }

  async function submitTurn(
    videoBlob: Blob,
    audioBlob: Blob,
    durationMs: number,
    fallbackTranscriptAudioBlob?: Blob | null,
  ) {
    if (!sessionId || currentTurn == null) {
      throw new Error('No active turn.');
    }

    setStatus('processing');
    setProcessingStage('Uploading your response');
    setErrorMessage('');

    const turnIndex = currentTurn.turn_index;

    const uploadChunkFormData = new FormData();
    uploadChunkFormData.append('video_file', videoBlob, 'phase-b-video.webm');
    uploadChunkFormData.append('audio_file', audioBlob, getAudioFilename(audioBlob));
    uploadChunkFormData.append('chunk_index', '0');
    uploadChunkFormData.append('start_ms', '0');
    uploadChunkFormData.append('end_ms', String(Math.max(Math.round(durationMs), 0)));
    uploadChunkFormData.append('mediapipe_metrics', '{}');

    const chunkResponse = await fetch(
      `${API_URL}/api/phase-b/sessions/${sessionId}/turns/${turnIndex}/chunks`,
      {
        method: 'POST',
        body: uploadChunkFormData,
      },
    );

    if (!chunkResponse.ok) {
      const detail = await safeDetail(chunkResponse);
      throw new Error(detail || 'Could not upload the turn recording.');
    }

    setProcessingStage('Transcribing your response');
    const primaryTranscriptResult = await tryTranscribeTurn(sessionId, turnIndex, audioBlob);
    if (primaryTranscriptResult.errorMessage) {
      const canRetryWithFallback =
        primaryTranscriptResult.retryable &&
        fallbackTranscriptAudioBlob != null &&
        fallbackTranscriptAudioBlob.size > 0 &&
        fallbackTranscriptAudioBlob.type === 'audio/wav' &&
        audioBlob.type !== 'audio/wav';

      if (!canRetryWithFallback) {
        throw new Error(primaryTranscriptResult.errorMessage);
      }

      setProcessingStage('Retrying transcription');
      const fallbackTranscriptResult = await tryTranscribeTurn(
        sessionId,
        turnIndex,
        fallbackTranscriptAudioBlob,
      );
      if (fallbackTranscriptResult.errorMessage) {
        throw new Error(fallbackTranscriptResult.errorMessage);
      }
      applyTranscriptToCurrentTurn(turnIndex, fallbackTranscriptResult.transcript);
    } else {
      applyTranscriptToCurrentTurn(turnIndex, primaryTranscriptResult.transcript);
    }

    setProcessingStage('Generating the next step');
    const completeResponse = await fetch(
      `${API_URL}/api/phase-b/sessions/${sessionId}/turns/${turnIndex}/complete`,
      {
        method: 'POST',
      },
    );

    if (!completeResponse.ok) {
      const detail = await safeDetail(completeResponse);
      throw new Error(detail || 'Could not complete the turn.');
    }

    const completeData = (await completeResponse.json()) as {
      continue_conversation: boolean;
      final_report?: FinalReport | null;
    };

    await refreshSession(sessionId);

    if (completeData.final_report) {
      setFinalReport(completeData.final_report);
    }

    if (completeData.continue_conversation) {
      await requestNextTurn(sessionId);
      return;
    }

    setStatus('complete');
  }

  async function endSession() {
    if (!sessionId) {
      return;
    }

    setStatus('processing');
    setProcessingStage('Building final report');
    const response = await fetch(`${API_URL}/api/phase-b/sessions/${sessionId}/end`, {
      method: 'POST',
    });

    if (!response.ok) {
      const detail = await safeDetail(response);
      throw new Error(detail || 'Could not end the conversation.');
    }

    const data = (await response.json()) as { final_report?: FinalReport | null };
    if (data.final_report) {
      setFinalReport(data.final_report);
    }
    await refreshSession(sessionId);
    setStatus('complete');
  }

  async function refreshSession(idOverride?: string) {
    const activeSessionId = idOverride ?? sessionId;
    if (!activeSessionId) {
      return;
    }

    const response = await fetch(`${API_URL}/api/phase-b/sessions/${activeSessionId}`);
    if (!response.ok) {
      return;
    }

    const data = (await response.json()) as SessionStateResponse;
    applySessionState(data);
  }

  function connectWebsocket(id: string) {
    stopActiveAudio();
    websocketRef.current?.close();
    const socket = new WebSocket(`${WS_URL}/api/phase-b/ws/${id}`);
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
      case 'session_initialized':
        setScenario(String(event.payload.scenario ?? ''));
        setPeerProfile(event.payload.peer_profile as PeerProfile);
        setStarterTopic(String(event.payload.starter_topic ?? ''));
        break;
      case 'prompt_generated': {
        const promptText = String(event.payload.prompt_text ?? '');
        const nextTurnIndex = Number(event.payload.turn_index ?? 0);
        setCurrentTurn({
          turn_index: Number.isFinite(nextTurnIndex) ? nextTurnIndex : 0,
          prompt_text: promptText,
          transcript: null,
          analysis_status: 'pending',
          turn_analysis: null,
          chunks: [],
        });
        if (!playPeerVoiceRef.current && !audioElementRef.current && !peerSpeakingRef.current) {
          pendingRecordingReadyRef.current = false;
          setStatus('recording');
        }
        break;
      }
      case 'processing_stage':
        setStatus('processing');
        setProcessingStage(String(event.payload.stage ?? ''));
        break;
      case 'tts_start':
        if (event.payload.audio_type === 'peer_message') {
          stopActiveAudio();
          audioChunksRef.current = [];
          pendingRecordingReadyRef.current = false;
          skipPeerAudioRef.current = false;
          peerSpeakingRef.current = true;
          setIsPeerSpeaking(true);
          setStatus('listening');
        }
        break;
      case 'audio_chunk':
        if (event.payload.audio_type === 'peer_message') {
          if (!skipPeerAudioRef.current) {
            audioChunksRef.current.push(String(event.payload.chunk ?? ''));
          }
        }
        break;
      case 'tts_end':
        if (event.payload.audio_type === 'peer_message') {
          void playBufferedPeerAudio();
        }
        break;
      case 'recording_ready':
        setMaxRecordingSeconds(Number(event.payload.max_seconds ?? 45));
        pendingRecordingReadyRef.current = true;
        if (!audioElementRef.current && !peerSpeakingRef.current) {
          pendingRecordingReadyRef.current = false;
          setStatus('recording');
        }
        break;
      case 'turn_analysis_ready':
        void refreshSession();
        break;
      case 'session_complete':
        if (event.payload.final_report) {
          setFinalReport(event.payload.final_report as FinalReport);
        }
        setStatus('complete');
        void refreshSession();
        break;
      case 'error':
        setStatus('error');
        setErrorMessage(String(event.payload.message ?? 'Something went wrong.'));
        break;
      default:
        break;
    }
  }

  async function playBufferedPeerAudio() {
    const base64Chunks = audioChunksRef.current.slice();
    audioChunksRef.current = [];
    if (skipPeerAudioRef.current || base64Chunks.length === 0) {
      peerSpeakingRef.current = false;
      setIsPeerSpeaking(false);
      if (pendingRecordingReadyRef.current) {
        pendingRecordingReadyRef.current = false;
        setStatus('recording');
      }
      return;
    }

    stopActiveAudio();
    const blob = base64ChunksToBlob(base64Chunks, 'audio/mpeg');
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    attachAudioElement(audio, {
      onFinished: () => {
        setReplayingTurnIndex(null);
        peerSpeakingRef.current = false;
        setIsPeerSpeaking(false);
        if (pendingRecordingReadyRef.current) {
          pendingRecordingReadyRef.current = false;
          setStatus('recording');
        }
      },
    });
    audio.playbackRate = clampSpeechRate(speechRate);
    await audio.play().catch(() => {
      detachAudioElement(audio);
      setReplayingTurnIndex(null);
      peerSpeakingRef.current = false;
      setIsPeerSpeaking(false);
      if (pendingRecordingReadyRef.current) {
        pendingRecordingReadyRef.current = false;
        setStatus('recording');
      }
    });
  }

  function skipPeerAudio() {
    skipPeerAudioRef.current = true;
    audioChunksRef.current = [];
    stopActiveAudio();
    peerSpeakingRef.current = false;
    setIsPeerSpeaking(false);
    if (pendingRecordingReadyRef.current) {
      pendingRecordingReadyRef.current = false;
      setStatus('recording');
    }
  }

  async function replayPeerMessage(turnIndex: number, text: string) {
    const trimmedText = text.trim();
    if (!trimmedText) {
      return;
    }

    setErrorMessage('');
    setReplayingTurnIndex(turnIndex);
    stopActiveAudio();
    const playbackToken = audioPlaybackTokenRef.current;

    try {
      const blob = await fetchVoicePreviewAudio({
        voiceId,
        voiceName: peerProfile?.name || 'Peer',
        text: trimmedText,
      });
      if (playbackToken !== audioPlaybackTokenRef.current) {
        return;
      }
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      attachAudioElement(audio, {
        onFinished: () => {
          setReplayingTurnIndex((current) => (current === turnIndex ? null : current));
        },
      });
      audio.playbackRate = clampSpeechRate(speechRate);
      await audio.play();
    } catch (error) {
      setReplayingTurnIndex((current) => (current === turnIndex ? null : current));
      setErrorMessage(getErrorMessage(error, 'Could not replay that message.'));
    }
  }

  function applySessionState(data: SessionStateResponse) {
    setSessionId(data.session_id);
    setPracticePrompt(data.practice_prompt);
    setScenario(data.scenario);
    setPeerProfile(data.peer_profile);
    setStarterTopic(data.starter_topic);
    setCurrentTurn(data.current_turn);
    setTurns(data.turns);
    setFinalReport(data.final_report);

    if (data.status === 'complete') {
      setStatus('complete');
    }
  }

  function applyTranscriptToCurrentTurn(turnIndex: number, transcript: string) {
    if (!transcript) {
      return;
    }

    setCurrentTurn((existing) => {
      if (!existing || existing.turn_index !== turnIndex) {
        return existing;
      }
      return {
        ...existing,
        transcript,
      };
    });
  }

  function attachAudioElement(
    audio: HTMLAudioElement,
    options: {
      onFinished: () => void;
    },
  ) {
    audioElementRef.current = audio;
    audio.onended = () => {
      detachAudioElement(audio);
      options.onFinished();
    };
    audio.onerror = () => {
      detachAudioElement(audio);
      options.onFinished();
    };
  }

  function detachAudioElement(audio: HTMLAudioElement) {
    audio.onended = null;
    audio.onerror = null;
    if (audio.src.startsWith('blob:')) {
      URL.revokeObjectURL(audio.src);
    }
    if (audioElementRef.current === audio) {
      audioElementRef.current = null;
    }
  }

  function stopActiveAudio() {
    audioPlaybackTokenRef.current += 1;
    setReplayingTurnIndex(null);
    const audio = audioElementRef.current;
    if (!audio) {
      return;
    }

    audio.pause();
    audio.currentTime = 0;
    detachAudioElement(audio);
  }

  function clearSurface() {
    setPracticePrompt(null);
    setScenario(null);
    setPeerProfile(null);
    setStarterTopic(null);
    setCurrentTurn(null);
    setTurns([]);
    setFinalReport(null);
    setProcessingStage('');
    setErrorMessage('');
    setMaxRecordingSeconds(45);
    setReplayingTurnIndex(null);
    peerSpeakingRef.current = false;
    setIsPeerSpeaking(false);
    audioChunksRef.current = [];
    pendingRecordingReadyRef.current = false;
    skipPeerAudioRef.current = false;
  }

  function resetAll() {
    stopActiveAudio();
    websocketRef.current?.close();
    websocketRef.current = null;
    setSessionId(null);
    setStatus('setup');
    clearSurface();
  }

  return {
    status,
    sessionId,
    practicePrompt,
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
    replayingTurnIndex,
    skipPeerAudio,
    replayPeerMessage,
    startSession,
    submitTurn,
    requestNextTurn,
    refreshSession,
    endSession,
    resetAll,
  };
}

async function tryTranscribeTurn(sessionId: string, turnIndex: number, audioBlob: Blob) {
  const transcriptFormData = new FormData();
  transcriptFormData.append('audio_file', audioBlob, getAudioFilename(audioBlob));
  const transcriptResponse = await fetch(
    `${API_URL}/api/phase-b/sessions/${sessionId}/turns/${turnIndex}/transcribe`,
    {
      method: 'POST',
      body: transcriptFormData,
    },
  );

  if (transcriptResponse.ok) {
    const data = (await transcriptResponse.json()) as { transcript?: unknown };
    return {
      transcript: typeof data.transcript === 'string' ? data.transcript : '',
      errorMessage: '',
      retryable: false,
    };
  }

  const detail = await safeDetail(transcriptResponse);
  const errorMessage = detail || 'Could not transcribe the turn.';
  return {
    transcript: '',
    errorMessage,
    retryable: isRetryableTranscriptionError(transcriptResponse.status, errorMessage),
  };
}

async function safeDetail(response: Response) {
  try {
    const data = (await response.json()) as { detail?: unknown };
    return normalizeDetail(data.detail);
  } catch {
    return '';
  }
}

function normalizeDetail(detail: unknown): string {
  if (typeof detail === 'string') {
    return detail;
  }

  if (Array.isArray(detail)) {
    return detail
      .map((item) => normalizeDetail(item))
      .filter(Boolean)
      .join('; ');
  }

  if (detail && typeof detail === 'object') {
    const maybeMessage =
      ('message' in detail && normalizeDetail(detail.message)) ||
      ('detail' in detail && normalizeDetail(detail.detail)) ||
      ('msg' in detail && normalizeDetail(detail.msg));
    if (maybeMessage) {
      return maybeMessage;
    }

    try {
      return JSON.stringify(detail);
    } catch {
      return String(detail);
    }
  }

  if (detail == null) {
    return '';
  }

  return String(detail);
}

function isRetryableTranscriptionError(status: number, detail: string): boolean {
  if (status === 503) {
    return false;
  }

  const normalized = detail.toLowerCase();
  return !(
    normalized.includes('speech_to_text permission') ||
    normalized.includes('configured elevenlabs api key') ||
    normalized.includes('api key was rejected') ||
    normalized.includes('missing_permissions') ||
    normalized.includes('unauthorized')
  );
}

function base64ChunksToBlob(chunks: string[], mimeType: string) {
  const byteArrays = chunks.map((chunk) => {
    const binary = window.atob(chunk);
    const bytes = new Uint8Array(binary.length);
    for (let index = 0; index < binary.length; index += 1) {
      bytes[index] = binary.charCodeAt(index);
    }
    return bytes;
  });

  const totalLength = byteArrays.reduce((sum, bytes) => sum + bytes.length, 0);
  const merged = new Uint8Array(totalLength);
  let offset = 0;
  for (const bytes of byteArrays) {
    merged.set(bytes, offset);
    offset += bytes.length;
  }
  return new Blob([merged], { type: mimeType });
}

function getAudioFilename(audioBlob: Blob) {
  return audioBlob.type === 'audio/wav' ? 'phase-b-audio.wav' : 'phase-b-audio.webm';
}

function clampSpeechRate(value: number) {
  if (!Number.isFinite(value)) {
    return 1;
  }
  return Math.max(0.5, Math.min(1.5, value));
}

function getErrorMessage(error: unknown, fallback: string) {
  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }
  return fallback;
}
