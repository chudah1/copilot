"use client";

import type { PortfolioTrend, PortfolioSummary } from "@/types";

interface SinceLastVisitProps {
  summary: PortfolioSummary;
  trend: PortfolioTrend | null;
}

export function SinceLastVisit({ summary, trend }: SinceLastVisitProps) {
  if (!trend || !trend.snapshot_date) return null;

  const snapshotDate = new Date(trend.snapshot_date);
  const daysAgo = Math.max(1, Math.floor((Date.now() - snapshotDate.getTime()) / (1000 * 60 * 60 * 24)));
  const daysLabel = daysAgo === 1 ? "1d ago" : `${daysAgo}d ago`;

  const changes: string[] = [];

  if (trend.new_event_count > 0) {
    changes.push(`${trend.new_event_count} evidence item${trend.new_event_count !== 1 ? "s" : ""} checked`);
  }

  if (trend.holdings_count != null && summary.holdings_count !== trend.holdings_count) {
    const diff = summary.holdings_count - trend.holdings_count;
    changes.push(`${diff > 0 ? "+" : ""}${diff} holding${Math.abs(diff) !== 1 ? "s" : ""}`);
  }

  if (summary.theses_need_review > 0) {
    changes.push(`${summary.theses_need_review} thesis${summary.theses_need_review !== 1 ? "es" : ""} need review`);
  }

  if (changes.length === 0) {
    return null;
  }

  return (
    <div className="product-panel border-emerald-500/25 bg-emerald-500/8 px-4 py-3">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div className="space-y-1">
          <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-emerald-700/80">
            Since last visit
          </p>
          <p className="font-sans text-sm leading-relaxed text-foreground/80">
            Here&apos;s what changed across the portfolio since {daysLabel}.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {changes.map((change) => (
            <span
              key={change}
              className="border border-emerald-600/15 bg-background/70 px-2.5 py-1 font-mono text-[10px] uppercase tracking-[0.12em] text-emerald-700/85"
            >
              {change}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
