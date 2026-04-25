type MatchScoreIndicatorProps = {
  score: number;
};

export default function MatchScoreIndicator({ score }: MatchScoreIndicatorProps) {
  const percentage = Math.round(score * 100);
  const colorClass =
    score > 0.6 ? "text-emerald-600" : score >= 0.3 ? "text-amber-500" : "text-red-500";
  const strokeClass =
    score > 0.6 ? "stroke-emerald-500" : score >= 0.3 ? "stroke-amber-400" : "stroke-red-400";
  const circumference = 2 * Math.PI * 42;
  const dashOffset = circumference * (1 - Math.min(Math.max(score, 0), 1));

  return (
    <div className="flex items-center gap-4 rounded-2xl border border-cream-200 bg-white p-4">
      <div className="relative h-24 w-24">
        <svg className="-rotate-90" viewBox="0 0 100 100">
          <circle cx="50" cy="50" r="42" fill="none" strokeWidth="10" className="stroke-cream-200" />
          <circle
            cx="50"
            cy="50"
            r="42"
            fill="none"
            strokeWidth="10"
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={dashOffset}
            className={strokeClass}
          />
        </svg>
        <div className={`absolute inset-0 flex items-center justify-center text-xl font-bold ${colorClass}`}>
          {percentage}%
        </div>
      </div>
      <div>
        <p className="text-sm font-semibold text-foreground">Emotion match</p>
        <p className="text-sm text-foreground/50">
          Based on the strongest matching facial emotion event.
        </p>
      </div>
    </div>
  );
}

