"use client";

import Link from "next/link";
import { useState } from "react";
import { ArrowRight, Minus } from "lucide-react";

import { cleanTicker } from "@/components/portfolio/position-card";
import { cn } from "@/lib/utils";
import type { DashboardOpenLoop } from "@/types";

function loopTone(loopType: DashboardOpenLoop["loop_type"]) {
  switch (loopType) {
    case "claim_review":
      return {
        panel: "border-amber-500/25 bg-amber-500/8",
        chip: "border-amber-600/20 bg-amber-600/10 text-amber-800",
      };
    case "quarterly_unsure":
      return {
        panel: "border-sky-500/25 bg-sky-500/8",
        chip: "border-sky-600/20 bg-sky-600/10 text-sky-800",
      };
    default:
      return {
        panel: "border-border/70 bg-background/55",
        chip: "border-border bg-background text-foreground/70",
      };
  }
}

function loopLabel(loopType: DashboardOpenLoop["loop_type"]) {
  switch (loopType) {
    case "claim_review":
      return "Needs follow-up";
    case "quarterly_unsure":
      return "Review again";
    case "review_overdue":
      return "Refresh due";
    case "weak_thesis":
      return "Needs clarity";
    case "draft_unreviewed":
      return "Draft to review";
    default:
      return "Needs a decision";
  }
}

function ageCopy(ageDays: number) {
  if (ageDays <= 0) return "Waiting today";
  if (ageDays === 1) return "Waiting 1d";
  return `Waiting ${ageDays}d`;
}

function sectionHeadline(loops: DashboardOpenLoop[]) {
  return loops.length === 1 ? "1 follow-up is still waiting." : `${loops.length} follow-ups are still waiting.`;
}

function loopCtaLabel(label: string) {
  if (label === "Open position") {
    return "Resolve now";
  }
  return label;
}

export function OpenLoopsSection({
  loops,
  onDismiss,
}: {
  loops: DashboardOpenLoop[];
  onDismiss: (loopKey: string) => Promise<void>;
}) {
  const [dismissingKey, setDismissingKey] = useState<string | null>(null);

  if (loops.length === 0) {
    return null;
  }

  return (
    <section className="product-panel p-4 sm:p-5">
      <div className="space-y-2">
        <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
          Follow-ups
        </p>
        <h3 className="font-display text-[1.4rem] italic leading-tight text-foreground">
          {sectionHeadline(loops)}
        </h3>
        <p className="max-w-sm font-sans text-sm leading-relaxed text-foreground/72">
          Reviews or next steps that still need a clean close.
        </p>
      </div>

      <div className="mt-4 space-y-3">
        {loops.map((loop) => {
          const tone = loopTone(loop.loop_type);
          return (
            <div
              key={loop.loop_key}
              className={cn("border px-3 py-3", tone.panel)}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 space-y-1.5">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className={cn("border px-2 py-1 font-mono text-[10px] uppercase tracking-[0.14em]", tone.chip)}>
                      {loopLabel(loop.loop_type)}
                    </span>
                    <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
                      {ageCopy(loop.age_days)}
                    </span>
                  </div>
                  <p className="font-sans text-sm text-foreground">
                    <span className="font-medium">{cleanTicker(loop.ticker)}</span>
                    <span className="text-foreground/55"> · {loop.name}</span>
                  </p>
                  <p className="font-display text-[1.1rem] italic leading-tight text-foreground">
                    {loop.title}
                  </p>
                  <p className="font-sans text-xs leading-relaxed text-foreground/78">
                    {loop.detail}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={async () => {
                    setDismissingKey(loop.loop_key);
                    try {
                      await onDismiss(loop.loop_key);
                    } finally {
                      setDismissingKey(null);
                    }
                  }}
                  disabled={dismissingKey === loop.loop_key}
                  className="shrink-0 text-muted-foreground transition-colors hover:text-foreground disabled:opacity-40"
                  aria-label={`Hide ${cleanTicker(loop.ticker)} follow-up for now`}
                >
                  <Minus className="h-4 w-4" />
                </button>
              </div>

              <div className="mt-3 flex items-center justify-end gap-3 border-t border-border/50 pt-3">
                <Link
                  href={loop.cta_href}
                  className="inline-flex items-center gap-1.5 border border-primary/25 bg-background/72 px-3 py-2 font-mono text-[10px] uppercase tracking-[0.14em] text-primary transition-colors hover:border-primary/50"
                >
                  {loopCtaLabel(loop.cta_label)}
                  <ArrowRight className="h-3 w-3" />
                </Link>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
