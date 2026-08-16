"use client";

import Link from "next/link";
import { ArrowRight } from "lucide-react";

import { formatAssumptionLabel } from "@/lib/assumption-label";
import { cn } from "@/lib/utils";
import type { DashboardCommandCenter, DashboardCommandCenterHolding, DashboardCommandCenterSection } from "@/types";
import { cleanTicker } from "@/components/portfolio/position-card";

function investorNoun(
  investorProfile: DashboardCommandCenter["investor_profile"] | null | undefined,
) {
  if (investorProfile === "hearsay_driven") return "reason";
  if (investorProfile === "thesis_driven") return "thesis";
  return "reason";
}

function sectionTone(kind: DashboardCommandCenterSection["kind"]) {
  switch (kind) {
    case "needs_review":
      return {
        panel: "border-amber-500/25 bg-amber-500/8",
        pill: "border-amber-600/20 bg-amber-600/10 text-amber-800",
      };
    case "held_up":
      return {
        panel: "border-emerald-500/25 bg-emerald-500/8",
        pill: "border-emerald-600/20 bg-emerald-600/10 text-emerald-800",
      };
    case "unclear_theses":
      return {
        panel: "border-border bg-card/80",
        pill: "border-border bg-background text-foreground/70",
      };
    case "decision_debt":
      return {
        panel: "border-sky-500/25 bg-sky-500/8",
        pill: "border-sky-600/20 bg-sky-600/10 text-sky-800",
      };
    default:
      return {
        panel: "border-border bg-card/80",
        pill: "border-border bg-background text-foreground/70",
      };
  }
}

function workflowTone(state: DashboardCommandCenterHolding["workflow_state"]) {
  switch (state) {
    case "decision_needed":
      return "text-amber-800";
    case "pressure_building":
      return "text-amber-700";
    case "review_due":
      return "text-sky-800";
    case "draft_ready":
    case "signals_unconfirmed":
    case "no_thesis":
      return "text-foreground/70";
    case "calm":
      return "text-emerald-800";
    default:
      return "text-foreground/70";
  }
}

function workflowLabel(
  sectionKind: DashboardCommandCenterSection["kind"],
  item: DashboardCommandCenterHolding,
  investorProfile: DashboardCommandCenter["investor_profile"] | null | undefined,
) {
  if (sectionKind === "held_up") {
    return null;
  }
  if (sectionKind === "unclear_theses") {
    if (item.workflow_state === "no_thesis") {
      return investorProfile === "hearsay_driven" ? "Write reason" : "Write thesis";
    }
    if (item.workflow_state === "draft_ready") return "Draft ready";
    if (item.workflow_state === "signals_unconfirmed") return "Confirm signals";
    if (item.case_quality === "review_overdue") return "Refresh due";
    if (item.case_quality === "weak") return "Needs clarity";
    if (item.case_quality === "workable") return "Can sharpen";
  }
  return item.workflow_label;
}

function workflowMeta(
  sectionKind: DashboardCommandCenterSection["kind"],
  item: DashboardCommandCenterHolding,
  investorProfile?: DashboardCommandCenter["investor_profile"] | null,
) {
  const noun = investorNoun(investorProfile);
  if (sectionKind === "held_up") {
    return item.supporting_created_at ? "Fresh evidence" : null;
  }
  if (item.workflow_state === "review_due" && item.days_since_thesis_update != null) {
    return `${item.days_since_thesis_update}d since update`;
  }
  if (item.workflow_state === "decision_needed" && item.open_loop_count > 0) {
    return `${item.open_loop_count} review${item.open_loop_count === 1 ? "" : "s"} waiting`;
  }
  if (item.workflow_state === "pressure_building" && item.pulse_status === "watch") {
    return "New change detected";
  }
  if (sectionKind === "unclear_theses") {
    return null;
  }
  if (item.workflow_state === "draft_ready") {
    return "Ready to review";
  }
  if (item.workflow_state === "signals_unconfirmed") {
    return "Checks to confirm";
  }
  if (item.workflow_state === "no_thesis") {
    return `No ${noun} yet`;
  }
  if (item.case_quality === "weak") {
    return `${titleCase(noun)} needs clarity`;
  }
  if (item.case_quality === "workable") {
    return "One rule still needs sharpening";
  }
  return item.workflow_label;
}

function supportingLine(
  item: DashboardCommandCenterHolding,
  investorProfile: DashboardCommandCenter["investor_profile"] | null | undefined,
) {
  if (!item.assumption_label) return null;
  return formatAssumptionLabel(item.assumption_label, investorProfile ?? null, {
    maxLength: 64,
    sentenceCaseFallback: true,
  });
}

function truncateAtWordBoundary(value: string, maxLength: number) {
  if (value.length <= maxLength) return value;
  const sliced = value.slice(0, maxLength - 1);
  const boundary = sliced.lastIndexOf(" ");
  const trimmed = (boundary > Math.floor(maxLength * 0.6) ? sliced.slice(0, boundary) : sliced).trim();
  return `${trimmed}…`;
}

function compressHeldUpDetail(value: string | null | undefined) {
  if (!value) return null;
  const normalized = value.trim().replace(/\s+/g, " ");
  if (!normalized) return null;

  const sentenceMatch = normalized.match(/^.+?[.!?](?=\s|$)/);
  const firstSentence = sentenceMatch ? sentenceMatch[0].trim() : normalized;
  return truncateAtWordBoundary(firstSentence, 148);
}

function formatSupportingSourceTitle(title: string | null | undefined, ticker: string) {
  if (!title) return null;

  const normalized = title.trim().replace(/\s+/g, " ");
  if (!normalized) return null;

  const withoutTicker = normalized.replace(new RegExp(`^${ticker.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\s*:\\s*`, "i"), "").trim();
  const cleaned = withoutTicker || normalized;

  if (/analyst/i.test(cleaned)) {
    return "Analyst note";
  }
  if (/earnings/i.test(cleaned)) {
    return "Earnings note";
  }
  if (/shares are|what you need to know|market|sector/i.test(cleaned) || cleaned.split(",").length >= 3) {
    return "Market note";
  }

  return truncateAtWordBoundary(cleaned, 42);
}

function itemDetail(
  sectionKind: DashboardCommandCenterSection["kind"],
  item: DashboardCommandCenterHolding,
  investorProfile: DashboardCommandCenter["investor_profile"] | null | undefined,
) {
  if (sectionKind === "held_up") {
    return compressHeldUpDetail(item.supporting_summary || item.workflow_reason);
  }
  if (sectionKind === "decision_debt") {
    return item.open_loop_detail || item.workflow_reason;
  }
  if (sectionKind === "unclear_theses") {
    const noun =
      investorProfile === "hearsay_driven"
        ? "reason"
        : investorProfile === "thesis_driven"
          ? "thesis"
          : "reason";
    if (item.workflow_state === "draft_ready") {
      return "AI draft is ready for your review.";
    }
    if (item.workflow_state === "signals_unconfirmed") {
      return `The ${noun} is there. Confirm the suggested checks next.`;
    }
    if (item.workflow_state === "no_thesis") {
      return `A working ${noun} is still missing.`;
    }
    if (item.case_quality === "review_overdue") {
      return `${noun[0]?.toUpperCase() ?? ""}${noun.slice(1)} is due for a refresh.`;
    }
    if (item.case_quality === "weak") {
      if (!item.assumption_label) {
        return null;
      }
      return "Break condition still unclear.";
    }
    if (item.case_quality === "workable") {
      if (!item.assumption_label) {
        return null;
      }
      return "One monitored rule could be clearer.";
    }
  }
  return item.latest_event_summary || item.workflow_reason;
}

function compactCtaLabel(
  sectionKind: DashboardCommandCenterSection["kind"],
  label: string,
  investorProfile: DashboardCommandCenter["investor_profile"] | null | undefined,
) {
  const noun = investorNoun(investorProfile);
  if (label === "Open position") {
    if (sectionKind === "held_up") return "See why";
    if (sectionKind === "decision_debt") return "Revisit";
    if (sectionKind === "unclear_theses") return `Open ${noun}`;
    return "Open review";
  }
  return label;
}

function titleCase(value: string) {
  return `${value.slice(0, 1).toUpperCase()}${value.slice(1)}`;
}

function sectionHeadline(
  section: DashboardCommandCenterSection,
  investorProfile: DashboardCommandCenter["investor_profile"] | null | undefined,
) {
  const noun = investorNoun(investorProfile);
  const pluralNoun = noun === "thesis" ? "theses" : "reasons";
  if (section.count === 0) return "Quiet right now.";

  switch (section.kind) {
    case "needs_review":
      return section.count === 1 ? "1 decision waiting." : `${section.count} decisions waiting.`;
    case "held_up":
      return section.count === 1 ? "1 supporting update landed." : `${section.count} supporting updates landed.`;
    case "unclear_theses":
      return section.count === 1 ? `1 ${noun} needs attention.` : `${section.count} ${pluralNoun} need attention.`;
    case "decision_debt":
      return section.count === 1 ? "1 follow-up still waiting." : `${section.count} follow-ups still waiting.`;
    default:
      return `${section.count} in play.`;
  }
}

function repeatedSectionLabel(
  section: DashboardCommandCenterSection,
  investorProfile: DashboardCommandCenter["investor_profile"] | null | undefined,
) {
  if (section.items.length < 2) return null;

  const labels = section.items
    .map((item) => workflowLabel(section.kind, item, investorProfile))
    .filter((label): label is string => Boolean(label));

  if (labels.length !== section.items.length) return null;
  const first = labels[0];
  return labels.every((label) => label === first) ? first : null;
}

export function CommandCenterSection({
  section,
  investorProfile,
}: {
  section: DashboardCommandCenterSection;
  investorProfile: DashboardCommandCenter["investor_profile"] | null | undefined;
}) {
  const tone = sectionTone(section.kind);
  const sharedLabel = repeatedSectionLabel(section, investorProfile);

  return (
    <section className={cn("product-panel overflow-hidden border p-5 sm:p-6", tone.panel)}>
      <div className="space-y-2">
        <div className="space-y-2">
          <span className={cn("inline-flex border px-2 py-1 font-mono text-[10px] uppercase tracking-[0.18em]", tone.pill)}>
            {section.title}
          </span>
          <h3 className="font-display text-[1.45rem] italic leading-tight text-foreground">
            {sectionHeadline(section, investorProfile)}
          </h3>
          {section.count === 0 && (
            <p className="max-w-xl font-sans text-sm leading-relaxed text-foreground/75">
              {section.empty_copy}
            </p>
          )}
        </div>
      </div>

      {section.items.length === 0 ? null : (
        <div className="mt-5 space-y-3">
          {section.items.map((item) => {
            const assumption = supportingLine(item, investorProfile);
            const detail = itemDetail(section.kind, item, investorProfile);
            const meta = workflowMeta(section.kind, item, investorProfile);
            const supportingTitle = formatSupportingSourceTitle(
              item.supporting_title,
              cleanTicker(item.holding.ticker),
            );
            const ctaLabel = compactCtaLabel(section.kind, item.primary_cta_label, investorProfile);
            const isAssumptionLed = section.kind === "unclear_theses" && Boolean(assumption);
            const rowLabel = workflowLabel(section.kind, item, investorProfile);
            const showRowLabel = rowLabel && rowLabel !== sharedLabel;
            return (
              <div
                key={`${section.kind}-${item.holding.id}`}
                className="border border-border/70 bg-background/72 px-4 py-4 transition-colors hover:border-foreground/20"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0 space-y-2">
                    <div className="flex flex-wrap items-center gap-2">
                      {showRowLabel && (
                        <span className={cn("font-mono text-[10px] uppercase tracking-[0.18em]", workflowTone(item.workflow_state))}>
                          {rowLabel}
                        </span>
                      )}
                      <span className="font-sans text-sm font-semibold text-foreground">
                        {cleanTicker(item.holding.ticker)}
                      </span>
                      {meta && (
                        <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                          {meta}
                        </span>
                      )}
                    </div>

                    {assumption && (
                      <p className={cn(
                        "font-sans text-foreground/82",
                        isAssumptionLed ? "text-sm font-medium leading-relaxed" : "text-sm",
                      )}>
                        {assumption}
                      </p>
                    )}

                    {detail && (
                      <p className={cn(
                        "max-w-2xl font-sans leading-relaxed text-foreground/80",
                        isAssumptionLed ? "text-xs text-muted-foreground" : "text-sm",
                      )}>
                        {detail}
                      </p>
                    )}

                    {(item.open_loop_title || supportingTitle) && (
                      <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                        {item.open_loop_title || supportingTitle}
                      </p>
                    )}
                  </div>

                  <Link
                    href={item.primary_cta_href}
                    aria-label={`${ctaLabel} ${cleanTicker(item.holding.ticker)}`}
                    className="inline-flex shrink-0 items-center gap-1.5 border border-primary/25 bg-background/80 px-3 py-2 font-mono text-[10px] uppercase tracking-[0.16em] text-primary transition-colors hover:border-primary/50"
                  >
                    {ctaLabel}
                    <ArrowRight className="h-3 w-3" />
                  </Link>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
