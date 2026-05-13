"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { formatCurrency, formatPercent } from "@/lib/utils";
import { HoldingsTable } from "@/components/portfolio/holdings-table";
import { AllocationChart } from "@/components/portfolio/allocation-chart";
import { ThesisHealthSummary } from "@/components/thesis/thesis-health-summary";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { Holding, PortfolioSummary, Thesis } from "@/types";

function formatPlainPercent(value: number) {
  return `${value.toFixed(0)}%`;
}

export default function DashboardPage() {
  const [holdings, setHoldings] = useState<Holding[]>([]);
  const [currentTheses, setCurrentTheses] = useState<Thesis[]>([]);
  const [summary, setSummary] = useState<PortfolioSummary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const [h, s, t] = await Promise.all([
          api.get<Holding[]>("/api/portfolio/holdings"),
          api.get<PortfolioSummary>("/api/portfolio/summary"),
          api.get<Thesis[]>("/api/theses/current"),
        ]);
        setHoldings(h);
        setSummary(s);
        setCurrentTheses(t);
      } catch (err) {
        console.error("Failed to load portfolio", err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const thesesByHolding = Object.fromEntries(currentTheses.map((thesis) => [thesis.holding_id, thesis]));

  if (loading) return <p>Loading portfolio...</p>;

  if (holdings.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-20">
        <h2 className="text-xl font-semibold">No holdings yet</h2>
        <p className="text-muted-foreground">Connect your broker or add positions manually to get started.</p>
        <Link href="/connect">
          <Button>Connect Portfolio</Button>
        </Link>
      </div>
    );
  }

  const observations = summary
    ? [
        {
          title: "Concentration",
          body:
            summary.top_3_concentration_pct >= 50
              ? `Your top 3 positions drive ${formatPlainPercent(summary.top_3_concentration_pct)} of the portfolio.`
              : `Your top 3 positions make up ${formatPlainPercent(summary.top_3_concentration_pct)} of the portfolio.`,
        },
        {
          title: "Thesis coverage",
          body: `${formatPlainPercent(summary.thesis_coverage_pct)} of portfolio value has a current thesis, and ${formatPlainPercent(summary.monitorable_thesis_coverage_pct)} is monitorable today.`,
        },
        {
          title: "Decision debt",
          body:
            summary.unmonitored_holdings_count > 0
              ? `${summary.unmonitored_holdings_count} holdings still lack a clear, monitorable reason for existing.`
              : "Every holding has at least a monitorable reason attached.",
        },
        {
          title: "Conviction mismatch",
          body:
            summary.conviction_mismatch_count > 0
              ? `${summary.conviction_mismatch_count} of your top positions may be too large relative to thesis quality or confidence.`
              : "Your biggest positions do not currently show an obvious confidence mismatch.",
        },
      ]
    : [];

  return (
    <div className="space-y-6">
      {summary && (
        <>
          <Card className="border-0 bg-[linear-gradient(135deg,rgba(10,20,24,0.96),rgba(26,51,44,0.92)_55%,rgba(208,224,212,0.96))] text-white ring-0">
            <CardHeader className="gap-3">
              <div className="flex flex-wrap items-center gap-2">
                <Badge className="bg-white/12 text-white backdrop-blur">Accountability-first investing</Badge>
                <Badge className="bg-emerald-200/20 text-emerald-50 backdrop-blur">
                  {summary.attention_queue.length > 0 ? `${summary.attention_queue.length} positions need attention` : "No urgent thesis breaks"}
                </Badge>
              </div>
              <CardTitle className="max-w-3xl text-3xl font-semibold tracking-tight text-white">
                Your portfolio is being watched against your own beliefs, not generic market noise.
              </CardTitle>
              <CardDescription className="max-w-2xl text-white/80">
                We decode concentration, thesis quality, and review debt so you know where your next best decision lives.
              </CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4 md:grid-cols-3">
              <div className="rounded-2xl border border-white/12 bg-white/8 p-4 backdrop-blur">
                <p className="text-sm text-white/70">First place to look</p>
                <p className="mt-2 text-xl font-semibold">
                  {summary.attention_queue[0]?.ticker ?? "Portfolio looks steady"}
                </p>
                <p className="mt-1 text-sm text-white/75">
                  {summary.attention_queue[0]?.reason ?? "Nothing urgent right now. Keep tightening thesis quality over time."}
                </p>
              </div>
              <div className="rounded-2xl border border-white/12 bg-white/8 p-4 backdrop-blur">
                <p className="text-sm text-white/70">Monitorable value</p>
                <p className="mt-2 text-xl font-semibold">{formatPlainPercent(summary.monitorable_thesis_coverage_pct)}</p>
                <p className="mt-1 text-sm text-white/75">of your portfolio can be actively watched against a clear thesis.</p>
              </div>
              <div className="rounded-2xl border border-white/12 bg-white/8 p-4 backdrop-blur">
                <p className="text-sm text-white/70">Decision debt</p>
                <p className="mt-2 text-xl font-semibold">{summary.unmonitored_holdings_count}</p>
                <p className="mt-1 text-sm text-white/75">holdings still need a cleaner reason before monitoring becomes trustworthy.</p>
              </div>
            </CardContent>
            <CardContent className="pt-0">
              <div className={`rounded-2xl border px-4 py-3 text-sm ${summary.monitoring_ready ? "border-emerald-200/20 bg-emerald-200/10 text-emerald-50" : "border-amber-200/20 bg-amber-200/10 text-amber-50"}`}>
                {summary.monitoring_message}
              </div>
            </CardContent>
          </Card>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">Portfolio Value</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-bold">{formatCurrency(summary.total_value)}</p>
                <p className={`text-sm ${summary.total_pnl >= 0 ? "text-green-600" : "text-red-600"}`}>
                  {formatCurrency(summary.total_pnl)} ({formatPercent(summary.total_pnl_pct)})
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">Top 3 Concentration</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-bold">{formatPlainPercent(summary.top_3_concentration_pct)}</p>
                <p className="text-sm text-muted-foreground">how much your biggest bets drive the portfolio</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">Thesis Coverage</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-bold">{formatPlainPercent(summary.thesis_coverage_pct)}</p>
                <p className="text-sm text-muted-foreground">of value has a current thesis</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">Need Attention</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-bold text-orange-500">{summary.attention_queue.length}</p>
                <p className="text-sm text-muted-foreground">positions to review first</p>
              </CardContent>
            </Card>
          </div>

          <ThesisHealthSummary summary={summary} />

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Your Portfolio, Decoded</CardTitle>
                <CardDescription>Immediate value after upload: what is concentrated, vague, stale, or oversized.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {observations.map((item) => (
                  <div key={item.title} className="space-y-1">
                    <p className="text-sm font-medium">{item.title}</p>
                    <p className="text-sm text-muted-foreground">{item.body}</p>
                  </div>
                ))}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Attention Queue</CardTitle>
                <CardDescription>Start here before looking at the rest of the portfolio.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {summary.attention_queue.length === 0 ? (
                  <p className="text-sm text-muted-foreground">Nothing urgent right now. Your current theses look reasonably healthy.</p>
                ) : (
                  summary.attention_queue.map((item) => (
                    <div key={item.holding_id} className="rounded-lg border p-3">
                      <div className="flex items-center justify-between gap-3">
                        <div>
                          <p className="font-medium">{item.ticker}</p>
                          <p className="text-sm text-muted-foreground">{item.name}</p>
                        </div>
                        <Link href={`/dashboard/positions/${item.ticker}`} className="text-sm font-medium text-primary underline-offset-4 hover:underline">
                          Review
                        </Link>
                      </div>
                      <p className="mt-2 text-sm text-muted-foreground">{item.reason}</p>
                    </div>
                  ))
                )}
              </CardContent>
            </Card>
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <AllocationChart title="Sector Allocation" breakdown={summary.sector_breakdown} />
            <AllocationChart title="Geography Allocation" breakdown={summary.geography_breakdown} />
          </div>
        </>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Holdings</CardTitle>
          <CardDescription>Click a position to capture the thesis, review monitoring events, or tighten a vague reason.</CardDescription>
        </CardHeader>
        <CardContent>
          <HoldingsTable holdings={holdings} currentThesesByHolding={thesesByHolding} />
        </CardContent>
      </Card>
    </div>
  );
}
