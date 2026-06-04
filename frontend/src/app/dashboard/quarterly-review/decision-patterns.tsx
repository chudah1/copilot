"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

interface Pattern {
  kind: string;
  tone: "warning" | "calm" | "neutral" | string;
  headline: string;
  detail: string;
  instances: number;
  hits: number;
}

interface PatternsResponse {
  patterns: Pattern[];
  resolved_count: number;
}

const TONE: Record<string, string> = {
  warning: "border-amber-500/30 bg-amber-500/8",
  calm: "border-emerald-500/30 bg-emerald-500/8",
  neutral: "border-border/70 bg-background/55",
};

export function DecisionPatterns() {
  const [data, setData] = useState<PatternsResponse | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .get<PatternsResponse>("/api/quarterly-review/patterns")
      .then((d) => { if (!cancelled) setData(d); })
      .catch(() => { if (!cancelled) setData({ patterns: [], resolved_count: 0 }); });
    return () => { cancelled = true; };
  }, []);

  if (!data || data.patterns.length === 0) return null;

  return (
    <section className="space-y-3">
      <div className="product-panel product-panel-muted p-5">
        <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground mb-0.5">
          What your calls reveal
        </p>
        <p className="font-sans text-xs text-muted-foreground/70">
          Across {data.resolved_count} decision{data.resolved_count === 1 ? "" : "s"} that have since been tested.
        </p>
      </div>
      <div className="space-y-2">
        {data.patterns.map((p, i) => (
          <div key={i} className={`product-panel border px-5 py-4 space-y-1 ${TONE[p.tone] ?? TONE.neutral}`}>
            <p className="font-display italic text-[1.2rem] leading-tight text-foreground">{p.headline}</p>
            <p className="font-sans text-sm text-foreground/80 leading-relaxed">{p.detail}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
