"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { getErrorMessage } from "@/lib/errors";
import { formatCurrency, formatDate, formatPercent } from "@/lib/utils";
import { HoldingCard } from "@/components/portfolio/holding-card";
import { PulseStream } from "@/components/portfolio/pulse-stream";
import { QuickAddHolding } from "@/components/portfolio/quick-add-holding";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { Holding, PortfolioSummary, Thesis, PortfolioPulse, QuarterlyReviewCurrent, UpcomingEarnings } from "@/types";
import { toast } from "sonner";
import { motion } from "framer-motion";

export default function DashboardPage() {
  const [holdings, setHoldings] = useState<Holding[]>([]);
  const [currentTheses, setCurrentTheses] = useState<Thesis[]>([]);
  const [summary, setSummary] = useState<PortfolioSummary | null>(null);
  const [pulse, setPulse] = useState<PortfolioPulse | null>(null);
  const [quarterlyReview, setQuarterlyReview] = useState<QuarterlyReviewCurrent | null>(null);
  const [upcomingEarnings, setUpcomingEarnings] = useState<UpcomingEarnings[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [showAddForm, setShowAddForm] = useState(false);

  const fetchDashboardData = () =>
    Promise.all([
      api.get<Holding[]>("/api/portfolio/holdings"),
      api.get<PortfolioSummary>("/api/portfolio/summary"),
      api.get<Thesis[]>("/api/theses/current"),
      api.get<PortfolioPulse>("/api/portfolio/pulse"),
      api.get<UpcomingEarnings[]>("/api/portfolio/upcoming-earnings").catch(() => []),
      api
        .get<QuarterlyReviewCurrent>("/api/quarterly-review/current")
        .catch(() => null),
    ]);

  const refreshDashboard = async () => {
    const [h, s, t, p, upcoming, q] = await fetchDashboardData();
    setHoldings(h);
    setSummary(s);
    setCurrentTheses(t);
    setPulse(p);
    setUpcomingEarnings(upcoming);
    setQuarterlyReview(q);
  };

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      try {
        const [h, s, t, p, upcoming, q] = await fetchDashboardData();
        if (cancelled) return;
        setHoldings(h);
        setSummary(s);
        setCurrentTheses(t);
        setPulse(p);
        setUpcomingEarnings(upcoming);
        setQuarterlyReview(q);
        setLoadError(null);
      } catch (err) {
        if (cancelled) return;
        console.error("Failed to load portfolio", err);
        setLoadError(getErrorMessage(err, "Failed to load portfolio"));
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    void load();
    return () => { cancelled = true; };
  }, []);

  const handleGenerateDraft = async (holdingId: string, ticker: string) => {
    try {
      const draft = await api.post<{why_own_it: string, must_remain_true: string, what_would_change_my_mind: string}>("/api/theses/draft", { ticker });
      
      await api.post("/api/theses", {
        holding_id: holdingId,
        thesis_kind: "company",
        why_own_it: draft.why_own_it,
        must_remain_true: draft.must_remain_true,
        what_would_change_my_mind: draft.what_would_change_my_mind,
        status: "active",
        confidence: "medium",
        source: "ai_assisted",
        review_cadence_days: 30
      });
      
      toast.success(`Draft thesis saved for ${ticker}!`);
      void refreshDashboard();
    } catch (err) {
      toast.error(getErrorMessage(err, "Failed to generate draft"));
    }
  };

  const thesesByHolding = Object.fromEntries(currentTheses.map((thesis) => [thesis.holding_id, thesis]));
  const pulseByHolding = Object.fromEntries((pulse?.pulses ?? []).map((p) => [p.holding_id, p]));
  const earningsByHolding = Object.fromEntries(upcomingEarnings.map((e) => [e.holding_id, e]));
  const reviewCount = (pulse?.pulses ?? []).filter((p) => p.pulse_status === "review").length;
  const watchCount = (pulse?.pulses ?? []).filter((p) => p.pulse_status === "watch").length;
  const pendingQuarterlyCount = quarterlyReview?.pending_count ?? 0;
  const missingThesisCount = summary?.theses_missing ?? 0;
  const allClear =
    holdings.length > 0 &&
    reviewCount === 0 &&
    watchCount === 0 &&
    pendingQuarterlyCount === 0 &&
    missingThesisCount === 0;

  const latestMonitoringCheck = (pulse?.pulses ?? [])
    .map((entry) => entry.last_checked_at)
    .filter((entry): entry is string => Boolean(entry))
    .sort((a, b) => new Date(b).getTime() - new Date(a).getTime())[0] ?? null;

  const latestReasonRefreshDays = (pulse?.pulses ?? [])
    .map((entry) => entry.days_since_thesis_update)
    .filter((days): days is number => days !== null)
    .sort((a, b) => a - b)[0] ?? null;

  const oldestActiveReason = (pulse?.pulses ?? [])
    .filter((entry) => entry.has_thesis && entry.days_since_thesis_update !== null)
    .sort((a, b) => (b.days_since_thesis_update ?? 0) - (a.days_since_thesis_update ?? 0))[0] ?? null;
  const nextEarnings = upcomingEarnings[0] ?? null;

  if (loading) return <div className="py-20 text-center animate-pulse text-stone-400">Syncing portfolio...</div>;

  if (loadError && holdings.length === 0) {
    return (
      <div className="py-16 max-w-md mx-auto text-center">
        <p className="text-stone-500 mb-4">{loadError}</p>
        <Button onClick={() => void refreshDashboard()}>Try Again</Button>
      </div>
    );
  }

  if (holdings.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-6 py-32 text-center">
        <div className="w-16 h-16 bg-stone-100 rounded-full flex items-center justify-center text-2xl mb-2">🌱</div>
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">Welcome to your Copilot</h2>
          <p className="text-stone-500 mt-2 max-w-sm">Connect your broker or add positions manually to start investing with intention.</p>
        </div>
        <div className="flex gap-3">
          <Link href="/connect"><Button>Connect Broker</Button></Link>
          <Button variant="outline" onClick={() => setShowAddForm(true)}>Add manually</Button>
        </div>
        {showAddForm && (
          <div className="w-full max-w-lg mt-8 text-left">
            <QuickAddHolding onAdd={() => { setShowAddForm(false); void refreshDashboard(); }} />
          </div>
        )}
      </div>
    );
  }

  // Map HoldingPulses to Insights for the PulseStream
  const insights = (pulse?.pulses ?? [])
    .filter((p) => p.pulse_status !== "intact" || p.latest_event_summary)
    .map((p) => ({
      ticker: p.ticker,
      type: (p.pulse_status === "review" ? "warning" : p.pulse_status === "watch" ? "event" : "stable") as "warning"|"event"|"stable",
      headline: p.pulse_status === "review" ? "Review Recommended" : p.pulse_status === "watch" ? "On Watchlist" : "Thesis Intact",
      rationale: p.latest_event_summary || p.reason,
    }));

  const warnings = summary?.attention_queue.map(q => q.reason) || [];
  if (summary && summary.theses_missing > 0) {
    warnings.push(`${summary.theses_missing} holdings are missing a thesis. Click '✨ 1-Click AI Draft' below to start tracking them.`);
  }

  return (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="space-y-8 max-w-6xl mx-auto pb-20">
      
      {/* Command Center Header */}
      {summary && (
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 border-b pb-6">
          <div>
            <p className="text-sm font-medium text-stone-500 uppercase tracking-widest mb-2">Total Portfolio</p>
            <h1 className="text-5xl font-semibold tracking-tight">{formatCurrency(summary.total_value)}</h1>
            <div className="flex items-center gap-3 mt-3">
              <Badge variant="secondary" className={`text-sm py-1 px-3 ${summary.total_pnl >= 0 ? "text-emerald-700 bg-emerald-100" : "text-red-700 bg-red-100"}`}>
                {summary.total_pnl >= 0 ? "+" : ""}{formatCurrency(summary.total_pnl)} ({formatPercent(summary.total_pnl_pct)})
              </Badge>
              <span className="text-sm text-stone-400 font-medium">{summary.holdings_count} Holdings</span>
            </div>
          </div>
          
          <div className="flex gap-3">
            <Link href="/dashboard/simulate">
              <Button variant="outline" className="bg-white">Trade Simulator</Button>
            </Link>
            <Button onClick={() => setShowAddForm(!showAddForm)}>
              {showAddForm ? "Cancel" : "Add Position"}
            </Button>
          </div>
        </div>
      )}

      {showAddForm && (
        <Card className="bg-stone-50/50 border-dashed">
          <CardContent className="pt-6">
            <QuickAddHolding onAdd={() => { setShowAddForm(false); void refreshDashboard(); }} />
          </CardContent>
        </Card>
      )}

      {quarterlyReview && quarterlyReview.pending_count > 0 && (
        <Card className="border-0 bg-[linear-gradient(135deg,rgba(31,41,55,0.98),rgba(42,89,78,0.92)_58%,rgba(229,236,223,0.95))] text-white">
          <CardContent className="flex flex-col gap-4 p-6 md:flex-row md:items-center md:justify-between">
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <Badge className="bg-white/12 text-white">{quarterlyReview.quarter}</Badge>
                <Badge className="bg-white/12 text-white">{quarterlyReview.pending_count} to review</Badge>
              </div>
              <div>
                <p className="text-xl font-semibold tracking-tight">Quarterly conviction review is ready.</p>
                <p className="mt-1 max-w-2xl text-sm text-white/80">
                  Ask the hard question across your current reasons: would you still buy these holdings today for the same reason?
                </p>
              </div>
            </div>
            <Link href="/dashboard/quarterly-review">
              <Button variant="secondary" className="bg-white text-stone-900 hover:bg-white/90">
                Start review
              </Button>
            </Link>
          </CardContent>
        </Card>
      )}

      {/* Bento Box Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        
        {/* Left Column: Holdings List (Takes up 2 columns on large screens) */}
        <div className="lg:col-span-2 space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold tracking-tight">Your Positions</h2>
          </div>
          
          <div className="grid gap-4">
            {holdings.map((h) => (
              <HoldingCard
                key={h.id}
                holding={h}
                thesis={thesesByHolding[h.id]}
                pulse={pulseByHolding[h.id]}
                earnings={earningsByHolding[h.id]}
                onGenerateDraft={() => handleGenerateDraft(h.id, h.ticker)}
              />
            ))}
          </div>
        </div>

        {/* Right Column: Pulse Stream */}
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold tracking-tight">
              {allClear ? "Monitored and Calm" : "Pulse Feed"}
            </h2>
            <Badge variant="outline" className="text-xs bg-white text-stone-500">
              {allClear ? "All clear" : "Live AI Monitoring"}
            </Badge>
          </div>
          
          <Card className="bg-white sticky top-6 shadow-sm border-stone-200">
            <CardContent className="p-6">
              {allClear ? (
                <div className="space-y-5">
                  <div>
                    <p className="text-2xl font-semibold tracking-tight text-stone-900">All clear.</p>
                    <p className="mt-2 text-sm leading-6 text-stone-600">
                      Your {holdings.length} holdings are being monitored. All current reasons look intact, and nothing needs your review right now.
                    </p>
                  </div>

                  <div className="grid gap-3">
                    <div className="rounded-2xl border bg-stone-50 px-4 py-3">
                      <p className="text-xs font-medium uppercase tracking-wide text-stone-500">Last monitoring check</p>
                      <p className="mt-1 text-sm text-stone-800">
                        {latestMonitoringCheck
                          ? formatDate(latestMonitoringCheck)
                          : "Monitoring has not produced a check timestamp yet."}
                      </p>
                    </div>
                    <div className="rounded-2xl border bg-stone-50 px-4 py-3">
                      <p className="text-xs font-medium uppercase tracking-wide text-stone-500">Next routine check-in</p>
                      <p className="mt-1 text-sm text-stone-800">
                        {nextEarnings
                          ? `${nextEarnings.ticker} reports ${formatDate(nextEarnings.report_date)} (${nextEarnings.days_until} day${nextEarnings.days_until === 1 ? "" : "s"})`
                          : pulse?.next_digest_at
                            ? `Weekly digest due ${formatDate(pulse.next_digest_at)}`
                            : "Your next weekly digest will appear once monitoring runs again."}
                      </p>
                    </div>
                    <div className="rounded-2xl border bg-stone-50 px-4 py-3">
                      <p className="text-xs font-medium uppercase tracking-wide text-stone-500">Reason freshness</p>
                      <p className="mt-1 text-sm text-stone-800">
                        {latestReasonRefreshDays !== null
                          ? `You last refreshed a reason ${latestReasonRefreshDays} day${latestReasonRefreshDays === 1 ? "" : "s"} ago.`
                          : "Your reasons are in place, but none have a refresh timestamp yet."}
                      </p>
                    </div>
                  </div>

                  <div className="space-y-2 rounded-2xl border border-dashed border-stone-300 p-4">
                    <p className="text-sm font-medium text-stone-900">Quick actions</p>
                    <div className="flex flex-col gap-2 text-sm">
                      {oldestActiveReason && (
                        <Link
                          href={`/dashboard/positions/${oldestActiveReason.ticker}`}
                          className="text-stone-700 underline-offset-4 hover:text-stone-900 hover:underline"
                        >
                          Revisit your oldest reason: {oldestActiveReason.ticker} ({oldestActiveReason.days_since_thesis_update} days)
                        </Link>
                      )}
                      <Link
                        href="/digests"
                        className="text-stone-700 underline-offset-4 hover:text-stone-900 hover:underline"
                      >
                        Read your latest digest
                      </Link>
                      <Button
                        variant="link"
                        className="h-auto justify-start px-0 text-sm text-stone-700"
                        onClick={() => setShowAddForm(true)}
                      >
                        Add a new holding
                      </Button>
                    </div>
                  </div>

                  {upcomingEarnings.length > 0 && (
                    <div className="space-y-3 rounded-2xl border p-4">
                      <p className="text-sm font-medium text-stone-900">Upcoming earnings</p>
                      {(() => {
                        const thisWeek = upcomingEarnings.filter((e) => e.days_until <= 7);
                        const nextWeek = upcomingEarnings.filter((e) => e.days_until > 7 && e.days_until <= 14);
                        const later = upcomingEarnings.filter((e) => e.days_until > 14);
                        const EarningsRow = ({ event }: { event: typeof upcomingEarnings[0] }) => (
                          <Link
                            key={event.holding_id}
                            href={`/dashboard/positions/${event.ticker}`}
                            className="flex items-center justify-between rounded-xl bg-stone-50 px-3 py-2 text-sm transition hover:bg-stone-100"
                          >
                            <span className={`font-medium ${event.days_until <= 7 ? "text-violet-700" : "text-stone-800"}`}>{event.ticker}</span>
                            <span className="text-stone-500">
                              {formatDate(event.report_date)} · {event.days_until === 0 ? "today" : event.days_until === 1 ? "tomorrow" : `${event.days_until}d`}
                            </span>
                          </Link>
                        );
                        return (
                          <div className="space-y-3">
                            {thisWeek.length > 0 && (
                              <div>
                                <p className="text-xs font-medium text-violet-600 mb-1">This week</p>
                                <div className="space-y-1">{thisWeek.map((e) => <EarningsRow key={e.holding_id} event={e} />)}</div>
                              </div>
                            )}
                            {nextWeek.length > 0 && (
                              <div>
                                <p className="text-xs font-medium text-stone-500 mb-1">Next week</p>
                                <div className="space-y-1">{nextWeek.map((e) => <EarningsRow key={e.holding_id} event={e} />)}</div>
                              </div>
                            )}
                            {later.length > 0 && (
                              <div>
                                <p className="text-xs font-medium text-stone-400 mb-1">Later</p>
                                <div className="space-y-1">{later.slice(0, 3).map((e) => <EarningsRow key={e.holding_id} event={e} />)}</div>
                              </div>
                            )}
                          </div>
                        );
                      })()}
                    </div>
                  )}
                </div>
              ) : (
                <PulseStream insights={insights} warnings={warnings} />
              )}
            </CardContent>
          </Card>
        </div>

      </div>

    </motion.div>
  );
}
