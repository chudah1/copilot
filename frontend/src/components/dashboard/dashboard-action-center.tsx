"use client";

import Link from "next/link";
import { ArrowRight } from "lucide-react";

import type { DashboardAction } from "@/lib/dashboard-action-queue";
import { cn } from "@/lib/utils";

function actionTone(action: DashboardAction, primary = false) {
  if (primary) {
    return "border-primary/40 bg-[linear-gradient(180deg,rgba(163,126,79,0.12),rgba(255,255,255,0.94))]";
  }
  if (action.kind === "decision" || action.kind === "follow_up") {
    return "border-amber-500/25 bg-amber-500/7";
  }
  if (action.kind === "weekly_review") {
    return "border-primary/25 bg-primary/5";
  }
  return "border-border/70 bg-background/55";
}

function ActionCard({
  action,
  primary = false,
  onCoachAct,
  onCoachSkip,
  onActionOpen,
}: {
  action: DashboardAction;
  primary?: boolean;
  onCoachAct?: (target: NonNullable<DashboardAction["coachTarget"]>) => Promise<void>;
  onCoachSkip?: () => Promise<void>;
  onActionOpen?: (action: DashboardAction) => void;
}) {
  return (
    <div className={cn("flex flex-col justify-between gap-4 border p-4", actionTone(action, primary))}>
      <div className="space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-primary">
            {action.eyebrow}
          </p>
          {action.ticker && (
            <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
              {action.ticker}
            </span>
          )}
          {action.carriedForward && (
            <span className="border border-amber-600/25 bg-amber-600/10 px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-[0.12em] text-amber-800">
              Carrying over
            </span>
          )}
        </div>
        <h3 className={cn("font-display italic leading-tight text-foreground", primary ? "text-[1.65rem]" : "text-[1.15rem]")}>
          {action.title}
        </h3>
        <p className="font-sans text-sm leading-relaxed text-foreground/75">
          {action.detail}
        </p>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        {action.coachTarget && onCoachAct ? (
          <button
            type="button"
            onClick={() => void onCoachAct(action.coachTarget!)}
            className={cn(
              "inline-flex w-fit items-center gap-1.5 border px-3 py-2 font-mono text-[10px] uppercase tracking-[0.15em] transition-colors",
              primary
                ? "border-primary/35 bg-primary text-primary-foreground hover:bg-primary/90"
                : "border-primary/25 bg-background/72 text-primary hover:border-primary/55",
            )}
          >
            {action.ctaLabel}
            <ArrowRight className="h-3 w-3" />
          </button>
        ) : (
          <Link
            href={action.href}
            onClick={() => onActionOpen?.(action)}
            className={cn(
              "inline-flex w-fit items-center gap-1.5 border px-3 py-2 font-mono text-[10px] uppercase tracking-[0.15em] transition-colors",
              primary
                ? "border-primary/35 bg-primary text-primary-foreground hover:bg-primary/90"
                : "border-primary/25 bg-background/72 text-primary hover:border-primary/55",
            )}
          >
            {action.ctaLabel}
            <ArrowRight className="h-3 w-3" />
          </Link>
        )}
        {action.secondaryHref && action.secondaryLabel && (
          <Link
            href={action.secondaryHref}
            onClick={() => onActionOpen?.(action)}
            className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground transition-colors hover:text-foreground"
          >
            {action.secondaryLabel}
          </Link>
        )}
        {action.coachTarget && onCoachSkip && (
          <button
            type="button"
            onClick={() => void onCoachSkip()}
            className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground transition-colors hover:text-foreground"
          >
            Not now
          </button>
        )}
      </div>
    </div>
  );
}

export function DashboardActionCenter({
  actions,
  onCoachAct,
  onCoachSkip,
  onActionOpen,
}: {
  actions: DashboardAction[];
  onCoachAct?: (target: NonNullable<DashboardAction["coachTarget"]>) => Promise<void>;
  onCoachSkip?: () => Promise<void>;
  onActionOpen?: (action: DashboardAction) => void;
}) {
  if (actions.length === 0) return null;

  const [primary, ...secondary] = actions;

  return (
    <section className="product-panel border border-border/70 bg-background/82 p-5 sm:p-6">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-muted-foreground">
            What needs you now
          </p>
          <h2 className="mt-2 font-display text-[1.75rem] italic leading-tight text-foreground sm:text-[2rem]">
            One clear next step.
          </h2>
        </div>
        <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground/65">
          {actions.length} {actions.length === 1 ? "priority" : "priorities"}
        </p>
      </div>

      <div className="mt-5 grid gap-3 lg:grid-cols-[1.15fr_0.85fr]">
        <ActionCard action={primary} primary onCoachAct={onCoachAct} onCoachSkip={onCoachSkip} onActionOpen={onActionOpen} />
        {secondary.length > 0 && (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1">
            {secondary.slice(0, 3).map((action) => (
              <ActionCard key={action.key} action={action} onCoachAct={onCoachAct} onCoachSkip={onCoachSkip} onActionOpen={onActionOpen} />
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
