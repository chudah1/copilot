"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { getErrorMessage } from "@/lib/errors";
import { formatCurrency, formatPercent } from "@/lib/utils";
import { HoldingsTable } from "@/components/portfolio/holdings-table";
import { AllocationChart } from "@/components/portfolio/allocation-chart";
import { QuickAddHolding } from "@/components/portfolio/quick-add-holding";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { Holding, PortfolioSummary, Thesis, PortfolioPulse } from "@/types";

export default function DashboardPage() {
  const [holdings, setHoldings] = useState<Holding[]>([]);
  const [currentTheses, setCurrentTheses] = useState<Thesis[]>([]);
  const [summary, setSummary] = useState<PortfolioSummary | null>(null);
  const [pulse, setPulse] = useState<PortfolioPulse | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const [showHealth, setShowHealth] = useState(false);

  const fetchDashboardData = () =>
    Promise.all([
      api.get<Holding[]>("/api/portfolio/holdings"),
      api.get<PortfolioSummary>("/api/portfolio/summary"),
      api.get<Thesis[]>("/api/theses/current"),
      api.get<PortfolioPulse>("/api/portfolio/pulse"),
    ]);

  const refreshDashboard = async () => {
    const [h, s, t, p] = await fetchDashboardData();
    setHoldings(h);
    setSummary(s);
    setCurrentTheses(t);
    setPulse(p);
  };

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      try {
        const [h, s, t, p] = await fetchDashboardData();
        if (cancelled) return;
        setHoldings(h);
        setSummary(s);
        setCurrentTheses(t);
        setPulse(p);
        setLoadError(null);

        try {
          const enriched = await api.post<Holding[]>("/api/portfolio/holdings/enrich", {});
          if (!cancelled && enriched && enriched.length > 0) {
            const [nextHoldings, nextSummary, nextTheses, nextPulse] = await fetchDashboardData();
            if (cancelled) return;
            setHoldings(nextHoldings);
            setSummary(nextSummary);
            setCurrentTheses(nextTheses);
            setPulse(nextPulse);
          }
        } catch {
          // Background enrichment is optional for the initial dashboard render.
        }
      } catch (err) {
        if (cancelled) return;
        console.error("Failed to load portfolio", err);
        setLoadError(getErrorMessage(err, "Failed to load portfolio"));
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    void load();

    return () => {
      cancelled = true;
    };
  }, []);

  const thesesByHolding = Object.fromEntries(currentTheses.map((thesis) => [thesis.holding_id, thesis]));
  const pulseByHolding = Object.fromEntries((pulse?.pulses ?? []).map((p) => [p.holding_id, p]));

  if (loading) return <p className="py-20 text-center text-muted-foreground">Loading...</p>;

  if (loadError && holdings.length === 0) {
    return (
      <div className="space-y-4 py-16">
        <Card>
          <CardHeader>
            <CardTitle>Dashboard unavailable</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-muted-foreground">{loadError}</p>
            <Button onClick={() => void refreshDashboard()}>Retry</Button>
          </CardContent>
        </Card>
      </div>
    );
  }

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
            <QuickAddHolding onAdd={() => { setShowAddForm(false); void refreshDashboard(); }} />
          </div>
        )}
      </div>
    );
  }

  // Attention items
  const attentionItems = summary?.attention_queue ?? [];
  const reviewCount = pulse?.pulses.filter((p) => p.pulse_status === "review").length ?? 0;
  const watchCount = pulse?.pulses.filter((p) => p.pulse_status === "watch").length ?? 0;
  const missingThesisCount = summary?.theses_missing ?? 0;
  const monitorablePct = summary?.monitorable_thesis_coverage_pct ?? 0;
  const nextAction = attentionItems[0]
    ? {
        title: `${attentionItems[0].ticker} needs attention`,
        body: attentionItems[0].reason,
        href: `/dashboard/positions/${attentionItems[0].ticker}`,
        badge: attentionItems[0].priority,
      }
    : reviewCount > 0
      ? {
          title: `${reviewCount} holding${reviewCount === 1 ? "" : "s"} need review`,
          body: "Start with the positions where monitoring believes your thesis may have changed.",
          href: "/dashboard",
          badge: "review",
        }
      : missingThesisCount > 0
        ? {
            title: `${missingThesisCount} holding${missingThesisCount === 1 ? "" : "s"} still need a thesis`,
            body: "Write the missing reasons first so monitoring has something explicit to watch.",
            href: "/dashboard",
            badge: "setup",
          }
        : {
            title: "Your portfolio is calm",
            body: "No urgent thesis breaks are showing up right now. You can review portfolio health only if you want more context.",
            href: null,
            badge: "clear",
          };

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

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Core loop</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-[1.1fr_0.9fr]">
          <div className="rounded-xl border p-4">
            <div className="flex items-center gap-2">
              <p className="font-medium">{nextAction.title}</p>
              <Badge variant="outline">{nextAction.badge}</Badge>
            </div>
            <p className="mt-2 text-sm text-muted-foreground">{nextAction.body}</p>
            {nextAction.href && nextAction.href !== "/dashboard" && (
              <Link href={nextAction.href} className="mt-4 inline-block text-sm text-primary underline-offset-4 hover:underline">
                Open that position
              </Link>
            )}
          </div>

          <div className="grid gap-3 sm:grid-cols-3">
            <LoopStat
              step="Step 1"
              title="Write theses"
              value={missingThesisCount === 0 ? "Done" : `${missingThesisCount} missing`}
              tone={missingThesisCount === 0 ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-800"}
            />
            <LoopStat
              step="Step 2"
              title="Confirm signals"
              value={`${monitorablePct.toFixed(0)}% monitorable`}
              tone={monitorablePct >= 60 ? "bg-emerald-100 text-emerald-800" : "bg-stone-200 text-stone-800"}
            />
            <LoopStat
              step="Step 3"
              title="Review evidence"
              value={reviewCount > 0 ? `${reviewCount} due` : watchCount > 0 ? `${watchCount} watch` : "Up to date"}
              tone={reviewCount > 0 ? "bg-amber-100 text-amber-800" : "bg-sky-100 text-sky-800"}
            />
          </div>
        </CardContent>
      </Card>

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
              <QuickAddHolding onAdd={() => { setShowAddForm(false); void refreshDashboard(); }} />
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

function LoopStat({
  step,
  title,
  value,
  tone,
}: {
  step: string;
  title: string;
  value: string;
  tone: string;
}) {
  return (
    <div className="rounded-xl border p-3">
      <p className="text-[11px] uppercase tracking-wide text-muted-foreground">{step}</p>
      <p className="mt-1 font-medium">{title}</p>
      <Badge className={`mt-3 ${tone}`}>{value}</Badge>
    </div>
  );
}
