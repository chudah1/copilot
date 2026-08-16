"use client";

import { Badge } from "@/components/ui/badge";
import { InfoTip } from "@/components/ui/info-tip";
import { formatCurrency } from "@/lib/utils";
import type { HealthCheckResult } from "@/types";

const ASSESSMENT_CONFIG = {
  all_clear: { label: "All clear", className: "bg-emerald-500/15 text-emerald-700" },
  watch: { label: "Watch", className: "bg-amber-500/15 text-amber-700" },
  review_needed: { label: "Review needed", className: "bg-red-500/15 text-red-600" },
} as const;

const SEVERITY_COLORS: Record<string, string> = {
  thesis_breaking: "text-red-600",
  warning: "text-amber-700",
  info: "text-sky-700",
};

function formatLargeNumber(n: number): string {
  if (n >= 1_000_000_000_000) return `$${(n / 1_000_000_000_000).toFixed(1)}T`;
  if (n >= 1_000_000_000) return `$${(n / 1_000_000_000).toFixed(1)}B`;
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  return `$${n.toLocaleString()}`;
}

export function ThesisHealthCheck({
  result,
  loading,
  investorProfile,
}: {
  result: HealthCheckResult | null;
  loading: boolean;
  investorProfile?: "thesis_driven" | "hearsay_driven" | null;
}) {
  const copy = investorProfile === "thesis_driven"
    ? {
        title: "Thesis check",
        loading: "Checking your thesis against live market data...",
        conditions: "Your assumptions",
        findings: "What we found",
        empty: "Nothing jumped out. Your assumptions still look intact.",
      }
    : investorProfile === "hearsay_driven"
      ? {
          title: "Reason check",
          loading: "Checking whether your reason still lines up with live market data...",
          conditions: "What must stay true",
          findings: "What we found",
          empty: "Nothing jumped out. The reason you wrote still looks intact.",
        }
      : {
          title: "Reason check",
          loading: "Checking your reason against live market data...",
          conditions: "What must stay true",
          findings: "What we found",
          empty: "Nothing jumped out. Your reason still looks intact.",
        };
  if (loading) {
    return (
      <div className="product-panel p-5 sm:p-6">
        <div className="space-y-2">
          <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
            {copy.title}
          </p>
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-amber-400" />
            {copy.loading}
          </div>
        </div>
      </div>
    );
  }

  if (!result) return null;

  const checksOnly = result.candidates.length === 0 && result.watch_hints_status.length > 0;
  const assessment = ASSESSMENT_CONFIG[result.thesis_assessment] ?? ASSESSMENT_CONFIG.all_clear;
  const breachedHints = result.watch_hints_status.filter((w) => w.breached);
  const healthyHints = result.watch_hints_status.filter((w) => !w.breached);

  return (
    <div className="product-panel overflow-hidden">
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-3 border-b border-border/40 p-5 sm:p-6">
        <div className="min-w-0 flex-1 basis-56 space-y-1">
          <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
            {copy.title}
          </p>
          <p className="font-sans text-sm leading-relaxed text-foreground/80">
            {checksOnly
              ? "Baseline market conditions checked against your reason."
              : "Live data checked against your reason."}
          </p>
        </div>
        <Badge className={`${assessment.className} shrink-0`}>
          {checksOnly ? "Conditions hold" : assessment.label}
        </Badge>
      </div>

      <div className="space-y-5 p-5 sm:p-6">
        <div className="grid grid-cols-2 gap-3 text-sm">
          {result.current_price != null && (
            <div className="min-w-0 border border-border/60 bg-background/70 p-3">
              <p className="truncate font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">Price</p>
              <p className="mt-2 truncate font-display text-[1.15rem] italic leading-none text-foreground">
                {formatCurrency(result.current_price, result.currency)}
              </p>
            </div>
          )}
          {result.sector && (
            <div className="min-w-0 border border-border/60 bg-background/70 p-3">
              <p className="truncate font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">Sector</p>
              <p className="mt-2 truncate font-sans text-sm leading-none text-foreground" title={result.sector}>
                {result.sector}
              </p>
            </div>
          )}
          {result.pe_ratio != null && (
            <div className="min-w-0 border border-border/60 bg-background/70 p-3">
              <div className="flex items-center gap-1">
                <p className="truncate font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">P/E ratio</p>
                <InfoTip label="P/E ratio" align="center">
                  Share price divided by annual earnings per share. A higher number means investors are paying more for each unit of current earnings.
                </InfoTip>
              </div>
              <p className="mt-2 truncate font-display text-[1.15rem] italic leading-none text-foreground">
                {result.pe_ratio.toFixed(1)}
              </p>
            </div>
          )}
          {result.market_cap != null && (
            <div className="min-w-0 border border-border/60 bg-background/70 p-3">
              <p className="truncate font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">Market cap</p>
              <p className="mt-2 truncate font-display text-[1.15rem] italic leading-none text-foreground">
                {formatLargeNumber(result.market_cap)}
              </p>
            </div>
          )}
        </div>

        {result.watch_hints_status.length > 0 && (
          <div>
            <p className="mb-3 font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
              {copy.conditions}
            </p>
            <div className="space-y-2">
              {breachedHints.map((hint, i) => (
                <div key={i} className="border border-red-500/20 bg-red-500/8 px-3 py-3">
                  <div>
                    <p className="font-sans text-sm leading-relaxed text-red-600">
                      {hint.metric.replace(/_/g, " ")} is {hint.actual_value.toFixed(2)}
                    </p>
                    <p className="mt-1 text-xs text-red-600/70">
                      Expected {hint.operator} {hint.threshold}
                    </p>
                    {hint.rationale && <p className="mt-2 text-xs leading-relaxed text-red-600/60">{hint.rationale}</p>}
                  </div>
                </div>
              ))}
              {healthyHints.map((hint, i) => (
                <div key={i} className="border border-emerald-500/20 bg-emerald-500/8 px-3 py-3">
                  <p className="font-sans text-sm leading-relaxed text-emerald-700">
                    {hint.metric.replace(/_/g, " ")} is {hint.actual_value.toFixed(2)} ({hint.operator} {hint.threshold})
                  </p>
                </div>
              ))}
            </div>
          </div>
        )}

        {result.candidates.length > 0 && (
          <div>
            <p className="mb-3 font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
              {copy.findings}
            </p>
            <div className="space-y-2">
              {result.candidates.map((c, i) => {
                // The AI analysis often opens by restating the description
                // verbatim — strip that prefix so the card doesn't say the
                // same thing twice.
                const description = c.description?.trim() ?? "";
                const rawAnalysis = c.ai_analysis?.trim() ?? "";
                const analysis = description && rawAnalysis.startsWith(description)
                  ? rawAnalysis.slice(description.length).trim()
                  : rawAnalysis;
                return (
                  <div key={i} className="border border-border/60 bg-background/70 px-3 py-3">
                    <div className="flex items-center gap-2">
                      <span className={`font-mono text-[10px] uppercase tracking-[0.16em] ${SEVERITY_COLORS[c.severity ?? "info"] ?? "text-muted-foreground"}`}>
                        {c.event_type.replace(/_/g, " ")}
                      </span>
                      {c.severity && (
                        <Badge variant="outline" className="text-[10px]">
                          {c.severity.replace(/_/g, " ")}
                        </Badge>
                      )}
                    </div>
                    <p className="mt-2 font-sans text-sm leading-relaxed text-foreground/90">{description}</p>
                    {analysis && (
                      <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">{analysis}</p>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {result.candidates.length === 0 && result.watch_hints_status.length === 0 && (
          <p className="text-sm text-muted-foreground">
            {copy.empty}
          </p>
        )}

        {checksOnly && (
          <p className="text-sm text-muted-foreground">
            No fresh event, filing, or earnings signal was flagged in this pass. This only confirms the numeric conditions we could test today.
          </p>
        )}

        <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 border-t border-border/40 pt-4 text-xs text-muted-foreground">
          <span>
            {result.watch_hints_status.length + result.candidates.length} check
            {result.watch_hints_status.length + result.candidates.length !== 1 ? "s" : ""} in this pass
            {" · "}
            {result.recent_news_count} recent news article{result.recent_news_count !== 1 ? "s" : ""}
          </span>
          {result.upcoming_earnings_date && (
            <span>Next earnings: {new Date(result.upcoming_earnings_date).toLocaleDateString()}</span>
          )}
        </div>
      </div>
    </div>
  );
}
