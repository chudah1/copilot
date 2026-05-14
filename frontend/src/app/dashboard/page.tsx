"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { formatCurrency, formatPercent } from "@/lib/utils";
import { HoldingsTable } from "@/components/portfolio/holdings-table";
import { AllocationChart } from "@/components/portfolio/allocation-chart";
import { QuickAddHolding } from "@/components/portfolio/quick-add-holding";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { Holding, PortfolioSummary, Thesis, PortfolioPulse, PortfolioTrend } from "@/types";

export default function DashboardPage() {
  const [holdings, setHoldings] = useState<Holding[]>([]);
  const [currentTheses, setCurrentTheses] = useState<Thesis[]>([]);
  const [summary, setSummary] = useState<PortfolioSummary | null>(null);
  const [pulse, setPulse] = useState<PortfolioPulse | null>(null);
  const [loading, setLoading] = useState(true);
  const [showAddForm, setShowAddForm] = useState(false);
  const [showHealth, setShowHealth] = useState(false);

  const loadAll = async () => {
    try {
      const [h, s, t, p] = await Promise.all([
        api.get<Holding[]>("/api/portfolio/holdings"),
        api.get<PortfolioSummary>("/api/portfolio/summary"),
        api.get<Thesis[]>("/api/theses/current"),
        api.get<PortfolioPulse>("/api/portfolio/pulse"),
      ]);
      setHoldings(h);
      setSummary(s);
      setCurrentTheses(t);
      setPulse(p);
    } catch (err) {
      console.error("Failed to load portfolio", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAll().then(() => {
      api.post<Holding[]>("/api/portfolio/holdings/enrich", {})
        .then((enriched) => {
          if (enriched && enriched.length > 0) loadAll();
        })
        .catch(() => {});
    });
  }, []);

  const thesesByHolding = Object.fromEntries(currentTheses.map((thesis) => [thesis.holding_id, thesis]));
  const pulseByHolding = Object.fromEntries((pulse?.pulses ?? []).map((p) => [p.holding_id, p]));

  if (loading) return <p className="py-20 text-center text-muted-foreground">Loading...</p>;

  if (holdings.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-20">
        <h2 className="text-xl font-semibold">No holdings yet</h2>
        <p className="text-muted-foreground">Connect your broker or add positions manually to get started.</p>
        <div className="flex gap-3">
          <Link href="/connect">
            <Button>Connect Portfolio</Button>
          </Link>
          <Button variant="outline" onClick={() => setShowAddForm(true)}>Add manually</Button>
        </div>
        {showAddForm && (
          <div className="w-full max-w-lg mt-4">
            <QuickAddHolding onAdd={() => { setShowAddForm(false); loadAll(); }} />
          </div>
        )}
      </div>
    );
  }

  // Attention items
  const attentionItems = summary?.attention_queue ?? [];
  const reviewCount = pulse?.pulses.filter((p) => p.pulse_status === "review").length ?? 0;
  const watchCount = pulse?.pulses.filter((p) => p.pulse_status === "watch").length ?? 0;

  return (
    <div className="space-y-5">
      {/* Header — value + P&L, that's it */}
      {summary && (
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{formatCurrency(summary.total_value)}</h1>
          <p className={`text-sm ${summary.total_pnl >= 0 ? "text-green-600" : "text-red-600"}`}>
            {formatCurrency(summary.total_pnl)} ({formatPercent(summary.total_pnl_pct)}) · {summary.holdings_count} holdings
          </p>
        </div>
      )}

      {/* Attention banner — only shows if something needs attention */}
      {(attentionItems.length > 0 || reviewCount > 0) && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3">
          <div className="space-y-2">
            {attentionItems.map((item) => (
              <Link key={item.holding_id} href={`/dashboard/positions/${item.ticker}`} className="flex items-center justify-between text-sm text-amber-900 hover:underline underline-offset-4">
                <span><span className="font-medium">{item.ticker}</span> — {item.reason}</span>
                <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${
                  item.priority === "critical" ? "bg-red-100 text-red-800" : "bg-amber-100 text-amber-700"
                }`}>{item.priority}</span>
              </Link>
            ))}
            {reviewCount > 0 && attentionItems.length === 0 && (
              <p className="text-sm text-amber-800">
                {reviewCount} holding{reviewCount !== 1 ? "s" : ""} need{reviewCount === 1 ? "s" : ""} review
              </p>
            )}
          </div>
        </div>
      )}

      {/* Holdings — the main event */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Holdings</CardTitle>
            <div className="flex items-center gap-3">
              <Link href="/dashboard/simulate" className="text-sm text-primary hover:underline underline-offset-4">
                Simulate a trade
              </Link>
              <Button size="sm" variant="outline" onClick={() => setShowAddForm(!showAddForm)}>
                {showAddForm ? "Cancel" : "+ Add"}
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {showAddForm && (
            <div className="mb-4">
              <QuickAddHolding onAdd={() => { setShowAddForm(false); loadAll(); }} />
            </div>
          )}
          <HoldingsTable holdings={holdings} currentThesesByHolding={thesesByHolding} pulseByHolding={pulseByHolding} />
        </CardContent>
      </Card>

      {/* Portfolio health — collapsed by default */}
      {summary && (
        <div>
          <button
            onClick={() => setShowHealth(!showHealth)}
            className="text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            {showHealth ? "Hide" : "Show"} portfolio health
          </button>

          {showHealth && (
            <div className="mt-3 space-y-4 animate-in fade-in duration-200">
              {/* Quick stats */}
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <Stat label="Thesis coverage" value={`${summary.thesis_coverage_pct.toFixed(0)}%`} warn={summary.thesis_coverage_pct < 80} />
                <Stat label="Top 3 concentration" value={`${summary.top_3_concentration_pct.toFixed(0)}%`} warn={summary.top_3_concentration_pct >= 50} />
                <Stat label="Monitorable" value={`${summary.monitorable_thesis_coverage_pct.toFixed(0)}%`} warn={summary.monitorable_thesis_coverage_pct < 50} />
                <Stat label="Need thesis" value={String(summary.theses_missing)} warn={summary.theses_missing > 0} />
              </div>

              {/* Allocation */}
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <AllocationChart title="Sector" breakdown={summary.sector_breakdown} />
                <AllocationChart title="Geography" breakdown={summary.geography_breakdown} />
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function Stat({ label, value, warn }: { label: string; value: string; warn: boolean }) {
  return (
    <div className="rounded-lg border p-3">
      <p className="text-[11px] text-muted-foreground">{label}</p>
      <p className={`text-lg font-semibold mt-0.5 ${warn ? "text-amber-600" : ""}`}>{value}</p>
    </div>
  );
}
