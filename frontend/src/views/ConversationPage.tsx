'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import { Mic, Square, Power, Video, Loader2 } from 'lucide-react';
import {
  type Scenario,
  type WsEvent,
  createSession,
  getSession,
  requestNextTurn,
  uploadChunk,
  transcribeTurn,
  completeTurn,
  endSession,
  connectWs,
} from '@/lib/phase-b-api';

// ---------------------------------------------------------------------------
// Scenario display metadata  (visual treatment unchanged)
// ---------------------------------------------------------------------------

const scenarioData: Record<
  Scenario,
  { label: string; description: string; color: string }
> = {
  interview: {
    label: 'Interview',
    description: 'Practice answering tough questions under pressure',
    color: 'border-navy-500',
  },
  negotiation: {
    label: 'Negotiation / Sales',
    description: 'Hone your persuasion and deal-making skills',
    color: 'border-teal-500',
  },
  casual: {
    label: 'Coffee Chat',
    description: 'Build rapport and practice casual networking',
    color: 'border-amber-500',
  },
  public_speaking: {
    label: 'Public Speaking',
    description: 'Deliver confident presentations to a live audience',
    color: 'border-violet-500',
  },
};

const CHUNK_DURATION_MS = 5_000;

// ---------------------------------------------------------------------------
// Chat message model
// ---------------------------------------------------------------------------

interface ChatMessage {
  id: string;
  role: 'assistant' | 'user' | 'critique';
  text: string;
}

// ---------------------------------------------------------------------------
// Phase states driven by websocket events
// ---------------------------------------------------------------------------

type TurnPhase =
  | 'idle'
  | 'requesting_prompt'
  | 'prompt_streaming'
  | 'playing_prompt_tts'
  | 'recording_ready'
  | 'recording'
  | 'uploading'
  | 'processing'
  | 'playing_critique_tts'
  | 'turn_done';

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function ConversationPage() {
  const router = useRouter();

  // Step 1 = setup, Step 2 = active conversation
  const [step, setStep] = useState<1 | 2>(1);
  const [scenario, setScenario] = useState<Scenario | null>(null);

  // Session
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [turnIndex, setTurnIndex] = useState(0);
  const [maxTurns, setMaxTurns] = useState(4);
  const [sessionStatus, setSessionStatus] = useState<'active' | 'complete' | 'error'>('active');

  // Chat thread
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isTyping, setIsTyping] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  // Turn phase
  const [turnPhase, setTurnPhase] = useState<TurnPhase>('idle');
  const [processingStage, setProcessingStage] = useState('');
  const [errorBanner, setErrorBanner] = useState('');
  const [hasMediaStream, setHasMediaStream] = useState(false);

  // Recording
  const [recordTime, setRecordTime] = useState(0);
  const [maxSeconds, setMaxSeconds] = useState(45);
  const previewRef = useRef<HTMLVideoElement | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const videoRecorderRef = useRef<MediaRecorder | null>(null);
  const audioRecorderRef = useRef<MediaRecorder | null>(null);
  const chunkVideoRecorderRef = useRef<MediaRecorder | null>(null);
  const chunkAudioRecorderRef = useRef<MediaRecorder | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const chunkTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const recordStartMsRef = useRef(0);
  const chunkIndexRef = useRef(0);
  const videoChunksRef = useRef<Blob[]>([]);
  const audioChunksRef = useRef<Blob[]>([]);
  const fullVideoChunksRef = useRef<Blob[]>([]);
  const fullAudioChunksRef = useRef<Blob[]>([]);

  // Audio playback
  const audioContextRef = useRef<AudioContext | null>(null);
  const audioQueueRef = useRef<ArrayBuffer[]>([]);
  const isPlayingAudioRef = useRef(false);
  const currentAudioTypeRef = useRef<'prompt' | 'critique' | null>(null);

  // WebSocket
  const wsRef = useRef<WebSocket | null>(null);

  // Session summary (for completion screen)
  const [completedTurns, setCompletedTurns] = useState<
    Array<{ turn_index: number; prompt: string; critique: string | null }>
  >([]);

  // -------------------------------------------------------------------------
  // Auto-scroll chat
  // -------------------------------------------------------------------------
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping]);

  // -------------------------------------------------------------------------
  // Cleanup on unmount
  // -------------------------------------------------------------------------
  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      if (chunkTimerRef.current) clearInterval(chunkTimerRef.current);
      mediaStreamRef.current?.getTracks().forEach((t) => t.stop());
      setHasMediaStream(false);
      wsRef.current?.close();
      audioContextRef.current?.close();
    };
  }, []);

  // -------------------------------------------------------------------------
  // Audio playback from base64 websocket chunks
  // -------------------------------------------------------------------------
  const drainAudioQueue = async () => {
    if (!audioContextRef.current) {
      audioContextRef.current = new AudioContext();
    }
    isPlayingAudioRef.current = true;
    while (audioQueueRef.current.length > 0) {
      const buf = audioQueueRef.current.shift()!;
      try {
        const decoded = await audioContextRef.current.decodeAudioData(buf.slice(0));
        const src = audioContextRef.current.createBufferSource();
        src.buffer = decoded;
        src.connect(audioContextRef.current.destination);
        src.start();
        await new Promise<void>((resolve) => {
          src.onended = () => resolve();
        });
      } catch {
        // skip undecodable frame
      }
    }
    isPlayingAudioRef.current = false;
  };

  const enqueueAudioChunk = useCallback(async (base64: string) => {
    const bytes = Uint8Array.from(atob(base64), (c) => c.charCodeAt(0));
    audioQueueRef.current.push(bytes.buffer);
    if (!isPlayingAudioRef.current) {
      void drainAudioQueue();
    }
  }, []);

  // -------------------------------------------------------------------------
  // WebSocket event handler
  // -------------------------------------------------------------------------
  const handleWsEvent = useCallback(
    (event: WsEvent) => {
      switch (event.type) {
        case 'prompt_generated': {
          setIsTyping(false);
          const text = event.payload.prompt_text;
          setMessages((prev) => [
            ...prev,
            { id: `prompt-${Date.now()}`, role: 'assistant', text },
          ]);
          setTurnPhase('prompt_streaming');
          break;
        }

        case 'tts_start': {
          currentAudioTypeRef.current = event.payload.audio_type;
          audioQueueRef.current = [];
          if (event.payload.audio_type === 'prompt') {
            setTurnPhase('playing_prompt_tts');
          } else {
            setTurnPhase('playing_critique_tts');
          }
          break;
        }

        case 'audio_chunk': {
          enqueueAudioChunk(event.payload.chunk);
          break;
        }

        case 'tts_end': {
          currentAudioTypeRef.current = null;
          break;
        }

        case 'recording_ready': {
          setMaxSeconds(event.payload.max_seconds);
          setTurnIndex(event.payload.turn_index);
          setTurnPhase('recording_ready');
          break;
        }

        case 'processing_stage': {
          setProcessingStage(event.payload.stage);
          setTurnPhase('processing');
          break;
        }

        case 'critique_generated': {
          const critique = event.payload.critique;
          setMessages((prev) => [
            ...prev,
            { id: `critique-${Date.now()}`, role: 'critique', text: critique },
          ]);
          break;
        }

        case 'retry_recording': {
          setErrorBanner(event.payload.message);
          setTurnPhase('recording_ready');
          break;
        }

        case 'session_complete': {
          setSessionStatus('complete');
          setCompletedTurns(event.payload.turns);
          setTurnPhase('idle');
          break;
        }

        case 'error': {
          setErrorBanner(event.payload.message);
          setTurnPhase('idle');
          break;
        }
      }
    },
    [enqueueAudioChunk],
  );

  // -------------------------------------------------------------------------
  // Start session
  // -------------------------------------------------------------------------
  const startConversation = async () => {
    if (!scenario) return;
    setErrorBanner('');
    try {
      const res = await createSession({ scenario, max_turns: 4 });
      setSessionId(res.session_id);
      setMaxTurns(4);
      setStep(2);

      // Open websocket
      const ws = connectWs(res.session_id, handleWsEvent);
      wsRef.current = ws;

      // Request first turn once socket is ready
      ws.onopen = async () => {
        setTurnPhase('requesting_prompt');
        setIsTyping(true);
        try {
          await requestNextTurn(res.session_id);
        } catch (err) {
          setErrorBanner(err instanceof Error ? err.message : 'Failed to start first turn');
          setIsTyping(false);
          setTurnPhase('idle');
        }
      };
    } catch (err) {
      setErrorBanner(err instanceof Error ? err.message : 'Failed to create session');
    }
  };

  // -------------------------------------------------------------------------
  // Request next turn
  // -------------------------------------------------------------------------
  const handleNextTurn = async () => {
    if (!sessionId) return;
    setErrorBanner('');
    setTurnPhase('requesting_prompt');
    setIsTyping(true);
    try {
      await requestNextTurn(sessionId);
    } catch (err) {
      setErrorBanner(err instanceof Error ? err.message : 'Failed to request next turn');
      setIsTyping(false);
      setTurnPhase('idle');
    }
  };

  // -------------------------------------------------------------------------
  // Recording
  // -------------------------------------------------------------------------
  const acquireMedia = async () => {
    if (mediaStreamRef.current) return mediaStreamRef.current;
    const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
    mediaStreamRef.current = stream;
    setHasMediaStream(true);
    if (previewRef.current) previewRef.current.srcObject = stream;
    return stream;
  };

  const startRecording = async () => {
    try {
      setErrorBanner('');
      const stream = await acquireMedia();

      // Full-turn recorders
      fullVideoChunksRef.current = [];
      fullAudioChunksRef.current = [];

      const fullVideoRec = new MediaRecorder(stream);
      const fullAudioRec = new MediaRecorder(new MediaStream(stream.getAudioTracks()));
      fullVideoRec.ondataavailable = (e) => { if (e.data.size > 0) fullVideoChunksRef.current.push(e.data); };
      fullAudioRec.ondataavailable = (e) => { if (e.data.size > 0) fullAudioChunksRef.current.push(e.data); };
      videoRecorderRef.current = fullVideoRec;
      audioRecorderRef.current = fullAudioRec;

      fullVideoRec.start();
      fullAudioRec.start();

      recordStartMsRef.current = Math.round(window.performance.now());
      chunkIndexRef.current = 0;
      setRecordTime(0);
      setTurnPhase('recording');

      // Timer display
      timerRef.current = setInterval(() => {
        setRecordTime((prev) => {
          const next = prev + 1;
          if (next >= maxSeconds) stopRecording();
          return next;
        });
      }, 1000);

      // Start first chunk recorder
      startChunkRecorder(stream);

      // Schedule chunk boundaries
      chunkTimerRef.current = setInterval(() => {
        rotateChunkRecorder(stream);
      }, CHUNK_DURATION_MS);
    } catch {
      setErrorBanner('Camera or microphone access was blocked. Allow access and try again.');
    }
  };

  const startChunkRecorder = (stream: MediaStream) => {
    videoChunksRef.current = [];
    audioChunksRef.current = [];

    const vRec = new MediaRecorder(stream);
    const aRec = new MediaRecorder(new MediaStream(stream.getAudioTracks()));
    vRec.ondataavailable = (e) => { if (e.data.size > 0) videoChunksRef.current.push(e.data); };
    aRec.ondataavailable = (e) => { if (e.data.size > 0) audioChunksRef.current.push(e.data); };

    chunkVideoRecorderRef.current = vRec;
    chunkAudioRecorderRef.current = aRec;
    vRec.start();
    aRec.start();
  };

  const rotateChunkRecorder = (stream: MediaStream) => {
    const idx = chunkIndexRef.current;
    const startMs = idx * CHUNK_DURATION_MS;
    const endMs = startMs + CHUNK_DURATION_MS;

    // Stop current chunk recorders and capture their data
    const vRec = chunkVideoRecorderRef.current;
    const aRec = chunkAudioRecorderRef.current;

    if (vRec && vRec.state === 'recording') vRec.stop();
    if (aRec && aRec.state === 'recording') aRec.stop();

    const capturedVideo = [...videoChunksRef.current];
    const capturedAudio = [...audioChunksRef.current];

    // Upload the completed chunk in background
    if (sessionId && capturedVideo.length > 0 && capturedAudio.length > 0) {
      const videoBlob = new Blob(capturedVideo, { type: 'video/webm' });
      const audioBlob = new Blob(capturedAudio, { type: 'audio/webm' });
      uploadChunk(sessionId, turnIndex, {
        chunkIndex: idx,
        startMs,
        endMs,
        videoBlob,
        audioBlob,
        mediapipeMetrics: {},
      }).catch(() => {
        // chunk upload failures are non-fatal; backend validation catches gaps
      });
    }

    chunkIndexRef.current = idx + 1;
    startChunkRecorder(stream);
  };

  const stopRecording = async () => {
    if (turnPhase !== 'recording') return;
    setTurnPhase('uploading');

    // Stop timers
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; }
    if (chunkTimerRef.current) { clearInterval(chunkTimerRef.current); chunkTimerRef.current = null; }

    // Finalize the last partial chunk
    const lastIdx = chunkIndexRef.current;
    const lastStartMs = lastIdx * CHUNK_DURATION_MS;
    const elapsed = Math.round(window.performance.now() - recordStartMsRef.current);
    const lastEndMs = Math.max(lastStartMs + 1, elapsed);

    // Stop chunk recorders
    const cvr = chunkVideoRecorderRef.current;
    const car = chunkAudioRecorderRef.current;
    if (cvr && cvr.state === 'recording') cvr.stop();
    if (car && car.state === 'recording') car.stop();

    // Stop full recorders
    const fvr = videoRecorderRef.current;
    const far = audioRecorderRef.current;
    if (fvr && fvr.state === 'recording') fvr.stop();
    if (far && far.state === 'recording') far.stop();

    // Wait a tick for ondataavailable to fire
    await new Promise((r) => setTimeout(r, 200));

    if (!sessionId) return;

    // Upload final partial chunk
    if (videoChunksRef.current.length > 0 && audioChunksRef.current.length > 0) {
      const videoBlob = new Blob(videoChunksRef.current, { type: 'video/webm' });
      const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
      try {
        await uploadChunk(sessionId, turnIndex, {
          chunkIndex: lastIdx,
          startMs: lastStartMs,
          endMs: lastEndMs,
          videoBlob,
          audioBlob,
          mediapipeMetrics: {},
        });
      } catch {
        // non-fatal
      }
    }

    // Transcribe full-turn audio
    const fullAudioBlob = new Blob(fullAudioChunksRef.current, { type: 'audio/webm' });
    try {
      const { transcript } = await transcribeTurn(sessionId, turnIndex, fullAudioBlob);
      setMessages((prev) => [
        ...prev,
        { id: `user-${Date.now()}`, role: 'user', text: transcript || '(no speech detected)' },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { id: `user-${Date.now()}`, role: 'user', text: '(transcription failed)' },
      ]);
    }

    // Complete the turn (triggers critique pipeline)
    setTurnPhase('processing');
    setProcessingStage('Analyzing your response...');
    try {
      await completeTurn(sessionId, turnIndex);
      setTurnPhase('turn_done');

      // Refresh session state for turn progression
      try {
        const state = await getSession(sessionId);
        setTurnIndex(state.turn_index);
        setSessionStatus(state.status);
        if (state.status === 'complete') {
          setCompletedTurns(
            state.turns.map((t) => ({
              turn_index: t.turn_index,
              prompt: t.prompt_text,
              critique: t.critique ?? null,
            })),
          );
        }
      } catch {
        // websocket events are primary source of truth
      }
    } catch (err) {
      setErrorBanner(err instanceof Error ? err.message : 'Turn completion failed');
      setTurnPhase('recording_ready');
    }
  };

  // -------------------------------------------------------------------------
  // End session
  // -------------------------------------------------------------------------
  const handleEndSession = async () => {
    if (!sessionId) return;
    try {
      const result = await endSession(sessionId);
      setSessionStatus('complete');
      setCompletedTurns(result.turns);
      setTurnPhase('idle');
    } catch (err) {
      setErrorBanner(err instanceof Error ? err.message : 'Failed to end session');
    }
  };

  // -------------------------------------------------------------------------
  // Hydrate on mount/reconnect if sessionId is in URL later (future-proof)
  // -------------------------------------------------------------------------

  // -------------------------------------------------------------------------
  // Render helpers
  // -------------------------------------------------------------------------
  const formatTime = (seconds: number) => {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}:${s.toString().padStart(2, '0')}`;
  };

  const canRecord = turnPhase === 'recording_ready';
  const isRecording = turnPhase === 'recording';
  const isBusy =
    turnPhase === 'requesting_prompt' ||
    turnPhase === 'uploading' ||
    turnPhase === 'processing';

  // -------------------------------------------------------------------------
  // RENDER
  // -------------------------------------------------------------------------
  return (
    <div className="flex min-h-[calc(100vh-64px)] flex-col">
      {/* Header */}
      <div className="mb-4 shrink-0">
        <h1 className="font-['Playfair_Display'] text-2xl font-semibold text-slate-900">
          Conversation Practice
        </h1>
        <p className="text-slate-500 text-sm mt-1">
          Simulate real conversations and get live feedback
        </p>
      </div>

      <AnimatePresence mode="wait">
        {/* ---- STEP 1: Setup ---- */}
        {step === 1 && (
          <motion.div
            key="step1"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            className="flex-1"
          >
            <h2 className="text-sm font-medium text-slate-700 mb-4">
              Select a conversation mode
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
              {(Object.keys(scenarioData) as Scenario[]).map((s) => (
                <button
                  key={s}
                  onClick={() => setScenario(s)}
                  className={`bg-white rounded-2xl border-2 p-6 text-left transition-all duration-200 hover:shadow-md ${
                    scenario === s
                      ? `${scenarioData[s].color} shadow-md`
                      : 'border-cream-300'
                  }`}
                >
                  <h3 className="font-semibold text-slate-900 mb-1">
                    {scenarioData[s].label}
                  </h3>
                  <p className="text-sm text-slate-500">
                    {scenarioData[s].description}
                  </p>
                </button>
              ))}
            </div>

            {errorBanner && (
              <p className="mb-4 rounded-2xl bg-red-50 px-4 py-3 text-sm text-red-600">
                {errorBanner}
              </p>
            )}

            <button
              disabled={!scenario}
              onClick={startConversation}
              className={`px-6 py-3 rounded-full font-medium text-sm transition-all ${
                scenario
                  ? 'bg-navy-500 text-white hover:bg-navy-600 shadow-md'
                  : 'bg-cream-200 text-slate-400 cursor-not-allowed'
              }`}
            >
              Begin conversation →
            </button>
          </motion.div>
        )}

        {/* ---- STEP 2: Active conversation ---- */}
        {step === 2 && sessionStatus !== 'complete' && (
          <motion.div
            key="step2"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="flex min-h-0 flex-1 gap-4 overflow-hidden"
          >
            {/* Chat Thread — 65% */}
            <div className="flex-[65] flex flex-col bg-white rounded-2xl border border-cream-300 overflow-hidden shadow-sm">
              {/* Chat mode header */}
              <div className="px-5 py-3 border-b border-cream-200 flex items-center justify-between">
                <span className="text-sm font-medium text-slate-700">
                  {scenario && scenarioData[scenario].label}
                  <span className="ml-2 text-xs text-slate-400">
                    Turn {turnIndex + 1} / {maxTurns}
                  </span>
                </span>
                <button
                  onClick={handleEndSession}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-red-50 text-red-500 text-xs font-medium hover:bg-red-100 transition-colors"
                >
                  <Power size={12} /> End session
                </button>
              </div>

              {/* Messages */}
              <div className="flex-1 overflow-y-auto p-5 space-y-4">
                {messages.map((msg) => (
                  <div
                    key={msg.id}
                    className={`flex ${
                      msg.role === 'user' ? 'justify-end' : 'justify-start'
                    }`}
                  >
                    <div
                      className={`max-w-[75%] px-4 py-3 rounded-2xl text-sm leading-relaxed ${
                        msg.role === 'user'
                          ? 'bg-navy-500 text-white rounded-br-md'
                          : msg.role === 'critique'
                            ? 'bg-amber-50 border border-amber-200 text-slate-800 rounded-bl-md'
                            : 'bg-cream-50 border border-cream-300 text-slate-800 rounded-bl-md'
                      }`}
                    >
                      {msg.role === 'critique' && (
                        <span className="block text-xs font-medium text-amber-600 mb-1">
                          Coach Feedback
                        </span>
                      )}
                      {msg.text}
                    </div>
                  </div>
                ))}
                {isTyping && (
                  <div className="flex justify-start">
                    <div className="bg-cream-50 border border-cream-300 rounded-2xl rounded-bl-md px-4 py-3">
                      <div className="flex gap-1.5">
                        <span className="w-2 h-2 rounded-full bg-slate-400 animate-bounce" />
                        <span className="w-2 h-2 rounded-full bg-slate-400 animate-bounce" style={{ animationDelay: '0.15s' }} />
                        <span className="w-2 h-2 rounded-full bg-slate-400 animate-bounce" style={{ animationDelay: '0.3s' }} />
                      </div>
                    </div>
                  </div>
                )}
                <div ref={chatEndRef} />
              </div>

              {/* Recording controls (replaces text input) */}
              <div className="px-5 py-3 border-t border-cream-200">
                {errorBanner && (
                  <p className="mb-3 rounded-xl bg-red-50 px-4 py-2.5 text-sm text-red-600">
                    {errorBanner}
                  </p>
                )}

                <div className="flex items-center gap-3">
                  {/* Record / Stop button */}
                  <button
                    onClick={isRecording ? stopRecording : startRecording}
                    disabled={!canRecord && !isRecording}
                    className={`w-10 h-10 rounded-full flex items-center justify-center transition-colors ${
                      isRecording
                        ? 'bg-red-500 text-white animate-pulse'
                        : canRecord
                          ? 'bg-navy-500 text-white hover:bg-navy-600'
                          : 'bg-cream-100 text-slate-400 cursor-not-allowed'
                    }`}
                  >
                    {isRecording ? <Square size={16} /> : <Mic size={18} />}
                  </button>

                  {/* Status text */}
                  <div className="flex-1 text-sm text-slate-500">
                    {isRecording && (
                      <span className="text-red-500 font-medium">
                        Recording {formatTime(recordTime)} / {formatTime(maxSeconds)}
                      </span>
                    )}
                    {canRecord && !isRecording && 'Click the mic to record your response'}
                    {turnPhase === 'requesting_prompt' && 'Generating prompt...'}
                    {(turnPhase === 'prompt_streaming' || turnPhase === 'playing_prompt_tts') &&
                      'Listen to the prompt...'}
                    {turnPhase === 'uploading' && 'Uploading recording...'}
                    {turnPhase === 'processing' && (processingStage || 'Processing...')}
                    {turnPhase === 'playing_critique_tts' && 'Playing coach feedback...'}
                    {turnPhase === 'turn_done' && turnIndex < maxTurns && 'Turn complete!'}
                    {turnPhase === 'turn_done' && turnIndex >= maxTurns && 'All turns complete!'}
                  </div>

                  {/* Next turn / spinner */}
                  {isBusy && (
                    <Loader2 size={18} className="text-slate-400 animate-spin" />
                  )}
                  {turnPhase === 'turn_done' && turnIndex < maxTurns && (
                    <button
                      onClick={handleNextTurn}
                      className="px-4 py-2 rounded-full bg-navy-500 text-white text-sm font-semibold hover:bg-navy-600 transition-colors"
                    >
                      Next prompt →
                    </button>
                  )}
                  {turnPhase === 'turn_done' && turnIndex >= maxTurns && (
                    <button
                      onClick={handleEndSession}
                      className="px-4 py-2 rounded-full bg-navy-500 text-white text-sm font-semibold hover:bg-navy-600 transition-colors"
                    >
                      View summary
                    </button>
                  )}
                </div>
              </div>
            </div>

            {/* Live Analysis Sidebar — 35% */}
            <div className="flex-[35] min-h-0 flex flex-col gap-4 overflow-y-auto pr-1">
              {/* Webcam preview */}
              <div className="bg-white rounded-2xl border border-cream-300 p-4 shadow-sm">
                <div className="flex items-center gap-2 mb-3">
                  <Video size={14} className="text-slate-500" />
                  <span className="text-sm font-medium text-slate-700">
                    Webcam preview
                  </span>
                </div>
                <video
                  ref={previewRef}
                  autoPlay
                  muted
                  playsInline
                  className="aspect-[4/3] w-full rounded-xl bg-slate-100 object-cover"
                />
                {!hasMediaStream && (
                  <button
                    onClick={acquireMedia}
                    className="mt-2 w-full rounded-lg bg-cream-50 border border-cream-300 py-2 text-xs text-slate-500 hover:bg-cream-100 transition-colors"
                  >
                    Enable camera
                  </button>
                )}
              </div>

              {/* Turn Status / Processing */}
              <div className="bg-white rounded-2xl border border-cream-300 p-5 shadow-sm">
                <h3 className="text-sm font-medium text-slate-700 mb-4">
                  Turn Status
                </h3>
                <div className="space-y-3">
                  {[
                    { label: 'Prompt', done: turnPhase !== 'idle' && turnPhase !== 'requesting_prompt' },
                    { label: 'Recording', done: turnPhase === 'uploading' || turnPhase === 'processing' || turnPhase === 'playing_critique_tts' || turnPhase === 'turn_done' },
                    { label: 'Analysis', done: turnPhase === 'playing_critique_tts' || turnPhase === 'turn_done' },
                    { label: 'Feedback', done: turnPhase === 'turn_done' },
                  ].map(({ label, done }) => (
                    <div key={label} className="flex items-center gap-2">
                      <div
                        className={`w-2 h-2 rounded-full ${
                          done ? 'bg-emerald-500' : 'bg-cream-300'
                        }`}
                      />
                      <span
                        className={`text-sm ${
                          done ? 'text-slate-800 font-medium' : 'text-slate-400'
                        }`}
                      >
                        {label}
                      </span>
                    </div>
                  ))}
                </div>

                {turnPhase === 'processing' && processingStage && (
                  <div className="mt-4 pt-3 border-t border-cream-200">
                    <div className="flex items-center gap-2">
                      <Loader2 size={12} className="text-navy-500 animate-spin" />
                      <span className="text-xs text-slate-500">{processingStage}</span>
                    </div>
                  </div>
                )}
              </div>

              {/* Session progress */}
              <div className="bg-white rounded-2xl border border-cream-300 p-5 shadow-sm">
                <h3 className="text-sm font-medium text-slate-700 mb-3">
                  Session Progress
                </h3>
                <div className="flex gap-1.5">
                  {Array.from({ length: maxTurns }).map((_, i) => (
                    <div
                      key={i}
                      className={`flex-1 h-1.5 rounded-full ${
                        i < turnIndex
                          ? 'bg-navy-500'
                          : i === turnIndex && turnPhase !== 'idle'
                            ? 'bg-navy-300'
                            : 'bg-cream-200'
                      }`}
                    />
                  ))}
                </div>
                <p className="mt-2 text-xs text-slate-400">
                  {turnIndex} of {maxTurns} turns completed
                </p>
              </div>
            </div>
          </motion.div>
        )}

        {/* ---- Session Complete ---- */}
        {step === 2 && sessionStatus === 'complete' && (
          <motion.div
            key="complete"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex-1 overflow-y-auto"
          >
            <div className="max-w-3xl mx-auto space-y-6">
              <div className="bg-white rounded-2xl border border-cream-300 p-6 shadow-sm text-center">
                <h2 className="font-['Playfair_Display'] text-xl font-semibold text-slate-900 mb-2">
                  Session Complete
                </h2>
                <p className="text-sm text-slate-500">
                  {completedTurns.length} turn{completedTurns.length !== 1 ? 's' : ''} completed
                  {scenario && ` · ${scenarioData[scenario].label}`}
                </p>
              </div>

              {completedTurns.map((turn) => (
                <div
                  key={turn.turn_index}
                  className="bg-white rounded-2xl border border-cream-300 p-5 shadow-sm space-y-3"
                >
                  <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">
                    Turn {turn.turn_index + 1}
                  </span>
                  <div className="bg-cream-50 border border-cream-300 rounded-xl px-4 py-3 text-sm text-slate-800">
                    {turn.prompt}
                  </div>
                  {turn.critique && (
                    <div className="bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 text-sm text-slate-800">
                      <span className="block text-xs font-medium text-amber-600 mb-1">
                        Coach Feedback
                      </span>
                      {turn.critique}
                    </div>
                  )}
                </div>
              ))}

              <div className="flex justify-center gap-3 pb-8">
                <button
                  onClick={() => {
                    setStep(1);
                    setSessionId(null);
                    setMessages([]);
                    setCompletedTurns([]);
                    setSessionStatus('active');
                    setTurnPhase('idle');
                    setTurnIndex(0);
                    setScenario(null);
                    setErrorBanner('');
                    wsRef.current?.close();
                  }}
                  className="px-6 py-3 rounded-full bg-navy-500 text-white text-sm font-semibold hover:bg-navy-600 shadow-sm transition-colors"
                >
                  Start new session
                </button>
                <button
                  onClick={() => router.push('/replays')}
                  className="px-6 py-3 rounded-full bg-cream-100 text-slate-600 text-sm font-medium hover:bg-cream-200 transition-colors"
                >
                  View replays
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
