"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
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
          loading: "Checking whether your written reason still lines up with live market data...",
          conditions: "What must stay true",
          findings: "What we found",
          empty: "Nothing jumped out. The reason you wrote still looks intact.",
        }
      : {
          title: "Reality Check",
          loading: "Checking your thesis against live market data...",
          conditions: "Your conditions",
          findings: "What we found",
          empty: "Nothing jumped out. Your conditions still look intact.",
        };
  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base">{copy.title}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-amber-400" />
            {copy.loading}
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!result) return null;

  const assessment = ASSESSMENT_CONFIG[result.thesis_assessment] ?? ASSESSMENT_CONFIG.all_clear;
  const breachedHints = result.watch_hints_status.filter((w) => w.breached);
  const healthyHints = result.watch_hints_status.filter((w) => !w.breached);

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">{copy.title}</CardTitle>
          <Badge className={assessment.className}>{assessment.label}</Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Snapshot row */}
        <div className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
          {result.current_price != null && (
            <div>
              <p className="text-muted-foreground">Price</p>
              <p className="font-semibold">${result.current_price.toFixed(2)}</p>
            </div>
          )}
          {result.sector && (
            <div>
              <p className="text-muted-foreground">Sector</p>
              <p className="font-semibold">{result.sector}</p>
            </div>
          )}
          {result.pe_ratio != null && (
            <div>
              <p className="text-muted-foreground">P/E</p>
              <p className="font-semibold">{result.pe_ratio.toFixed(1)}</p>
            </div>
          )}
          {result.market_cap != null && (
            <div>
              <p className="text-muted-foreground">Market Cap</p>
              <p className="font-semibold">{formatLargeNumber(result.market_cap)}</p>
            </div>
          )}
        </div>

        {/* Watch hints */}
        {result.watch_hints_status.length > 0 && (
          <div>
            <p className="mb-2 text-sm font-medium">{copy.conditions}</p>
            <div className="space-y-1.5">
              {breachedHints.map((hint, i) => (
                <div key={i} className="flex items-start gap-2 rounded-md bg-red-500/10 border border-red-500/20 px-3 py-2 text-sm">
                  <span className="mt-0.5 text-red-600">&#x2717;</span>
                  <div>
                    <span className="font-medium text-red-600">
                      {hint.metric.replace(/_/g, " ")} is {hint.actual_value.toFixed(2)}
                    </span>
                    <span className="text-red-600/70"> (expected {hint.operator} {hint.threshold})</span>
                    {hint.rationale && <p className="mt-0.5 text-xs text-red-600/60">{hint.rationale}</p>}
                  </div>
                </div>
              ))}
              {healthyHints.map((hint, i) => (
                <div key={i} className="flex items-start gap-2 rounded-md bg-emerald-500/10 border border-emerald-500/20 px-3 py-2 text-sm">
                  <span className="mt-0.5 text-emerald-700">&#x2713;</span>
                  <span className="text-emerald-700">
                    {hint.metric.replace(/_/g, " ")} is {hint.actual_value.toFixed(2)} ({hint.operator} {hint.threshold})
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Monitoring candidates */}
        {result.candidates.length > 0 && (
          <div>
            <p className="mb-2 text-sm font-medium">{copy.findings}</p>
            <div className="space-y-2">
              {result.candidates.map((c, i) => (
                <div key={i} className="rounded-md border px-3 py-2 text-sm">
                  <div className="flex items-center gap-2">
                    <span className={`font-medium ${SEVERITY_COLORS[c.severity ?? "info"] ?? "text-muted-foreground"}`}>
                      {c.event_type.replace(/_/g, " ")}
                    </span>
                    {c.severity && (
                      <Badge variant="outline" className="text-xs">
                        {c.severity.replace(/_/g, " ")}
                      </Badge>
                    )}
                  </div>
                  <p className="mt-1 text-muted-foreground">{c.description}</p>
                  {c.ai_analysis && <p className="mt-1 text-xs text-muted-foreground/80">{c.ai_analysis}</p>}
                </div>
              ))}
            </div>
          </div>
        )}

        {result.candidates.length === 0 && result.watch_hints_status.length === 0 && (
          <p className="text-sm text-muted-foreground">
            {copy.empty}
          </p>
        )}

        {/* Footer */}
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>{result.recent_news_count} recent news article{result.recent_news_count !== 1 ? "s" : ""}</span>
          {result.upcoming_earnings_date && (
            <span>Next earnings: {new Date(result.upcoming_earnings_date).toLocaleDateString()}</span>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
