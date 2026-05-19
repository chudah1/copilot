"use client";

interface PulseInsight {
  ticker: string;
  type: "event" | "warning" | "stable";
  headline: string;
  rationale: string;
}

interface PulseStreamProps {
  insights: PulseInsight[];
  warnings: string[];
}

export function PulseStream({ insights, warnings }: PulseStreamProps) {
  if (!insights.length && !warnings.length) {
    return (
      <p className="font-sans italic text-sm text-muted-foreground py-2">
        Nothing to note at this time.
      </p>
    );
  }

  return (
    <div className="space-y-5">
      {warnings.map((w, i) => (
        <div key={i} className="text-sm text-amber-300 leading-relaxed border-l-2 border-amber-500/60 pl-3">
          {w}
        </div>
      ))}

      {insights.map((insight, i) => {
        const borderColor =
          insight.type === "warning" ? "border-red-500/60"
          : insight.type === "event" ? "border-amber-500/60"
          : "border-emerald-500/60";

        const tickerColor =
          insight.type === "warning" ? "text-red-600"
          : insight.type === "event" ? "text-amber-700"
          : "text-emerald-700";

        return (
          <div key={i} className={`border-l-2 ${borderColor} pl-3 space-y-1`}>
            <div className="flex items-baseline gap-2 flex-wrap">
              <span className={`font-mono text-[11px] font-bold uppercase tracking-wide ${tickerColor}`}>
                {insight.ticker}
              </span>
              <span className="font-sans text-sm text-foreground/80">
                {insight.headline}
              </span>
            </div>
            {insight.rationale && (
              <p className="font-sans italic text-xs text-muted-foreground leading-relaxed">
                {insight.rationale}
              </p>
            )}
          </div>
        );
      })}
    </div>
  );
}
