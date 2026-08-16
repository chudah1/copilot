"use client";

import Link from "next/link";
import { ArrowRight } from "lucide-react";

import { formatAssumptionLabel } from "@/lib/assumption-label";
import { positionDetailHref } from "@/lib/position-links";
import { cn } from "@/lib/utils";
import type { DashboardCommandCenter } from "@/types";
import { cleanTicker } from "@/components/portfolio/position-card";

const SECTION_ORDER: Array<DashboardCommandCenter["sections"][number]["kind"]> = [
  "needs_review",
  "unclear_theses",
  "decision_debt",
  "held_up",
];

function orderedSections(center: DashboardCommandCenter) {
  return [...center.sections].sort(
    (a, b) => SECTION_ORDER.indexOf(a.kind) - SECTION_ORDER.indexOf(b.kind),
  );
}

function primaryItem(center: DashboardCommandCenter) {
  for (const section of orderedSections(center)) {
    if (section.items.length > 0) return { section, item: section.items[0] };
  }
  return null;
}

function queueItems(
  center: DashboardCommandCenter,
  primary: ReturnType<typeof primaryItem>,
) {
  const primaryHoldingId = primary?.item.holding.id ?? null;
  return orderedSections(center)
    .flatMap((section) => section.items)
    .filter((item) => item.holding.id !== primaryHoldingId);
}

function unclearStateCopy(
  item: DashboardCommandCenter["sections"][number]["items"][number],
  investorProfile: DashboardCommandCenter["investor_profile"] | null | undefined,
) {
  const noun =
    investorProfile === "hearsay_driven"
      ? "reason"
      : investorProfile === "thesis_driven"
        ? "thesis"
        : "reason";

  if (item.workflow_state === "draft_ready") {
    return {
      titleVerb: "Review",
      body: `An AI draft is waiting for your judgment before it becomes the live ${noun}.`,
      cta: item.primary_cta_label,
    };
  }

  if (item.workflow_state === "signals_unconfirmed") {
    return {
      titleVerb: "Confirm",
      body: `The ${noun} is there. Confirm the suggested checks before monitoring goes live.`,
      cta: item.primary_cta_label,
    };
  }

  if (item.workflow_state === "no_thesis") {
    return {
      titleVerb: "Write",
      body: `The price is live, but the ${noun} is still unwritten.`,
      cta: item.primary_cta_label,
    };
  }

  if (item.case_quality === "review_overdue") {
    return {
      titleVerb: "Refresh",
      body: `The ${noun} is due for a refresh. Refresh it while the position is still calm.`,
      cta: `Refresh ${cleanTicker(item.holding.ticker)}`,
    };
  }

  if (item.case_quality === "weak") {
    return {
      titleVerb: "Clarify",
      body: "The break condition still needs clarity.",
      cta: `Clarify ${cleanTicker(item.holding.ticker)}`,
    };
  }

  return {
    titleVerb: "Clarify",
    body: "One check still needs sharpening.",
    cta: `Clarify ${cleanTicker(item.holding.ticker)}`,
  };
}

function watchlistBody(
  item: DashboardCommandCenter["sections"][number]["items"][number],
  investorProfile: DashboardCommandCenter["investor_profile"] | null | undefined,
) {
  const noun =
    investorProfile === "hearsay_driven"
      ? "reason"
      : investorProfile === "thesis_driven"
        ? "thesis"
        : "reason";

  if (item.workflow_state === "draft_ready") {
    return "AI draft ready for review.";
  }
  if (item.workflow_state === "signals_unconfirmed") {
    return "Suggested checks still need confirmation.";
  }
  if (item.workflow_state === "no_thesis") {
    return `Position is live, but the ${noun} is still unwritten.`;
  }
  if (item.case_quality === "review_overdue") {
    return "Last rewrite is due for a refresh.";
  }
  if (item.case_quality === "weak") {
    return "Break condition still needs clarity.";
  }
  if (item.case_quality === "workable") {
    return "One check still needs sharpening.";
  }
  return item.workflow_reason;
}

function heroEyebrow(sectionKind: DashboardCommandCenter["sections"][number]["kind"] | null) {
  switch (sectionKind) {
    case "needs_review":
      return "Decision due";
    case "unclear_theses":
      return "Start here";
    case "decision_debt":
      return "Waiting on you";
    case "held_up":
      return "Held up recently";
    default:
      return "Quiet board";
  }
}

function heroCta(
  sectionKind: DashboardCommandCenter["sections"][number]["kind"],
  label: string | null | undefined,
  ticker: string,
) {
  if (!label || label === "Open position") {
    if (sectionKind === "held_up") return `See why ${ticker} held`;
    if (sectionKind === "decision_debt") return `Revisit ${ticker}`;
    if (sectionKind === "unclear_theses") return `Set up ${ticker}`;
    return `Review ${ticker}`;
  }
  return label;
}

function queueSubline(
  item: DashboardCommandCenter["sections"][number]["items"][number],
  investorProfile: DashboardCommandCenter["investor_profile"] | null | undefined,
) {
  if (item.assumption_label) {
    return formatAssumptionLabel(item.assumption_label, investorProfile ?? null, {
      maxLength: 72,
      sentenceCaseFallback: true,
    });
  }
  return watchlistBody(item, investorProfile);
}

function stateTone(sectionKind: DashboardCommandCenter["sections"][number]["kind"] | null) {
  switch (sectionKind) {
    case "needs_review":
      return {
        panel: "border-amber-500/25 bg-amber-500/8",
        pill: "border-amber-600/20 bg-amber-600/10 text-amber-800",
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
    case "held_up":
      return {
        panel: "border-emerald-500/25 bg-emerald-500/8",
        pill: "border-emerald-600/20 bg-emerald-600/10 text-emerald-800",
      };
    default:
      return {
        panel: "border-emerald-500/25 bg-emerald-500/8",
        pill: "border-emerald-600/20 bg-emerald-600/10 text-emerald-800",
      };
  }
}

function heroCopy(center: DashboardCommandCenter) {
  const investorProfile = center.investor_profile ?? null;
  const primary = primaryItem(center);
  if (!primary) {
    return {
      eyebrow: heroEyebrow(null),
      title: "Quiet right now.",
      body:
        investorProfile === "hearsay_driven"
          ? "Nothing needs you right now. Use the quiet to clarify one unclear reason before the market asks harder questions."
          : investorProfile === "thesis_driven"
            ? "Nothing needs you right now. Use the quiet to clarify one unclear thesis before the market asks harder questions."
            : "Nothing needs you right now. Use the quiet to clarify one unclear reason before the market asks harder questions.",
      href: "/dashboard",
      cta: "Scan positions",
      assumption: null as string | null,
    };
  }

  const { section, item } = primary;
  const ticker = cleanTicker(item.holding.ticker);
  const assumption = item.assumption_label
    ? formatAssumptionLabel(item.assumption_label, investorProfile, {
        maxLength: 56,
        sentenceCaseFallback: true,
      })
    : null;

  if (section.kind === "needs_review") {
    return {
      eyebrow: heroEyebrow(section.kind),
      title: `${ticker} needs your read.`,
      body: item.workflow_reason,
      href: item.primary_cta_href,
      cta: heroCta(section.kind, item.primary_cta_label, ticker),
      assumption,
    };
  }

  if (section.kind === "unclear_theses") {
    const unclearCopy = unclearStateCopy(item, investorProfile);
    return {
      eyebrow: heroEyebrow(section.kind),
      title: `${unclearCopy.titleVerb} ${ticker} first.`,
      body: unclearCopy.body,
      href: item.primary_cta_href,
      cta: heroCta(section.kind, unclearCopy.cta, ticker),
      assumption,
    };
  }

  if (section.kind === "decision_debt") {
    return {
      eyebrow: heroEyebrow(section.kind),
      title: `${ticker} still needs a follow-up.`,
      body: item.open_loop_detail || item.workflow_reason,
      href: item.primary_cta_href,
      cta: heroCta(section.kind, item.primary_cta_label, ticker),
      assumption,
    };
  }

  return {
    eyebrow: heroEyebrow(section.kind),
    title: `${ticker} is holding up.`,
    body: item.supporting_summary || item.workflow_reason,
    href: item.primary_cta_href || positionDetailHref(item.holding.ticker),
    cta: heroCta(section.kind, item.primary_cta_label, ticker),
    assumption,
  };
}

function watchlistLabel(
  item: DashboardCommandCenter["sections"][number]["items"][number],
  investorProfile: DashboardCommandCenter["investor_profile"] | null | undefined,
) {
  if (item.workflow_state === "no_thesis") {
    return investorProfile === "hearsay_driven" ? "Write reason" : "Write thesis";
  }
  if (item.workflow_state === "signals_unconfirmed") return "Confirm signals";
  if (item.workflow_state === "draft_ready") return "Review draft";
  if (item.workflow_state === "decision_needed") return "Review now";
  if (item.workflow_state === "pressure_building") return "Needs attention";
  if (item.workflow_state === "review_due") return "Refresh";
  if (item.case_quality === "weak") return "Needs clarity";
  if (item.case_quality === "workable") return "Can sharpen";
  return "Calm";
}

function showQueueBadge(
  item: DashboardCommandCenter["sections"][number]["items"][number],
) {
  if (item.workflow_state === "draft_ready") return false;
  if (item.workflow_state === "signals_unconfirmed") return false;
  if (item.workflow_state === "no_thesis") return false;
  if (item.case_quality === "review_overdue") return false;
  if (item.case_quality === "weak") return false;
  if (item.case_quality === "workable") return false;
  return true;
}

function queueCountLabel(total: number, shown: number) {
  if (total <= shown) {
    return `${shown} up next`;
  }
  return `${shown} of ${total} up next`;
}

export function CommandCenterHero({
  center,
}: {
  center: DashboardCommandCenter;
}) {
  const primary = primaryItem(center);
  const tone = stateTone(primary?.section.kind ?? null);
  const copy = heroCopy(center);
  const queue = queueItems(center, primary);
  const queuePreview = queue.slice(0, 2);

  return (
    <section className={cn("product-panel border px-5 py-5 sm:px-6 sm:py-6", tone.panel)}>
      <div className="space-y-5">
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <span className={cn("border px-2 py-1 font-mono text-[10px] uppercase tracking-[0.18em]", tone.pill)}>
              {copy.eyebrow}
            </span>
            {copy.assumption && (
              <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-foreground/45">
                {copy.assumption}
              </span>
            )}
          </div>
          <h2 className="max-w-2xl font-display text-[1.75rem] italic leading-tight text-foreground sm:text-[2.15rem]">
            {copy.title}
          </h2>
          <p className="max-w-2xl font-sans text-sm leading-relaxed text-foreground/82">
            {copy.body}
          </p>
        </div>

        <Link
          href={copy.href}
          className="inline-flex items-center gap-2 border border-primary/25 bg-background/70 px-3 py-2 font-mono text-[10px] uppercase tracking-[0.16em] text-primary transition-colors hover:border-primary/50"
        >
          {copy.cta}
          <ArrowRight className="h-3.5 w-3.5" />
        </Link>

        {queuePreview.length > 0 && (
          <div className="space-y-3 border-t border-border/50 pt-4">
            <div className="flex items-center justify-between gap-3">
              <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                Next in queue
              </p>
              <span className="font-mono text-[10px] text-muted-foreground">
                {queueCountLabel(queue.length, queuePreview.length)}
              </span>
            </div>
            <div className="grid gap-2 lg:max-w-[32rem]">
              {queuePreview.map((item) => (
                <Link
                  key={item.holding.id}
                  href={item.primary_cta_href || positionDetailHref(item.holding.ticker)}
                  className="flex items-start justify-between gap-3 border border-border/70 bg-background/72 px-3 py-3 transition-colors hover:border-foreground/20"
                >
                  <div className="min-w-0 space-y-1">
                    <p className="font-sans text-sm text-foreground">
                      <span className="font-medium">{cleanTicker(item.holding.ticker)}</span>
                    </p>
                    <p className="line-clamp-1 font-sans text-xs leading-relaxed text-muted-foreground">
                      {queueSubline(item, center.investor_profile)}
                    </p>
                  </div>
                  {showQueueBadge(item) && (
                    <span className="shrink-0 font-mono text-[10px] uppercase tracking-[0.16em] text-foreground/45">
                      {watchlistLabel(item, center.investor_profile)}
                    </span>
                  )}
                </Link>
              ))}
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
