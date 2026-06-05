"use client";

import type { PortfolioTrend, PortfolioSummary } from "@/types";

interface SinceLastVisitProps {
  summary: PortfolioSummary;
  trend: PortfolioTrend | null;
  recentEventCount: number;
}

export function SinceLastVisit({ summary, trend, recentEventCount }: SinceLastVisitProps) {
  if (!trend || !trend.snapshot_date) return null;

  const snapshotDate = new Date(trend.snapshot_date);
  const daysAgo = Math.max(1, Math.floor((Date.now() - snapshotDate.getTime()) / (1000 * 60 * 60 * 24)));
  const daysLabel = daysAgo === 1 ? "1d ago" : `${daysAgo}d ago`;

  const changes: string[] = [];

  if (recentEventCount > 0) {
    changes.push(`${recentEventCount} new event${recentEventCount !== 1 ? "s" : ""}`);
  }

  if (trend.holdings_count != null && summary.holdings_count !== trend.holdings_count) {
    const diff = summary.holdings_count - trend.holdings_count;
    changes.push(`${diff > 0 ? "+" : ""}${diff} holding${Math.abs(diff) !== 1 ? "s" : ""}`);
  }

  if (summary.theses_need_review > 0) {
    changes.push(`${summary.theses_need_review} thesis${summary.theses_need_review !== 1 ? "es" : ""} need review`);
  }

  if (changes.length === 0) {
    changes.push("No meaningful change");
  }

  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-lg border border-emerald-500/25 bg-emerald-500/8 px-4 py-2.5 text-emerald-700">
      <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-emerald-700/80">
        Since {daysLabel}
      </span>
      <span className="font-sans text-sm">
        {changes.join(" · ")}
      </span>
    </div>
  );
}
