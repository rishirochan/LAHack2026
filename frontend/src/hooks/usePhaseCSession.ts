'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import { useSessionsContext } from '@/context/SessionsContext';
import {
  completeSession,
  connectWs,
  createSession,
  type PhaseCScorecard,
  type PhaseCWsEvent,
  startRecording as startRecordingRequest,
  transcribeAudio,
  uploadChunk,
} from '@/lib/phase-c-api';

const CHUNK_DURATION_MS = 5_000;
const DEFAULT_MAX_SECONDS = 45;
const DEFAULT_WAVEFORM_BARS = Array(32).fill(6);
const MEDIA_RECORDER_TIMESLICE_MS = 1_000;

type PhaseCStatus =
  | 'setup'
  | 'ready'
  | 'recording'
  | 'uploading'
  | 'processing'
  | 'results'
  | 'error';

type ChunkUploadState = {
  chunkIndex: number;
  status: 'uploading' | 'uploaded' | 'failed';
};

type ActiveChunkRecorder = {
  index: number;
  startMs: number;
  videoRecorder: MediaRecorder;
  audioRecorder: MediaRecorder;
  videoChunks: Blob[];
  audioChunks: Blob[];
};

export function usePhaseCSession() {
  const { refetch: refetchSessions } = useSessionsContext();
  const [status, setStatus] = useState<PhaseCStatus>('setup');
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [scorecard, setScorecard] = useState<PhaseCScorecard | null>(null);
  const [writtenSummary, setWrittenSummary] = useState('');
  const [processingStage, setProcessingStage] = useState('');
  const [errorMessage, setErrorMessage] = useState('');
  const [recordSeconds, setRecordSeconds] = useState(0);
  const [maxSeconds, setMaxSeconds] = useState(DEFAULT_MAX_SECONDS);
  const [waveformBars, setWaveformBars] = useState<number[]>(DEFAULT_WAVEFORM_BARS);
  const [chunkUploads, setChunkUploads] = useState<ChunkUploadState[]>([]);
  const [recordedVideoUrl, setRecordedVideoUrl] = useState<string | null>(null);
  const [transcriptPreview, setTranscriptPreview] = useState('');

  const previewRef = useRef<HTMLVideoElement | null>(null);
  const sessionIdRef = useRef<string | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const websocketRef = useRef<WebSocket | null>(null);
  const isClosingSocketRef = useRef(false);
  const recordStartMsRef = useRef(0);
  const recordTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const chunkTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const activeChunkRef = useRef<ActiveChunkRecorder | null>(null);
  const fullVideoRecorderRef = useRef<MediaRecorder | null>(null);
  const fullAudioRecorderRef = useRef<MediaRecorder | null>(null);
  const fullVideoChunksRef = useRef<Blob[]>([]);
  const fullAudioChunksRef = useRef<Blob[]>([]);
  const recentSessionRefreshTimeoutsRef = useRef<number[]>([]);
  const stopInFlightRef = useRef(false);
  const stopRecordingRef = useRef<(() => Promise<void>) | null>(null);
  const analyserContextRef = useRef<AudioContext | null>(null);
  const analyserNodeRef = useRef<AnalyserNode | null>(null);
  const analyserSourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const waveformFrameRef = useRef<number | null>(null);

  const closeWebsocket = useCallback(() => {
    isClosingSocketRef.current = true;
    websocketRef.current?.close();
    websocketRef.current = null;
  }, []);

  const attachPreviewStream = useCallback((stream: MediaStream | null) => {
    const preview = previewRef.current;
    if (!preview) {
      return;
    }
    preview.srcObject = stream;
  }, []);

  const clearRecordedVideoUrl = useCallback(() => {
    setRecordedVideoUrl((currentUrl) => {
      if (currentUrl) {
        URL.revokeObjectURL(currentUrl);
      }
      return null;
    });
  }, []);

  const clearPendingSessionRefreshes = useCallback(() => {
    recentSessionRefreshTimeoutsRef.current.forEach((timeoutId) => {
      window.clearTimeout(timeoutId);
    });
    recentSessionRefreshTimeoutsRef.current = [];
  }, []);

  const refreshRecentSessionsAfterCompletion = useCallback(() => {
    clearPendingSessionRefreshes();
    void refetchSessions();
    recentSessionRefreshTimeoutsRef.current = [700, 2000].map((delayMs) =>
      window.setTimeout(() => {
        void refetchSessions();
      }, delayMs),
    );
  }, [clearPendingSessionRefreshes, refetchSessions]);

  const stopWaveformLoop = useCallback(() => {
    if (waveformFrameRef.current !== null) {
      cancelAnimationFrame(waveformFrameRef.current);
      waveformFrameRef.current = null;
    }
    analyserSourceRef.current?.disconnect();
    analyserSourceRef.current = null;
    analyserNodeRef.current = null;
    if (analyserContextRef.current) {
      void analyserContextRef.current.close();
      analyserContextRef.current = null;
    }
    setWaveformBars(DEFAULT_WAVEFORM_BARS);
  }, []);

  const stopMediaTracks = useCallback(() => {
    mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
    mediaStreamRef.current = null;
    attachPreviewStream(null);
    stopWaveformLoop();
  }, [attachPreviewStream, stopWaveformLoop]);

  const stopTimers = useCallback(() => {
    if (recordTimerRef.current) {
      clearInterval(recordTimerRef.current);
      recordTimerRef.current = null;
    }
    if (chunkTimerRef.current) {
      clearInterval(chunkTimerRef.current);
      chunkTimerRef.current = null;
    }
  }, []);

  const resetPresentationState = useCallback(() => {
    clearPendingSessionRefreshes();
    stopTimers();
    stopInFlightRef.current = false;
    activeChunkRef.current = null;
    fullVideoRecorderRef.current = null;
    fullAudioRecorderRef.current = null;
    fullVideoChunksRef.current = [];
    fullAudioChunksRef.current = [];
    setProcessingStage('');
    setErrorMessage('');
    setRecordSeconds(0);
    setChunkUploads([]);
    setTranscriptPreview('');
    setScorecard(null);
    setWrittenSummary('');
  }, [clearPendingSessionRefreshes, stopTimers]);

  const resetAll = useCallback(() => {
    clearPendingSessionRefreshes();
    stopTimers();
    closeWebsocket();
    stopMediaTracks();
    activeChunkRef.current = null;
    fullVideoRecorderRef.current = null;
    fullAudioRecorderRef.current = null;
    fullVideoChunksRef.current = [];
    fullAudioChunksRef.current = [];
    stopInFlightRef.current = false;
    sessionIdRef.current = null;
    setSessionId(null);
    setStatus('setup');
    setMaxSeconds(DEFAULT_MAX_SECONDS);
    clearRecordedVideoUrl();
    setWaveformBars(DEFAULT_WAVEFORM_BARS);
    setRecordSeconds(0);
    setChunkUploads([]);
    setScorecard(null);
    setWrittenSummary('');
    setProcessingStage('');
    setErrorMessage('');
    setTranscriptPreview('');
  }, [clearPendingSessionRefreshes, clearRecordedVideoUrl, closeWebsocket, stopMediaTracks, stopTimers]);

  useEffect(() => {
    return () => {
      resetAll();
    };
  }, [resetAll]);

  useEffect(() => {
    attachPreviewStream(mediaStreamRef.current);
  }, [attachPreviewStream, recordedVideoUrl]);

  const connectWaveform = useCallback((stream: MediaStream) => {
    stopWaveformLoop();
    const hasAudioTrack = stream.getAudioTracks().length > 0;
    if (!hasAudioTrack) {
      setWaveformBars(DEFAULT_WAVEFORM_BARS);
      return;
    }

    const audioContext = new AudioContext();
    const analyser = audioContext.createAnalyser();
    analyser.fftSize = 128;
    analyser.smoothingTimeConstant = 0.8;
    const source = audioContext.createMediaStreamSource(new MediaStream(stream.getAudioTracks()));
    source.connect(analyser);

    analyserContextRef.current = audioContext;
    analyserNodeRef.current = analyser;
    analyserSourceRef.current = source;

    const data = new Uint8Array(analyser.frequencyBinCount);
    const tick = () => {
      analyser.getByteFrequencyData(data);
      const bars = Array.from({ length: 32 }, (_, index) => {
        const sample = data[index] ?? 0;
        return Math.max(6, Math.round(sample / 6));
      });
      setWaveformBars(bars);
      waveformFrameRef.current = requestAnimationFrame(tick);
    };

    waveformFrameRef.current = requestAnimationFrame(tick);
  }, [stopWaveformLoop]);

  const acquireMedia = useCallback(async () => {
    if (mediaStreamRef.current) {
      attachPreviewStream(mediaStreamRef.current);
      return mediaStreamRef.current;
    }

    const stream = await navigator.mediaDevices.getUserMedia({
      video: true,
      audio: true,
    });
    mediaStreamRef.current = stream;
    attachPreviewStream(stream);
    connectWaveform(stream);
    return stream;
  }, [attachPreviewStream, connectWaveform]);

  const waitForSocketOpen = useCallback((socket: WebSocket) => {
    if (socket.readyState === WebSocket.OPEN) {
      return Promise.resolve();
    }

    return new Promise<void>((resolve, reject) => {
      const handleOpen = () => {
        socket.removeEventListener('error', handleError);
        resolve();
      };
      const handleError = () => {
        socket.removeEventListener('open', handleOpen);
        reject(new Error('Realtime connection failed.'));
      };

      socket.addEventListener('open', handleOpen, { once: true });
      socket.addEventListener('error', handleError, { once: true });
    });
  }, []);

  const createRecorder = useCallback((stream: MediaStream, mimeType: string | undefined) => {
    if (mimeType) {
      return new MediaRecorder(stream, { mimeType });
    }
    return new MediaRecorder(stream);
  }, []);

  const selectVideoMimeType = useCallback(() => {
    const candidates = [
      'video/webm;codecs=vp9,opus',
      'video/webm;codecs=vp8,opus',
      'video/webm',
    ];

    return candidates.find((candidate) => MediaRecorder.isTypeSupported(candidate));
  }, []);

  const selectAudioMimeType = useCallback(() => {
    const candidates = ['audio/webm;codecs=opus', 'audio/webm'];
    return candidates.find((candidate) => MediaRecorder.isTypeSupported(candidate));
  }, []);

  const waitForRecorderStop = useCallback((recorder: MediaRecorder | null) => {
    if (!recorder || recorder.state === 'inactive') {
      return Promise.resolve();
    }

    return new Promise<void>((resolve) => {
      try {
        recorder.requestData();
      } catch {
        // Ignore requestData failures during shutdown.
      }
      recorder.addEventListener('stop', () => resolve(), { once: true });
      recorder.stop();
    });
  }, []);

  const updateChunkUploadState = useCallback((chunkIndex: number, nextStatus: ChunkUploadState['status']) => {
    setChunkUploads((current) => {
      const withoutCurrent = current.filter((chunk) => chunk.chunkIndex !== chunkIndex);
      return [...withoutCurrent, { chunkIndex, status: nextStatus }].sort(
        (left, right) => left.chunkIndex - right.chunkIndex,
      );
    });
  }, []);

  const startChunkRecorder = useCallback(async (stream: MediaStream, index: number, startMs: number) => {
    const videoChunks: Blob[] = [];
    const audioChunks: Blob[] = [];
    const videoRecorder = createRecorder(stream, selectVideoMimeType());
    const audioRecorder = createRecorder(new MediaStream(stream.getAudioTracks()), selectAudioMimeType());

    videoRecorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        videoChunks.push(event.data);
      }
    };
    audioRecorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        audioChunks.push(event.data);
      }
    };

    videoRecorder.start(MEDIA_RECORDER_TIMESLICE_MS);
    audioRecorder.start(MEDIA_RECORDER_TIMESLICE_MS);

    activeChunkRef.current = {
      index,
      startMs,
      videoRecorder,
      audioRecorder,
      videoChunks,
      audioChunks,
    };
  }, [createRecorder, selectAudioMimeType, selectVideoMimeType]);

  const uploadCompletedChunk = useCallback(async (
    chunk: ActiveChunkRecorder,
    endMs: number,
    currentSessionId: string,
  ) => {
    await Promise.all([
      waitForRecorderStop(chunk.videoRecorder),
      waitForRecorderStop(chunk.audioRecorder),
    ]);

    if (!chunk.videoChunks.length || !chunk.audioChunks.length) {
      updateChunkUploadState(chunk.index, 'failed');
      return;
    }

    updateChunkUploadState(chunk.index, 'uploading');
    try {
      await uploadChunk(currentSessionId, {
        chunkIndex: chunk.index,
        startMs: chunk.startMs,
        endMs,
        videoBlob: new Blob(chunk.videoChunks, { type: 'video/webm' }),
        audioBlob: new Blob(chunk.audioChunks, { type: 'audio/webm' }),
        mediapipeMetrics: {},
      });
      updateChunkUploadState(chunk.index, 'uploaded');
    } catch {
      updateChunkUploadState(chunk.index, 'failed');
    }
  }, [updateChunkUploadState, waitForRecorderStop]);

  const startLocalRecording = useCallback(async (nextMaxSeconds: number) => {
    if (status === 'recording' || stopInFlightRef.current) {
      return;
    }

    const stream = await acquireMedia();
    clearRecordedVideoUrl();
    setErrorMessage('');
    setProcessingStage('');
    setTranscriptPreview('');
    setChunkUploads([]);
    setScorecard(null);
    setWrittenSummary('');
    setRecordSeconds(0);
    setMaxSeconds(nextMaxSeconds);

    fullVideoChunksRef.current = [];
    fullAudioChunksRef.current = [];

    const fullVideoRecorder = createRecorder(stream, selectVideoMimeType());
    const fullAudioRecorder = createRecorder(new MediaStream(stream.getAudioTracks()), selectAudioMimeType());
    fullVideoRecorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        fullVideoChunksRef.current.push(event.data);
      }
    };
    fullAudioRecorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        fullAudioChunksRef.current.push(event.data);
      }
    };

    fullVideoRecorderRef.current = fullVideoRecorder;
    fullAudioRecorderRef.current = fullAudioRecorder;
    fullVideoRecorder.start(MEDIA_RECORDER_TIMESLICE_MS);
    fullAudioRecorder.start(MEDIA_RECORDER_TIMESLICE_MS);

    recordStartMsRef.current = Date.now();
    await startChunkRecorder(stream, 0, 0);
    setStatus('recording');

    recordTimerRef.current = setInterval(() => {
      setRecordSeconds((currentSeconds) => {
        const nextSeconds = currentSeconds + 1;
        if (nextSeconds >= nextMaxSeconds) {
          void stopRecordingRef.current?.();
        }
        return nextSeconds;
      });
    }, 1000);

    chunkTimerRef.current = setInterval(() => {
      const currentSessionId = sessionIdRef.current;
      const streamForNextChunk = mediaStreamRef.current;
      const currentChunk = activeChunkRef.current;

      if (!currentSessionId || !streamForNextChunk || !currentChunk || stopInFlightRef.current) {
        return;
      }

      const endMs = Math.max(currentChunk.startMs + 1, Date.now() - recordStartMsRef.current);
      void startChunkRecorder(streamForNextChunk, currentChunk.index + 1, endMs);
      void uploadCompletedChunk(currentChunk, endMs, currentSessionId);
    }, CHUNK_DURATION_MS);
  }, [
    acquireMedia,
    clearRecordedVideoUrl,
    createRecorder,
    selectAudioMimeType,
    selectVideoMimeType,
    startChunkRecorder,
    status,
    uploadCompletedChunk,
  ]);

  const handleWsEvent = useCallback((event: PhaseCWsEvent) => {
    switch (event.type) {
      case 'recording_ready':
        setMaxSeconds(event.payload.max_seconds);
        setStatus('ready');
        void startLocalRecording(event.payload.max_seconds);
        break;
      case 'processing_stage':
        setStatus('processing');
        setProcessingStage(String(event.payload.stage ?? 'Processing'));
        break;
      case 'session_result':
        setScorecard(event.payload.scorecard ?? null);
        setWrittenSummary(String(event.payload.written_summary ?? ''));
        setProcessingStage('');
        setStatus('results');
        refreshRecentSessionsAfterCompletion();
        break;
      case 'retry_recording':
        setErrorMessage(String(event.payload.message ?? 'Try recording again.'));
        setProcessingStage('');
        setStatus('ready');
        break;
      case 'error':
        setErrorMessage(String(event.payload.message ?? 'Something went wrong.'));
        setProcessingStage('');
        setStatus('error');
        break;
      default:
        break;
    }
  }, [refreshRecentSessionsAfterCompletion, startLocalRecording]);

  const connectWebsocket = useCallback((nextSessionId: string) => {
    closeWebsocket();
    isClosingSocketRef.current = false;
    const socket = connectWs(nextSessionId, handleWsEvent);
    socket.onerror = () => {
      if (isClosingSocketRef.current) {
        return;
      }
      setErrorMessage('Realtime connection failed. Refresh and try again.');
      setStatus('error');
    };
    websocketRef.current = socket;
    return socket;
  }, [closeWebsocket, handleWsEvent]);

  const startSession = useCallback(async () => {
    resetPresentationState();
    setStatus('ready');

    try {
      const session = await createSession();
      sessionIdRef.current = session.session_id;
      setSessionId(session.session_id);
      const socket = connectWebsocket(session.session_id);
      await acquireMedia();
      await waitForSocketOpen(socket);
      await startRecordingRequest(session.session_id);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Could not start the free speaking session.');
      setStatus('error');
    }
  }, [acquireMedia, connectWebsocket, resetPresentationState, waitForSocketOpen]);

  const stopRecording = useCallback(async () => {
    const currentSessionId = sessionIdRef.current;
    if (!currentSessionId || stopInFlightRef.current || status !== 'recording') {
      return;
    }

    stopInFlightRef.current = true;
    stopTimers();
    setStatus('uploading');
    setProcessingStage('Uploading final recording');

    try {
      const activeChunk = activeChunkRef.current;
      const recordingElapsedMs = Math.max(1, Date.now() - recordStartMsRef.current);

      if (activeChunk) {
        activeChunkRef.current = null;
        await uploadCompletedChunk(activeChunk, recordingElapsedMs, currentSessionId);
      }

      await Promise.all([
        waitForRecorderStop(fullVideoRecorderRef.current),
        waitForRecorderStop(fullAudioRecorderRef.current),
      ]);

      const fullVideoBlob = new Blob(fullVideoChunksRef.current, { type: 'video/webm' });
      const fullAudioBlob = new Blob(fullAudioChunksRef.current, { type: 'audio/webm' });

      if (fullVideoBlob.size > 0) {
        clearRecordedVideoUrl();
        setRecordedVideoUrl(URL.createObjectURL(fullVideoBlob));
      }

      if (fullAudioBlob.size === 0) {
        throw new Error('The recording ended before any audio was captured. Try again and wait a second before stopping.');
      }

      stopMediaTracks();

      setStatus('processing');
      setProcessingStage('Transcribing audio');

      const transcriptResult = await transcribeAudio(currentSessionId, fullAudioBlob);
      setTranscriptPreview(transcriptResult.transcript || '');
      await completeSession(currentSessionId);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Could not finish the recording.');
      setProcessingStage('');
      setStatus('error');
    } finally {
      stopInFlightRef.current = false;
    }
  }, [
    clearRecordedVideoUrl,
    status,
    stopMediaTracks,
    stopTimers,
    uploadCompletedChunk,
    waitForRecorderStop,
  ]);

  useEffect(() => {
    stopRecordingRef.current = stopRecording;
  }, [stopRecording]);

  const retryRecording = useCallback(async () => {
    const currentSessionId = sessionIdRef.current;
    if (!currentSessionId) {
      await startSession();
      return;
    }

    resetPresentationState();
    clearRecordedVideoUrl();
    try {
      await acquireMedia();
      const socket = connectWebsocket(currentSessionId);
      await waitForSocketOpen(socket);
      await startRecordingRequest(currentSessionId);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Could not restart the recording.');
      setStatus('error');
    }
  }, [acquireMedia, clearRecordedVideoUrl, connectWebsocket, resetPresentationState, startSession, waitForSocketOpen]);

  return {
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
    stopRecording,
    retryRecording,
    resetAll,
  };
}
