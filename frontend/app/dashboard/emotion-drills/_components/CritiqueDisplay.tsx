import MatchScoreIndicator from "./MatchScoreIndicator";

type CritiqueDisplayProps = {
  critique: string;
  matchScore: number;
  onTryAgain: () => void;
  onEndSession: () => void;
};

export default function CritiqueDisplay({
  critique,
  matchScore,
  onTryAgain,
  onEndSession,
}: CritiqueDisplayProps) {
  return (
    <div className="grid gap-5 lg:grid-cols-[1fr_320px]">
      <div className="rounded-3xl border border-cream-200 bg-white p-6">
        <p className="mb-2 text-sm font-semibold uppercase tracking-widest text-blue-600">
          Coach critique
        </p>
        <p className="text-xl leading-relaxed text-foreground">
          {critique || "Preparing your critique..."}
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <button
            type="button"
            onClick={onTryAgain}
            className="rounded-2xl bg-blue-600 px-5 py-3 text-sm font-semibold text-white hover:bg-blue-700"
          >
            Try Again
          </button>
          <button
            type="button"
            onClick={onEndSession}
            className="rounded-2xl border border-cream-300 px-5 py-3 text-sm font-semibold text-foreground hover:bg-cream-50"
          >
            End Session
          </button>
        </div>
      </div>
      <MatchScoreIndicator score={matchScore} />
    </div>
  );
}

