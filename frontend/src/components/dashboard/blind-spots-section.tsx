"use client";

import Link from "next/link";
import { ArrowRight } from "lucide-react";
import type { DashboardBlindSpot, DashboardWorkspace } from "@/types";
import { cleanTicker } from "@/components/portfolio/position-card";
import { positionBlindSpotHref, positionDetailHref } from "@/lib/position-links";
import { cn } from "@/lib/utils";

function investorNoun(investorProfile: DashboardWorkspace["investor_profile"]) {
  if (investorProfile === "hearsay_driven") return "reason";
  if (investorProfile === "thesis_driven") return "thesis";
  return "reason";
}

function titleCase(value: string) {
  return `${value.slice(0, 1).toUpperCase()}${value.slice(1)}`;
}

function blindSpotTone(kind: DashboardBlindSpot["blind_spot_kind"]) {
  switch (kind) {
    case "missing":
      return {
        panel: "border-amber-500/25 bg-amber-500/[0.07]",
        chip: "border-amber-600/20 bg-amber-600/10 text-amber-800",
      };
    case "review_overdue":
      return {
        panel: "border-sky-500/25 bg-sky-500/[0.06]",
        chip: "border-sky-600/20 bg-sky-600/10 text-sky-800",
      };
    default:
      return {
        panel: "border-border/70 bg-background/55",
        chip: "border-border bg-background text-foreground/70",
      };
  }
}

function blindSpotLabel(
  kind: DashboardBlindSpot["blind_spot_kind"],
  investorProfile: DashboardWorkspace["investor_profile"],
) {
  const noun = investorNoun(investorProfile);
  switch (kind) {
    case "missing":
      return `No ${noun} yet`;
    case "weak":
      return "Needs clarity";
    case "review_overdue":
      return "Refresh due";
    default:
      return "Can sharpen";
  }
}

function blindSpotCta(
  blindSpot: DashboardBlindSpot,
  investorProfile: DashboardWorkspace["investor_profile"],
) {
  const noun = investorNoun(investorProfile);
  switch (blindSpot.blind_spot_kind) {
    case "missing":
      return investorProfile === "hearsay_driven" ? "Write reason" : "Write thesis";
    case "review_overdue":
      return `Refresh ${noun}`;
    default:
      return `Clarify ${noun}`;
  }
}

function cadenceLine(blindSpot: DashboardBlindSpot) {
  if (blindSpot.days_since_thesis_update == null || blindSpot.review_cadence_days == null) {
    return null;
  }

  return `${blindSpot.days_since_thesis_update}d old · revisit every ${blindSpot.review_cadence_days}d`;
}

function sectionHeadline(
  blindSpots: DashboardBlindSpot[],
  investorProfile: DashboardWorkspace["investor_profile"],
) {
  const noun = investorNoun(investorProfile);
  const pluralNoun = noun === "thesis" ? "theses" : "reasons";
  const missingCount = blindSpots.filter((spot) => spot.blind_spot_kind === "missing").length;
  const reviewDueCount = blindSpots.filter((spot) => spot.blind_spot_kind === "review_overdue").length;
  const tightenCount = blindSpots.length - missingCount - reviewDueCount;

  if (blindSpots.length === 1) {
    const kind = blindSpots[0]?.blind_spot_kind;
    if (kind === "missing") return `1 position still needs a ${noun}.`;
    if (kind === "review_overdue") return `1 ${noun} needs a refresh.`;
    return `1 ${noun} needs attention.`;
  }

  if (missingCount === blindSpots.length) return `${missingCount} positions still need a ${noun}.`;
  if (reviewDueCount === blindSpots.length) return `${reviewDueCount} ${pluralNoun} need a refresh.`;
  if (tightenCount === blindSpots.length) return `${tightenCount} ${pluralNoun} still need clarification.`;
  return `${blindSpots.length} need attention.`;
}

export function BlindSpotsSection({
  blindSpots,
  investorProfile,
}: {
  blindSpots: DashboardBlindSpot[];
  investorProfile: DashboardWorkspace["investor_profile"];
}) {
  if (blindSpots.length === 0) {
    return null;
  }

  return (
    <section className="product-panel p-4 sm:p-5">
      <div className="space-y-2">
        <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
          Needs attention
        </p>
        <h3 className="font-display text-[1.4rem] italic leading-tight text-foreground">
          {sectionHeadline(blindSpots, investorProfile)}
        </h3>
        <p className="max-w-sm font-sans text-sm leading-relaxed text-foreground/72">
          The places where your {investorNoun(investorProfile)} is still missing, due for refresh, or not yet specific enough to lean on.
        </p>
      </div>

      <div className="mt-4 space-y-3">
        {blindSpots.map((blindSpot) => {
          const tone = blindSpotTone(blindSpot.blind_spot_kind);
          return (
            <div key={blindSpot.holding.id} className={cn("border px-3 py-3", tone.panel)}>
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="font-sans text-sm text-foreground">
                    <span className="font-medium">{cleanTicker(blindSpot.holding.ticker)}</span>
                    <span className="text-foreground/55"> · {blindSpot.holding.name}</span>
                  </p>
                  <p className="mt-1 font-sans text-xs leading-relaxed text-muted-foreground">
                    {blindSpot.reason}
                  </p>
                </div>
                <span className={cn("shrink-0 border px-2 py-1 font-mono text-[10px] uppercase tracking-[0.16em]", tone.chip)}>
                  {blindSpotLabel(blindSpot.blind_spot_kind, investorProfile)}
                </span>
              </div>

              <div className="mt-3 flex items-center justify-between gap-3 border-t border-border/60 pt-3">
                <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
                  {cadenceLine(blindSpot) ?? "One condition is still loose"}
                </p>
                <Link
                  href={
                    blindSpot.blind_spot_kind === "missing"
                      ? positionBlindSpotHref(blindSpot.holding.ticker)
                      : positionDetailHref(blindSpot.holding.ticker)
                  }
                  className="inline-flex items-center gap-1.5 border border-primary/25 bg-background/72 px-3 py-2 font-mono text-[10px] uppercase tracking-[0.14em] text-primary transition-colors hover:border-primary/50"
                >
                  {blindSpotCta(blindSpot, investorProfile)}
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
