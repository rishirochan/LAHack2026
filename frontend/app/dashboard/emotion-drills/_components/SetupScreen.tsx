"use client";

import type { SessionSetup, TargetEmotion, Theme } from "../types";

const themes: Theme[] = [
  "Job Interview",
  "Salary Negotiation",
  "Casual Conversation",
  "Public Speaking",
];

const emotions: TargetEmotion[] = [
  "Confident",
  "Enthusiastic",
  "Calm",
  "Assertive",
  "Passionate",
];

type SetupScreenProps = {
  value: SessionSetup;
  onChange: (value: SessionSetup) => void;
  onStart: () => void;
};

export default function SetupScreen({ value, onChange, onStart }: SetupScreenProps) {
  return (
    <div className="max-w-3xl mx-auto pt-12">
      <div className="text-center mb-10">
        <p className="text-sm font-semibold uppercase tracking-[0.3em] text-blue-600 mb-3">
          Emotion Drills
        </p>
        <h1 className="text-5xl font-bold tracking-tight text-foreground mb-4">
          Practice sounding intentional.
        </h1>
        <p className="text-lg text-foreground/60">
          Pick a scenario, choose the emotion you want to express, then answer a
          short 2-sentence prompt in 20 seconds or less.
        </p>
      </div>

      <div className="bg-white rounded-3xl border border-cream-200 p-8 shadow-sm">
        <label className="block mb-6">
          <span className="text-sm font-semibold text-foreground">Theme</span>
          <select
            value={value.theme}
            onChange={(event) => onChange({ ...value, theme: event.target.value as Theme })}
            className="mt-2 w-full rounded-2xl border border-cream-300 bg-cream-50 px-4 py-3 text-foreground outline-none focus:border-blue-600"
          >
            {themes.map((theme) => (
              <option key={theme} value={theme}>
                {theme}
              </option>
            ))}
          </select>
        </label>

        <label className="block mb-6">
          <span className="text-sm font-semibold text-foreground">Target emotion</span>
          <select
            value={value.targetEmotion}
            onChange={(event) =>
              onChange({ ...value, targetEmotion: event.target.value as TargetEmotion })
            }
            className="mt-2 w-full rounded-2xl border border-cream-300 bg-cream-50 px-4 py-3 text-foreground outline-none focus:border-blue-600"
          >
            {emotions.map((emotion) => (
              <option key={emotion} value={emotion}>
                {emotion}
              </option>
            ))}
          </select>
        </label>

        <label className="block mb-8">
          <div className="flex items-center justify-between">
            <span className="text-sm font-semibold text-foreground">Difficulty</span>
            <span className="rounded-full bg-blue-600/10 px-3 py-1 text-sm font-semibold text-blue-700">
              {value.difficulty}/10
            </span>
          </div>
          <input
            type="range"
            min={1}
            max={10}
            value={value.difficulty}
            onChange={(event) => onChange({ ...value, difficulty: Number(event.target.value) })}
            className="mt-4 w-full accent-blue-600"
          />
        </label>

        <button
          type="button"
          onClick={onStart}
          className="w-full rounded-2xl bg-blue-600 px-5 py-4 text-base font-semibold text-white transition hover:bg-blue-700"
        >
          Start Session
        </button>
      </div>
    </div>
  );
}

