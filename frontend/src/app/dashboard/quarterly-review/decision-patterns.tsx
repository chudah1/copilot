"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { positionDecisionTrailHref } from "@/lib/position-links";
import { cn } from "@/lib/utils";
import { formatDate } from "@/lib/utils";

interface Pattern {
  kind: string;
  tone: "warning" | "calm" | "neutral" | string;
  headline: string;
  detail: string;
  instances: number;
  hits: number;
  examples: PatternExample[];
}

interface PatternExample {
  ticker: string;
  bucket: string;
  bet_text: string | null;
  read: string | null;
  decided_at: string | null;
  resolved_at: string | null;
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

function patternLabel(kind: string) {
  switch (kind) {
    case "attention":
      return "Early-warning pattern";
    case "conviction":
      return "Conviction pattern";
    case "exit":
      return "Exit pattern";
    default:
      return "Pattern";
  }
}

function exampleBucketLabel(bucket: string) {
  switch (bucket) {
    case "dismissed":
      return "Dismissed";
    case "held":
      return "Held";
    case "exited":
      return "Exited";
    default:
      return bucket;
  }
}

function exampleActionCopy(kind: string, bucket: string) {
  if (kind === "attention" && bucket === "dismissed") {
    return "Review the dismissed decision";
  }
  if (kind === "conviction" && bucket === "held") {
    return "Open the hold decision";
  }
  if (kind === "exit" && bucket === "exited") {
    return "Open the exit decision";
  }
  return "View decision trail";
}

export function DecisionPatterns({
  selectedKind = null,
  variant = "full",
}: {
  selectedKind?: string | null;
  variant?: "full" | "compact";
}) {
  const [data, setData] = useState<PatternsResponse | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .get<PatternsResponse>("/api/quarterly-review/patterns")
      .then((d) => { if (!cancelled) setData(d); })
      .catch(() => { if (!cancelled) setData({ patterns: [], resolved_count: 0 }); });
    return () => { cancelled = true; };
  }, []);

  const orderedPatterns = useMemo(() => {
    if (!data) return [];
    if (!selectedKind) return data.patterns;
    return [...data.patterns].sort((a, b) => {
      if (a.kind === selectedKind) return -1;
      if (b.kind === selectedKind) return 1;
      return 0;
    });
  }, [data, selectedKind]);

  if (!data || orderedPatterns.length === 0) return null;

  const visiblePatterns = variant === "compact" ? orderedPatterns.slice(0, 1) : orderedPatterns;
  const sectionId = variant === "full" ? "decision-patterns" : undefined;

  return (
    <section id={sectionId} className="space-y-3 scroll-mt-24">
      <div className="product-panel border border-border/60 bg-background/82 p-5">
        <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground mb-0.5">
          What your decisions reveal
        </p>
        <p className="font-sans text-xs text-muted-foreground/70">
          Across {data.resolved_count} decision{data.resolved_count === 1 ? "" : "s"} that have since been tested.
        </p>
        {selectedKind && orderedPatterns[0]?.kind === selectedKind && (
          <p className="mt-2 font-sans text-xs text-foreground/65">
            Jumped here from the dashboard because this is the strongest pattern showing up right now.
          </p>
        )}
      </div>
      <div className="space-y-2">
        {visiblePatterns.map((p, i) => (
          <div
            key={i}
            className={cn(
              "product-panel border px-5 py-4 space-y-4 transition-shadow",
              TONE[p.tone] ?? TONE.neutral,
              selectedKind === p.kind && "ring-1 ring-primary/25 shadow-[0_10px_30px_-18px_rgba(52,40,24,0.28)]",
            )}
          >
            <div className="space-y-1">
              <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                {patternLabel(p.kind)}
              </p>
              <p className="font-display italic text-[1.2rem] leading-tight text-foreground">{p.headline}</p>
              <p className="font-sans text-sm text-foreground/80 leading-relaxed">{p.detail}</p>
            </div>

            {p.examples.length > 0 && (
              <div className="space-y-2 border-t border-border/40 pt-4">
                <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                  Recent examples
                </p>
                <div className="grid gap-2">
                  {p.examples.slice(0, 3).map((example) => (
                    <div
                      key={`${p.kind}-${example.ticker}-${example.decided_at ?? "na"}`}
                      className="border border-border/60 bg-background/70 px-3 py-3"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0 space-y-1">
                          <p className="font-sans text-sm text-foreground">
                            <span className="font-medium">{example.ticker}</span>
                            <span className="text-foreground/55"> · {exampleBucketLabel(example.bucket)} decision</span>
                          </p>
                          {example.bet_text && (
                            <p className="font-sans text-xs leading-relaxed text-muted-foreground">
                              {example.bet_text}
                            </p>
                          )}
                          {example.read && (
                            <p className="font-sans text-xs leading-relaxed text-foreground/78">
                              {example.read}
                            </p>
                          )}
                        </div>
                        <div className="shrink-0 text-right">
                          {example.resolved_at && (
                            <p className="font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
                              {formatDate(example.resolved_at)}
                            </p>
                          )}
                        </div>
                      </div>

                      <div className="mt-3 flex items-center justify-between gap-3 border-t border-border/50 pt-3">
                        <p className="font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
                          {example.decided_at ? `Decided ${formatDate(example.decided_at)}` : "Decision saved"}
                        </p>
                        <Link
                          href={positionDecisionTrailHref(example.ticker)}
                          className="inline-flex items-center gap-1.5 border border-primary/25 bg-background/72 px-3 py-2 font-mono text-[10px] uppercase tracking-[0.14em] text-primary transition-colors hover:border-primary/50"
                        >
                          {exampleActionCopy(p.kind, example.bucket)}
                        </Link>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
      {variant === "compact" && orderedPatterns.length > 1 && (
        <Link
          href="#decision-patterns"
          className="inline-flex items-center gap-1.5 border border-primary/25 bg-background/72 px-3 py-2 font-mono text-[10px] uppercase tracking-[0.14em] text-primary transition-colors hover:border-primary/50"
        >
          See all patterns
        </Link>
      )}
    </section>
  );
}
