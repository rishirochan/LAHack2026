"use client";

import { useRef, useState } from "react";
import type {
  RoundResult,
  SessionSetup,
  SessionStatus,
  SessionSummary,
} from "../types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const WS_URL = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000";

type WebsocketEvent = {
  type: string;
  payload: Record<string, unknown>;
};

export function usePhaseASession() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [status, setStatus] = useState<SessionStatus>("setup");
  const [scenarioPrompt, setScenarioPrompt] = useState("");
  const [critique, setCritique] = useState("");
  const [processingStage, setProcessingStage] = useState("");
  const [roundResult, setRoundResult] = useState<RoundResult | null>(null);
  const [summary, setSummary] = useState<SessionSummary | null>(null);
  const [errorMessage, setErrorMessage] = useState("");
  const websocketRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const nextAudioStartRef = useRef(0);

  async function startSession(setup: SessionSetup) {
    setErrorMessage("");
    setProcessingStage("");
    setSummary(null);
    setRoundResult(null);
    setCritique("");
    setScenarioPrompt("");
    setStatus("scenario");

    const response = await fetch(`${API_URL}/api/phase-a/sessions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        theme: setup.theme,
        target_emotion: setup.targetEmotion,
        difficulty: setup.difficulty,
      }),
    });

    if (!response.ok) {
      throw new Error("Could not start the emotion drill session.");
    }

    const data = (await response.json()) as { session_id: string };
    setSessionId(data.session_id);
    connectWebsocket(data.session_id);
  }

  async function uploadRecording(videoBlob: Blob, audioBlob: Blob, durationSeconds: number) {
    if (!sessionId) {
      throw new Error("No active session.");
    }

    setStatus("processing");
    setProcessingStage("Uploading recording");
    setErrorMessage("");

    const formData = new FormData();
    formData.append("video_file", videoBlob, "phase-a-video.webm");
    formData.append("audio_file", audioBlob, "phase-a-audio.webm");
    formData.append("duration_seconds", String(durationSeconds));

    const response = await fetch(`${API_URL}/api/phase-a/sessions/${sessionId}/recording`, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      throw new Error("Could not upload the recording.");
    }

    const data = (await response.json()) as { status: string };
    if (data.status === "retry") {
      setStatus("recording");
    }
  }

  async function chooseContinue(continueSession: boolean) {
    if (!sessionId) {
      return;
    }

    if (continueSession) {
      setStatus("scenario");
      setCritique("");
      setRoundResult(null);
      setProcessingStage("");
    } else {
      setStatus("summary");
    }

    const response = await fetch(`${API_URL}/api/phase-a/sessions/${sessionId}/continue`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ continue_session: continueSession }),
    });

    if (!response.ok) {
      throw new Error("Could not send session decision.");
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
      setStatus("error");
      setErrorMessage("Realtime connection failed. Refresh and try again.");
    };
  }

  function handleEvent(event: WebsocketEvent) {
    switch (event.type) {
      case "scenario":
        setScenarioPrompt(String(event.payload.scenario_prompt ?? ""));
        setStatus("scenario");
        break;
      case "recording_ready":
        setStatus("recording");
        break;
      case "processing_stage":
        setStatus("processing");
        setProcessingStage(String(event.payload.stage ?? ""));
        break;
      case "tts_start":
        resetAudioClock();
        if (event.payload.audio_type === "critique") {
          setCritique(String(event.payload.text ?? ""));
          setStatus("critique");
        }
        break;
      case "audio_chunk":
        void playAudioChunk(String(event.payload.chunk ?? ""));
        break;
      case "round_result":
        setRoundResult(event.payload as RoundResult);
        setCritique(String(event.payload.critique ?? ""));
        break;
      case "retry_recording":
        setStatus("recording");
        setErrorMessage(String(event.payload.message ?? "Try recording again."));
        break;
      case "session_summary":
        setSummary(event.payload as SessionSummary);
        setStatus("summary");
        break;
      case "error":
        setStatus("error");
        setErrorMessage(String(event.payload.message ?? "Something went wrong."));
        break;
      default:
        break;
    }
  }

  function resetAudioClock() {
    const context = getAudioContext();
    nextAudioStartRef.current = context.currentTime;
  }

  async function playAudioChunk(base64Chunk: string) {
    if (!base64Chunk) {
      return;
    }

    const context = getAudioContext();
    const binary = window.atob(base64Chunk);
    const bytes = new Uint8Array(binary.length);
    for (let index = 0; index < binary.length; index += 1) {
      bytes[index] = binary.charCodeAt(index);
    }

    try {
      const buffer = await context.decodeAudioData(bytes.buffer);
      const source = context.createBufferSource();
      source.buffer = buffer;
      source.connect(context.destination);
      const startAt = Math.max(context.currentTime, nextAudioStartRef.current);
      source.start(startAt);
      nextAudioStartRef.current = startAt + buffer.duration;
    } catch {
      // Some providers emit streaming fragments that are not individually decodable.
    }
  }

  function getAudioContext() {
    if (!audioContextRef.current) {
      audioContextRef.current = new AudioContext();
    }
    return audioContextRef.current;
  }

  return {
    sessionId,
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
  };
}

