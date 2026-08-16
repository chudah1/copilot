"use client";

import { ArrowRight } from "lucide-react";

import { cn } from "@/lib/utils";
import type { DashboardCoachPlan } from "@/lib/dashboard-coach";

function toneClasses(tone: DashboardCoachPlan["tone"]) {
  switch (tone) {
    case "warning":
      return {
        panel: "border-amber-500/25 bg-[linear-gradient(180deg,rgba(245,158,11,0.12),rgba(245,158,11,0.05))]",
        chip: "border-amber-600/20 bg-amber-600/10 text-amber-800",
      };
    case "focus":
      return {
        panel: "border-sky-500/25 bg-[linear-gradient(180deg,rgba(14,165,233,0.12),rgba(14,165,233,0.04))]",
        chip: "border-sky-600/20 bg-sky-600/10 text-sky-800",
      };
    default:
      return {
        panel: "border-emerald-500/25 bg-[linear-gradient(180deg,rgba(16,185,129,0.10),rgba(16,185,129,0.04))]",
        chip: "border-emerald-600/20 bg-emerald-600/10 text-emerald-800",
      };
  }
}

export function DecisionCoachCard({
  plan,
  onAct,
  onSkip,
}: {
  plan: DashboardCoachPlan;
  onAct: (target: DashboardCoachPlan["primaryCta"] | NonNullable<DashboardCoachPlan["secondaryCta"]>) => Promise<void>;
  onSkip: () => Promise<void>;
}) {
  const tone = toneClasses(plan.tone);
  const secondaryCta = plan.secondaryCta;

  return (
    <section className={cn("product-panel border p-4 sm:p-5 overflow-hidden", tone.panel)}>
      <div className="space-y-4">
        <div className="flex items-center justify-between gap-3">
          <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
            {plan.eyebrow}
          </p>
          <span className={cn("border px-2 py-1 font-mono text-[10px] uppercase tracking-[0.14em]", tone.chip)}>
            {plan.chip}
          </span>
        </div>

        <div className="space-y-2">
          <h2 className="font-display text-[1.45rem] italic leading-tight text-foreground">
            {plan.title}
          </h2>
          <p className="font-sans text-sm leading-relaxed text-foreground/82">
            {plan.body}
          </p>
          <p className="font-sans text-xs leading-relaxed text-muted-foreground">
            {plan.context}
          </p>
        </div>

        {plan.stats.length > 0 && (
          <div className={cn("grid gap-2", plan.stats.length === 1 ? "grid-cols-1" : "grid-cols-2")}>
            {plan.stats.map((stat) => (
              <div key={stat.label} className="border border-border/60 bg-background/65 px-3 py-3">
                <p className="font-mono text-[9px] uppercase tracking-[0.18em] text-muted-foreground/70">
                  {stat.label}
                </p>
                <p className="mt-1 font-display text-[1.2rem] italic leading-none text-foreground">
                  {stat.value}
                </p>
              </div>
            ))}
          </div>
        )}

        <div className="flex flex-wrap items-center gap-3 border-t border-border/50 pt-4">
          <button
            type="button"
            onClick={() => void onAct(plan.primaryCta)}
            className="inline-flex items-center gap-2 border border-primary/25 bg-background/70 px-3 py-2 font-mono text-[10px] uppercase tracking-[0.16em] text-primary transition-colors hover:border-primary/50"
          >
            {plan.primaryCta.label}
            <ArrowRight className="h-3.5 w-3.5" />
          </button>
          {secondaryCta && (
            <button
              type="button"
              onClick={() => void onAct(secondaryCta)}
              className="inline-flex items-center gap-2 border border-border/60 bg-background/72 px-3 py-2 font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground transition-colors hover:border-border hover:text-foreground"
            >
              {secondaryCta.label}
              <ArrowRight className="h-3.5 w-3.5" />
            </button>
          )}
          <button
            type="button"
            onClick={() => void onSkip()}
            className="inline-flex items-center gap-2 border border-border/60 bg-background/72 px-3 py-2 font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground transition-colors hover:border-border hover:text-foreground"
          >
            Not now
          </button>
        </div>
      </div>
    </section>
  );
}
