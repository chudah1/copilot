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
        <div key={i} className="border border-amber-500/30 bg-amber-500/[0.06] px-3 py-3">
          <p className="font-sans text-sm leading-relaxed text-foreground/80">
            {w}
          </p>
        </div>
      ))}

      {insights.map((insight, i) => {
        const cardTone =
          insight.type === "warning"
            ? "border-red-500/30 bg-red-500/[0.05]"
            : insight.type === "event"
              ? "border-amber-500/30 bg-amber-500/[0.06]"
              : "border-emerald-500/30 bg-emerald-500/[0.05]";

        const tickerColor =
          insight.type === "warning" ? "text-red-600"
          : insight.type === "event" ? "text-amber-700"
          : "text-emerald-700";

        return (
          <div key={i} className={`border px-3 py-3 space-y-1 ${cardTone}`}>
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
