"use client";

import { Loader2, Mic, Square } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import CritiqueDisplay from "./CritiqueDisplay";
import type { RoundResult, SessionStatus } from "../types";

const MAX_RECORDING_SECONDS = 20;
const MIN_RECORDING_SECONDS = 2;
const processingStages = [
  "Uploading recording",
  "Analyzing facial emotion",
  "Analyzing vocal emotion",
  "Transcribing speech",
  "Generating critique",
  "Preparing playback",
];

type ActiveSessionScreenProps = {
  status: SessionStatus;
  scenarioPrompt: string;
  critique: string;
  processingStage: string;
  roundResult: RoundResult | null;
  errorMessage: string;
  onUploadRecording: (videoBlob: Blob, audioBlob: Blob, durationSeconds: number) => Promise<void>;
  onTryAgain: () => void;
  onEndSession: () => void;
};

export default function ActiveSessionScreen({
  status,
  scenarioPrompt,
  critique,
  processingStage,
  roundResult,
  errorMessage,
  onUploadRecording,
  onTryAgain,
  onEndSession,
}: ActiveSessionScreenProps) {
  const [isRecording, setIsRecording] = useState(false);
  const [secondsRemaining, setSecondsRemaining] = useState(MAX_RECORDING_SECONDS);
  const [localError, setLocalError] = useState("");
  const previewRef = useRef<HTMLVideoElement | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const videoRecorderRef = useRef<MediaRecorder | null>(null);
  const audioRecorderRef = useRef<MediaRecorder | null>(null);
  const videoChunksRef = useRef<Blob[]>([]);
  const audioChunksRef = useRef<Blob[]>([]);
  const startedAtRef = useRef<number>(0);
  const timerRef = useRef<number | null>(null);

  const toggleRecording = async () => {
    if (isRecording) {
      await stopRecording();
      return;
    }
    await startRecording();
  };

  const startRecording = async () => {
    try {
      setLocalError("");
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
        mimeType: getSupportedMimeType(["video/webm;codecs=vp8,opus", "video/webm"]),
      });
      const audioRecorder = new MediaRecorder(audioOnlyStream, {
        mimeType: getSupportedMimeType(["audio/webm;codecs=opus", "audio/webm"]),
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
      setLocalError("Camera or microphone access was blocked. Allow access and try again.");
    }
  };

  const stopRecording = async () => {
    stopTimer();
    setIsRecording(false);
    const durationSeconds = (window.performance.now() - startedAtRef.current) / 1000;

    if (durationSeconds < MIN_RECORDING_SECONDS) {
      stopRecordersWithoutUpload();
      setLocalError("That was a little too short. Try recording a full response.");
      return;
    }

    const [videoBlob, audioBlob] = await Promise.all([
      stopRecorder(videoRecorderRef.current, videoChunksRef.current, "video/webm"),
      stopRecorder(audioRecorderRef.current, audioChunksRef.current, "audio/webm"),
    ]);
    await onUploadRecording(videoBlob, audioBlob, durationSeconds);
  };

  const startCountdown = () => {
    stopTimer();
    timerRef.current = window.setInterval(() => {
      const elapsed = Math.floor((window.performance.now() - startedAtRef.current) / 1000);
      const remaining = Math.max(MAX_RECORDING_SECONDS - elapsed, 0);
      setSecondsRemaining(remaining);
      if (remaining === 0) {
        void stopRecording();
      }
    }, 250);
  };

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

  const stopRecordersWithoutUpload = () => {
    [videoRecorderRef.current, audioRecorderRef.current].forEach((recorder) => {
      if (recorder?.state === "recording") {
        recorder.stop();
      }
    });
  };

  const canRecord = status === "recording" || isRecording;
  const warningClass = secondsRemaining <= 5 ? "text-red-500" : "text-foreground/50";

  return (
    <div className="space-y-6">
      <section className="rounded-3xl border border-cream-200 bg-white p-6">
        <p className="mb-2 text-sm font-semibold uppercase tracking-widest text-blue-600">
          Scenario
        </p>
        <p className="min-h-20 text-2xl font-semibold leading-relaxed text-foreground">
          {scenarioPrompt || "Generating your 2-sentence prompt..."}
        </p>
      </section>

      <section className="grid gap-6 lg:grid-cols-[1fr_260px]">
        <div className="flex min-h-[340px] flex-col items-center justify-center rounded-3xl border border-cream-200 bg-white p-8">
          {status === "processing" ? (
            <ProcessingStages activeStage={processingStage} />
          ) : (
            <>
              <button
                type="button"
                disabled={!canRecord}
                onClick={toggleRecording}
                className={`flex h-36 w-36 items-center justify-center rounded-full transition ${
                  isRecording
                    ? "animate-pulse bg-red-500 text-white"
                    : "bg-blue-600 text-white hover:bg-blue-700 disabled:bg-foreground/20"
                }`}
              >
                {isRecording ? <Square className="h-10 w-10" /> : <Mic className="h-12 w-12" />}
              </button>
              <p className="mt-5 text-sm font-semibold text-foreground">
                {isRecording ? "Recording..." : "Click to start recording"}
              </p>
              <p className={`mt-2 text-sm ${warningClass}`}>
                {isRecording
                  ? `${secondsRemaining}s remaining`
                  : "You will have 20 seconds to answer."}
              </p>
            </>
          )}
          {(localError || errorMessage) && (
            <p className="mt-4 rounded-2xl bg-red-50 px-4 py-3 text-sm text-red-600">
              {localError || errorMessage}
            </p>
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

      {(status === "critique" || roundResult) && (
        <CritiqueDisplay
          critique={critique || roundResult?.critique || ""}
          matchScore={roundResult?.match_score ?? 0}
          onTryAgain={onTryAgain}
          onEndSession={onEndSession}
        />
      )}
    </div>
  );
}

function ProcessingStages({ activeStage }: { activeStage: string }) {
  const activeIndex = Math.max(processingStages.indexOf(activeStage), 0);

  return (
    <div className="w-full max-w-md">
      <div className="mb-6 flex items-center justify-center gap-3 text-blue-600">
        <Loader2 className="h-6 w-6 animate-spin" />
        <span className="text-sm font-semibold">{activeStage || "Processing recording"}</span>
      </div>
      <div className="space-y-3">
        {processingStages.map((stage, index) => (
          <div
            key={stage}
            className={`flex items-center gap-3 rounded-2xl px-4 py-3 text-sm ${
              index <= activeIndex ? "bg-blue-600/10 text-blue-700" : "bg-cream-50 text-foreground/40"
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

function getSupportedMimeType(candidates: string[]) {
  return candidates.find((candidate) => MediaRecorder.isTypeSupported(candidate)) ?? "";
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

    if (recorder.state === "recording") {
      recorder.stop();
    } else {
      resolve(new Blob(chunks, { type: recorder.mimeType || fallbackType }));
    }
  });
}

