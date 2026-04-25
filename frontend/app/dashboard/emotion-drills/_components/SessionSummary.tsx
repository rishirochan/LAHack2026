import type { SessionSummary as SessionSummaryType } from "../types";

type SessionSummaryProps = {
  summary: SessionSummaryType | null;
  onStartOver: () => void;
};

export default function SessionSummary({ summary, onStartOver }: SessionSummaryProps) {
  const scores = summary?.match_scores ?? [];
  const fillerEntries = Object.entries(summary?.filler_words ?? {});

  return (
    <div className="max-w-4xl mx-auto pt-10">
      <div className="mb-8 text-center">
        <p className="mb-3 text-sm font-semibold uppercase tracking-[0.3em] text-blue-600">
          Session Summary
        </p>
        <h1 className="text-4xl font-bold text-foreground">Nice work today.</h1>
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <section className="rounded-3xl border border-cream-200 bg-white p-6">
          <h2 className="mb-4 text-lg font-semibold text-foreground">Critiques</h2>
          {summary?.critiques.length ? (
            <ol className="space-y-4">
              {summary.critiques.map((critique, index) => (
                <li key={`${critique}-${index}`} className="rounded-2xl bg-cream-50 p-4">
                  <p className="mb-1 text-xs font-semibold uppercase tracking-widest text-foreground/40">
                    Round {index + 1}
                  </p>
                  <p className="text-sm leading-relaxed text-foreground/70">{critique}</p>
                </li>
              ))}
            </ol>
          ) : (
            <p className="text-sm text-foreground/50">No completed rounds yet.</p>
          )}
        </section>

        <section className="rounded-3xl border border-cream-200 bg-white p-6">
          <h2 className="mb-4 text-lg font-semibold text-foreground">Match score trend</h2>
          <div className="flex h-40 items-end gap-3 rounded-2xl bg-cream-50 p-4">
            {scores.length ? (
              scores.map((score, index) => (
                <div key={`${score}-${index}`} className="flex flex-1 flex-col items-center gap-2">
                  <div
                    className="w-full rounded-t-xl bg-blue-600"
                    style={{ height: `${Math.max(score * 100, 6)}%` }}
                  />
                  <span className="text-xs font-semibold text-foreground/50">
                    {Math.round(score * 100)}%
                  </span>
                </div>
              ))
            ) : (
              <p className="self-center text-sm text-foreground/50">No scores yet.</p>
            )}
          </div>

          <h2 className="mb-4 mt-6 text-lg font-semibold text-foreground">Filler words</h2>
          {fillerEntries.length ? (
            <div className="flex flex-wrap gap-2">
              {fillerEntries.map(([word, count]) => (
                <span key={word} className="rounded-full bg-cream-100 px-3 py-1 text-sm text-foreground/70">
                  {word}: {count}
                </span>
              ))}
            </div>
          ) : (
            <p className="text-sm text-foreground/50">No filler words detected.</p>
          )}
        </section>
      </div>

      <button
        type="button"
        onClick={onStartOver}
        className="mx-auto mt-8 block rounded-2xl bg-blue-600 px-6 py-3 text-sm font-semibold text-white hover:bg-blue-700"
      >
        Start New Session
      </button>
    </div>
  );
}

