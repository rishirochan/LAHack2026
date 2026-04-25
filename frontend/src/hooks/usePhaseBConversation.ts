'use client';

import { useRef, useState } from 'react';

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
  scenario: string | null;
  scenario_preference: string | null;
  difficulty: number;
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

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8001';
const WS_URL = process.env.NEXT_PUBLIC_WS_URL ?? 'ws://localhost:8001';

export function usePhaseBConversation() {
  const [status, setStatus] = useState<ConversationStatus>('setup');
  const [sessionId, setSessionId] = useState<string | null>(null);
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
  const websocketRef = useRef<WebSocket | null>(null);
  const audioElementRef = useRef<HTMLAudioElement | null>(null);
  const audioChunksRef = useRef<string[]>([]);
  const pendingRecordingReadyRef = useRef(false);

  async function startSession(difficulty: number) {
    clearSurface();
    setStatus('starting');
    const response = await fetch(`${API_URL}/api/phase-b/sessions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        difficulty,
      }),
    });

    if (!response.ok) {
      throw new Error('Could not start the conversation.');
    }

    const data = (await response.json()) as { session_id: string };
    setSessionId(data.session_id);
    connectWebsocket(data.session_id);
    await requestNextTurn(data.session_id);
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
    });

    if (!response.ok) {
      const detail = await safeDetail(response);
      throw new Error(detail || 'Could not get the next peer turn.');
    }

    await refreshSession(activeSessionId);
  }

  async function submitTurn(videoBlob: Blob, audioBlob: Blob, durationMs: number) {
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
    uploadChunkFormData.append('end_ms', String(Math.max(durationMs, 0)));
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
    const transcriptFormData = new FormData();
    transcriptFormData.append('audio_file', audioBlob, getAudioFilename(audioBlob));
    const transcriptResponse = await fetch(
      `${API_URL}/api/phase-b/sessions/${sessionId}/turns/${turnIndex}/transcribe`,
      {
        method: 'POST',
        body: transcriptFormData,
      },
    );

    if (!transcriptResponse.ok) {
      const detail = await safeDetail(transcriptResponse);
      throw new Error(detail || 'Could not transcribe the turn.');
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
      case 'processing_stage':
        setStatus('processing');
        setProcessingStage(String(event.payload.stage ?? ''));
        break;
      case 'tts_start':
        if (event.payload.audio_type === 'peer_message') {
          audioChunksRef.current = [];
          pendingRecordingReadyRef.current = false;
          setIsPeerSpeaking(true);
          setStatus('listening');
        }
        break;
      case 'audio_chunk':
        if (event.payload.audio_type === 'peer_message') {
          audioChunksRef.current.push(String(event.payload.chunk ?? ''));
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
        if (!audioElementRef.current) {
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
    if (base64Chunks.length === 0) {
      setIsPeerSpeaking(false);
      if (pendingRecordingReadyRef.current) {
        setStatus('recording');
      }
      return;
    }

    stopActiveAudio();
    const blob = base64ChunksToBlob(base64Chunks, 'audio/mpeg');
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    audioElementRef.current = audio;
    audio.onended = () => {
      URL.revokeObjectURL(url);
      if (audioElementRef.current === audio) {
        audioElementRef.current = null;
      }
      setIsPeerSpeaking(false);
      if (pendingRecordingReadyRef.current) {
        pendingRecordingReadyRef.current = false;
        setStatus('recording');
      }
    };
    audio.onerror = () => {
      URL.revokeObjectURL(url);
      if (audioElementRef.current === audio) {
        audioElementRef.current = null;
      }
      setIsPeerSpeaking(false);
      if (pendingRecordingReadyRef.current) {
        pendingRecordingReadyRef.current = false;
        setStatus('recording');
      }
    };
    await audio.play().catch(() => {
      URL.revokeObjectURL(url);
      if (audioElementRef.current === audio) {
        audioElementRef.current = null;
      }
      setIsPeerSpeaking(false);
      if (pendingRecordingReadyRef.current) {
        pendingRecordingReadyRef.current = false;
        setStatus('recording');
      }
    });
  }

  function applySessionState(data: SessionStateResponse) {
    setSessionId(data.session_id);
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

  function clearSurface() {
    setScenario(null);
    setPeerProfile(null);
    setStarterTopic(null);
    setCurrentTurn(null);
    setTurns([]);
    setFinalReport(null);
    setProcessingStage('');
    setErrorMessage('');
    setMaxRecordingSeconds(45);
    setIsPeerSpeaking(false);
  }

  function resetAll() {
    stopActiveAudio();
    websocketRef.current?.close();
    websocketRef.current = null;
    audioChunksRef.current = [];
    pendingRecordingReadyRef.current = false;
    setSessionId(null);
    setStatus('setup');
    clearSurface();
  }

  return {
    status,
    sessionId,
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
    requestNextTurn,
    refreshSession,
    endSession,
    resetAll,
  };
}

async function safeDetail(response: Response) {
  try {
    const data = (await response.json()) as { detail?: string };
    return data.detail ?? '';
  } catch {
    return '';
  }
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
