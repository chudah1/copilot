"use client";

import Link from "next/link";
import { ArrowRight } from "lucide-react";

import { cleanTicker } from "@/components/portfolio/position-card";
import { formatAssumptionLabel } from "@/lib/assumption-label";
import {
  coachOutcomeCopy,
  decisionMemoryCta,
  patternKindCopy,
} from "@/lib/dashboard-memory";
import { positionDecisionTrailHref } from "@/lib/position-links";
import { cn } from "@/lib/utils";
import type {
  DashboardCoachMemory,
  DashboardRecentDecision,
  DashboardWorkspace,
  DashboardWorkspaceItem,
} from "@/types";

function toneClasses(tone: string | null | undefined) {
  if (tone === "warning") {
    return {
      panel: "border-amber-500/25 bg-[linear-gradient(180deg,rgba(245,158,11,0.10),rgba(255,255,255,0.88))]",
      pill: "border-amber-600/20 bg-amber-600/10 text-amber-800",
    };
  }
  if (tone === "calm") {
    return {
      panel: "border-emerald-500/25 bg-[linear-gradient(180deg,rgba(16,185,129,0.10),rgba(255,255,255,0.9))]",
      pill: "border-emerald-600/20 bg-emerald-600/10 text-emerald-800",
    };
  }
  return {
    panel: "border-border/70 bg-[linear-gradient(180deg,rgba(148,163,184,0.08),rgba(255,255,255,0.94))]",
    pill: "border-border bg-background text-foreground/70",
  };
}

function memoryIntro(investorProfile: DashboardWorkspace["investor_profile"]) {
  if (investorProfile === "hearsay_driven") {
    return "It is learning how you respond when the original reason starts to change.";
  }
  if (investorProfile === "thesis_driven") {
    return "It is learning how you respond when an assumption gets tested.";
  }
  return "It is learning how you respond when a position gets tested.";
}

function learningCopy(args: {
  investorProfile: DashboardWorkspace["investor_profile"];
  currentPressure: DashboardWorkspaceItem | null;
}) {
  const { currentPressure } = args;
  if (currentPressure) {
    const ticker = cleanTicker(currentPressure.holding.ticker);
    return `${ticker} is the clearest place to build that memory. A few closed decisions will make the pattern clearer.`;
  }
  return "A few more closed decisions will make this feel more like a pattern you can trust.";
}

function livePressureCopy(args: {
  currentPressure: DashboardWorkspaceItem | null;
  investorProfile: DashboardWorkspace["investor_profile"];
  patternKind: string | null | undefined;
}) {
  const { currentPressure, investorProfile, patternKind } = args;
  if (!currentPressure || currentPressure.decision_state === "calm") return null;

  const ticker = cleanTicker(currentPressure.holding.ticker);
  const assumption = formatAssumptionLabel(currentPressure.assumption_label, investorProfile, {
    maxLength: 72,
    sentenceCaseFallback: true,
  });

  if (patternKind === "attention") {
    return `${ticker} is getting tested. ${assumption} is the place to look first, and this matches the kind of early warning you often come back to late.`;
  }
  if (patternKind === "conviction") {
    return `${ticker} is getting tested. ${assumption} is the question on the table, and this matches the kind of signal you often sit with before making a clean call.`;
  }
  if (patternKind === "exit") {
    return `${ticker} is getting tested. ${assumption} is the place to revisit, and this matches the kind of shift that often later turns into an exit decision.`;
  }
  return `${ticker} is getting tested. ${assumption} is the best place to compare today’s read with your prior decisions.`;
}

function decisionVerb(entry: DashboardRecentDecision) {
  if (entry.action === "invalidated") return "Marked no longer holding";
  if (entry.action === "lowered_confidence") return "Lowered confidence";
  if (entry.action === "reaffirmed") return "Reaffirmed";
  if (entry.action === "not_relevant") return "Dismissed";
  if (entry.entry_type === "reason_updated") return "Updated";
  if (entry.entry_type === "post_earnings_review") return "Reviewed earnings";
  if (entry.entry_type === "quarterly_review") return "Quarterly review";
  return "Reviewed";
}

function timeAgo(iso: string) {
  const diffSec = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 1000));
  if (diffSec < 3600) return `${Math.max(1, Math.floor(diffSec / 60))}m ago`;
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`;
  const days = Math.floor(diffSec / 86400);
  if (days < 30) return `${days}d ago`;
  return `${Math.floor(days / 30)}mo ago`;
}

export function BehavioralMemoryStrip({
  workspace,
  coachMemory,
}: {
  workspace: DashboardWorkspace;
  coachMemory: DashboardCoachMemory | null;
}) {
  const { decision_memory: memory, recent_decisions: recentDecisions, top_decision: currentPressure, investor_profile: investorProfile } = workspace;
  const coachOutcome = coachOutcomeCopy(coachMemory);

  const tone = toneClasses(memory.primary_pattern?.tone);
  const patternMeta = patternKindCopy(memory.primary_pattern?.kind);
  const livePressure = livePressureCopy({
    currentPressure,
    investorProfile,
    patternKind: memory.primary_pattern?.kind,
  });
  const decisionTrailHref = recentDecisions[0]
    ? positionDecisionTrailHref(recentDecisions[0].ticker)
    : "/dashboard/quarterly-review#decision-patterns";
  const hasFollowThroughStats = Boolean(
    coachOutcome && (
      coachOutcome.summary.resolved > 0 ||
      coachOutcome.summary.acted > 0 ||
      coachOutcome.summary.helpful > 0 ||
      coachOutcome.summary.hurt > 0
    ),
  );
  const summaryChips = [
    memory.resolved_count > 0 ? `Closed ${memory.resolved_count}` : null,
    memory.open_followups_count > 0 ? `Waiting ${memory.open_followups_count}` : null,
    memory.primary_pattern ? `Pattern ${memory.primary_pattern.instances}x` : null,
    memory.primary_pattern && memory.primary_pattern.hits > 0 ? `Held up ${memory.primary_pattern.hits}` : null,
  ].filter((value): value is string => Boolean(value));

  return (
    <section className="grid gap-4 xl:grid-cols-12">
      <div className={cn("product-panel border p-5 sm:p-6 xl:col-span-5", tone.panel)}>
        <div className="space-y-5">
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <span className="border border-border/70 bg-background/80 px-2 py-1 font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                Behavioral memory
              </span>
              <span className={cn("border px-2 py-1 font-mono text-[10px] uppercase tracking-[0.16em]", tone.pill)}>
                {memory.has_pattern ? patternMeta.chip : "Learning"}
              </span>
            </div>
            <h2 className="max-w-2xl font-display text-[1.6rem] italic leading-tight text-foreground sm:text-[1.9rem]">
              {memory.has_pattern && memory.primary_pattern
                ? memory.primary_pattern.headline
                : "PenKeep is starting to recognize your decision style."}
            </h2>
            <p className="max-w-2xl font-sans text-sm leading-relaxed text-foreground/82">
              {memory.has_pattern && memory.primary_pattern
                ? memory.primary_pattern.detail
                : learningCopy({ investorProfile, currentPressure })}
            </p>
            <p className="max-w-2xl font-sans text-xs leading-relaxed text-foreground/65">
              {memoryIntro(investorProfile)}
            </p>
          </div>

          {summaryChips.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {summaryChips.map((chip) => (
                <span
                  key={chip}
                  className="border border-border/60 bg-background/70 px-2.5 py-1 font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground"
                >
                  {chip}
                </span>
              ))}
            </div>
          )}

          {livePressure && (
            <div className="border-t border-border/50 pt-4">
              <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                Why this matters now
              </p>
              <p className="mt-2 font-sans text-sm leading-relaxed text-foreground/82">
                {livePressure}
              </p>
            </div>
          )}

          <Link
            href={memory.has_pattern ? patternMeta.href : "/dashboard/quarterly-review#decision-patterns"}
            className="inline-flex items-center gap-2 border border-primary/25 bg-background/72 px-3 py-2 font-mono text-[10px] uppercase tracking-[0.16em] text-primary transition-colors hover:border-primary/45"
          >
            {decisionMemoryCta(memory)}
            <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </div>
      </div>

      <div className="product-panel border border-border/70 bg-background/88 p-5 sm:p-6 xl:col-span-3">
        <div className="space-y-5">
          <div className="space-y-2">
            <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
              Outcome memory
            </p>
            <h3 className="font-display text-[1.4rem] italic leading-tight text-foreground">
              What happens after you act
            </h3>
            <p className="font-sans text-sm leading-relaxed text-foreground/82">
              {coachOutcome?.body ?? "As prompted decisions resolve, this starts to show whether acting early helped or whether a situation kept becoming harder to ignore."}
            </p>
          </div>

          {hasFollowThroughStats ? (
            <div className="grid grid-cols-2 gap-2">
              <div className="border border-border/60 bg-background/70 px-3 py-3">
                <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
                  Resolved later
                </p>
                <p className="mt-2 font-display text-[1.55rem] italic leading-none text-foreground">
                  {coachOutcome?.summary.resolved ?? 0}
                </p>
              </div>
              <div className="border border-border/60 bg-background/70 px-3 py-3">
                <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
                  Acted on prompt
                </p>
                <p className="mt-2 font-display text-[1.55rem] italic leading-none text-foreground">
                  {coachOutcome?.summary.acted ?? coachMemory?.acted_count ?? 0}
                </p>
              </div>
              <div className="border border-emerald-700/15 bg-emerald-500/8 px-3 py-3">
                <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-emerald-800">
                  Held up
                </p>
                <p className="mt-2 font-display text-[1.55rem] italic leading-none text-emerald-900">
                  {coachOutcome?.summary.helpful ?? 0}
                </p>
              </div>
              <div className="border border-amber-700/15 bg-amber-500/8 px-3 py-3">
                <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-amber-800">
                  Kept worsening
                </p>
                <p className="mt-2 font-display text-[1.55rem] italic leading-none text-amber-900">
                  {coachOutcome?.summary.hurt ?? 0}
                </p>
              </div>
            </div>
          ) : (
            <div className="border border-dashed border-border/70 bg-background/55 px-3 py-4">
              <p className="font-sans text-sm leading-relaxed text-foreground/78">
                Once a few prompted decisions play out, this will show whether early action usually helped or whether pressure kept building.
              </p>
            </div>
          )}
        </div>
      </div>

      <div className="product-panel border border-border/70 bg-background/88 p-5 sm:p-6 xl:col-span-4">
        <div className="space-y-4">
          <div className="space-y-2">
            <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
              Decision trail
            </p>
            <h3 className="font-display text-[1.4rem] italic leading-tight text-foreground">
              Recent decisions
            </h3>
          </div>

          {recentDecisions.length > 0 ? (
            <div className="space-y-3">
              {recentDecisions.slice(0, 3).map((entry) => (
                <Link
                  key={`${entry.holding_id}:${entry.created_at}`}
                  href={positionDecisionTrailHref(entry.ticker)}
                  className="block border border-border/60 bg-background/70 px-3 py-3 transition-colors hover:border-foreground/20"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0 space-y-1">
                      <p className="font-sans text-sm text-foreground">
                        <span className="font-medium">{cleanTicker(entry.ticker)}</span>
                        <span className="text-foreground/55"> · {decisionVerb(entry)}</span>
                      </p>
                      <p className="font-sans text-xs leading-relaxed text-muted-foreground">
                        {formatAssumptionLabel(entry.assumption_label, investorProfile, {
                          maxLength: 60,
                          sentenceCaseFallback: true,
                        })}
                      </p>
                    </div>
                    <span className="shrink-0 font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
                      {timeAgo(entry.created_at)}
                    </span>
                  </div>
                </Link>
              ))}
            </div>
          ) : (
            <div className="border border-dashed border-border/70 bg-background/55 px-3 py-4">
              <p className="font-sans text-sm leading-relaxed text-foreground/78">
                As you close reviews, reaffirm your reason, or rewrite it, the recent decisions will start to collect here.
              </p>
            </div>
          )}

          <Link
            href={decisionTrailHref}
            className="inline-flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.16em] text-primary transition-colors hover:text-primary/75"
          >
            View decision trail
            <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </div>
      </div>
    </section>
  );
}
