"use client";

import { useState } from "react";
import ActiveSessionScreen from "./_components/ActiveSessionScreen";
import SessionSummary from "./_components/SessionSummary";
import SetupScreen from "./_components/SetupScreen";
import { usePhaseASession } from "./_hooks/usePhaseASession";
import type { SessionSetup } from "./types";

const defaultSetup: SessionSetup = {
  theme: "Job Interview",
  targetEmotion: "Confident",
  difficulty: 5,
};

export default function EmotionDrillsPage() {
  const [setup, setSetup] = useState<SessionSetup>(defaultSetup);
  const {
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
  } = usePhaseASession();

  const handleStart = async () => {
    await startSession(setup);
  };

  if (status === "setup") {
    return <SetupScreen value={setup} onChange={setSetup} onStart={handleStart} />;
  }

  if (status === "summary") {
    return <SessionSummary summary={summary} onStartOver={() => window.location.reload()} />;
  }

  if (status === "error") {
    return (
      <div className="mx-auto flex min-h-[60vh] max-w-xl flex-col items-center justify-center text-center">
        <p className="mb-3 text-sm font-semibold uppercase tracking-[0.3em] text-red-500">
          Session Error
        </p>
        <h1 className="mb-4 text-4xl font-bold text-foreground">Something got stuck.</h1>
        <p className="mb-6 text-foreground/60">
          {errorMessage || "Refresh and try the drill again."}
        </p>
        <button
          type="button"
          onClick={() => window.location.reload()}
          className="rounded-2xl bg-blue-600 px-5 py-3 text-sm font-semibold text-white hover:bg-blue-700"
        >
          Restart Drill
        </button>
      </div>
    );
  }

  return (
    <ActiveSessionScreen
      status={status}
      scenarioPrompt={scenarioPrompt}
      critique={critique}
      processingStage={processingStage}
      roundResult={roundResult}
      errorMessage={errorMessage}
      onUploadRecording={uploadRecording}
      onTryAgain={() => chooseContinue(true)}
      onEndSession={() => chooseContinue(false)}
    />
  );
}

