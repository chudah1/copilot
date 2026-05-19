"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { getErrorMessage } from "@/lib/errors";
import { formatCurrency, formatDate, formatPercent } from "@/lib/utils";
import { HoldingCard } from "@/components/portfolio/holding-card";
import { OnboardingBanner } from "@/components/onboarding/onboarding-banner";
import { PulseStream } from "@/components/portfolio/pulse-stream";
import { QuickAddHolding } from "@/components/portfolio/quick-add-holding";
import { motion } from "framer-motion";
import { toast } from "sonner";
import type { DraftStatus, Holding, PortfolioSummary, Thesis, PortfolioPulse, QuarterlyReviewCurrent, UpcomingEarnings } from "@/types";

type DashboardData = {
  holdings: Holding[];
  summary: PortfolioSummary;
  currentTheses: Thesis[];
  pulse: PortfolioPulse;
  upcomingEarnings: UpcomingEarnings[];
  quarterlyReview: QuarterlyReviewCurrent | null;
  draftStatus: DraftStatus | null;
};

async function fetchDashboardData(): Promise<DashboardData> {
  const [holdings, summary, currentTheses, pulse, upcomingEarnings, quarterlyReview, draftStatus] = await Promise.all([
    api.get<Holding[]>("/api/portfolio/holdings"),
    api.get<PortfolioSummary>("/api/portfolio/summary"),
    api.get<Thesis[]>("/api/theses/current"),
    api.get<PortfolioPulse>("/api/portfolio/pulse"),
    api.get<UpcomingEarnings[]>("/api/portfolio/upcoming-earnings").catch(() => []),
    api.get<QuarterlyReviewCurrent>("/api/quarterly-review/current").catch(() => null),
    api.get<DraftStatus>("/api/portfolio/draft-status").catch(() => null),
  ]);
  return { holdings, summary, currentTheses, pulse, upcomingEarnings, quarterlyReview, draftStatus };
}

function buildPulseInsights(pulse: PortfolioPulse | null) {
  return (pulse?.pulses ?? [])
    .filter((p) => p.pulse_status !== "intact" || p.latest_event_summary)
    .map((p) => ({
      ticker: p.ticker,
      type: (p.pulse_status === "review" ? "warning" : p.pulse_status === "watch" ? "event" : "stable") as "warning" | "event" | "stable",
      headline: p.recent_event_count > 1 ? `${p.recent_event_count} updates` : p.pulse_status === "review" ? "Review recommended" : "Watchlist",
      rationale: p.latest_event_summary || p.reason,
    }));
}

export default function DashboardPage() {
  const [holdings, setHoldings] = useState<Holding[]>([]);
  const [currentTheses, setCurrentTheses] = useState<Thesis[]>([]);
  const [summary, setSummary] = useState<PortfolioSummary | null>(null);
  const [pulse, setPulse] = useState<PortfolioPulse | null>(null);
  const [quarterlyReview, setQuarterlyReview] = useState<QuarterlyReviewCurrent | null>(null);
  const [upcomingEarnings, setUpcomingEarnings] = useState<UpcomingEarnings[]>([]);
  const [draftStatus, setDraftStatus] = useState<DraftStatus | null>(null);
  const [draftBannerDismissed, setDraftBannerDismissed] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [showAddForm, setShowAddForm] = useState(false);

  const applyData = (data: DashboardData) => {
    setHoldings(data.holdings);
    setSummary(data.summary);
    setCurrentTheses(data.currentTheses);
    setPulse(data.pulse);
    setUpcomingEarnings(data.upcomingEarnings);
    setQuarterlyReview(data.quarterlyReview);
    setDraftStatus(data.draftStatus);
  };

  const refresh = async ({ spinner = false }: { spinner?: boolean } = {}) => {
    if (spinner) setLoading(true);
    setLoadError(null);
    try { applyData(await fetchDashboardData()); }
    catch (err) { setLoadError(getErrorMessage(err, "Failed to load portfolio")); }
    finally { setLoading(false); }
  };

  useEffect(() => {
    let cancelled = false;
    fetchDashboardData()
      .then((data) => { if (!cancelled) { applyData(data); setLoadError(null); } })
      .catch((err) => { if (!cancelled) setLoadError(getErrorMessage(err, "Failed to load portfolio")); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  const handleGenerateDraft = async (holdingId: string, ticker: string) => {
    try {
      const draft = await api.post<{ why_own_it: string; must_remain_true: string; what_would_change_my_mind: string }>("/api/theses/draft", { ticker });
      await api.post("/api/theses", { holding_id: holdingId, thesis_kind: "company", ...draft, status: "active", confidence: "medium", source: "ai_assisted", review_cadence_days: 30 });
      toast.success(`Draft thesis saved for ${ticker}`);
      void refresh();
    } catch (err) {
      toast.error(getErrorMessage(err, "Failed to generate draft"));
    }
  };

  const thesesByHolding = Object.fromEntries(currentTheses.map((t) => [t.holding_id, t]));
  const pulseByHolding = Object.fromEntries((pulse?.pulses ?? []).map((p) => [p.holding_id, p]));
  const earningsByHolding = Object.fromEntries(upcomingEarnings.map((e) => [e.holding_id, e]));

  const reviewCount = (pulse?.pulses ?? []).filter((p) => p.pulse_status === "review").length;
  const watchCount = (pulse?.pulses ?? []).filter((p) => p.pulse_status === "watch").length;
  const missingThesisCount = summary?.theses_missing ?? 0;
  const allClear = holdings.length > 0 && reviewCount === 0 && watchCount === 0 && (quarterlyReview?.pending_count ?? 0) === 0 && missingThesisCount === 0;

  const latestCheck = (pulse?.pulses ?? []).map((p) => p.last_checked_at).filter(Boolean).sort((a, b) => new Date(b!).getTime() - new Date(a!).getTime())[0] ?? null;
  const oldestReason = (pulse?.pulses ?? []).filter((p) => p.has_thesis && p.days_since_thesis_update !== null).sort((a, b) => (b.days_since_thesis_update ?? 0) - (a.days_since_thesis_update ?? 0))[0] ?? null;
  const nextEarnings = upcomingEarnings[0] ?? null;
  const insights = buildPulseInsights(pulse);
  const warnings = (summary?.attention_queue.map((q) => q.reason) ?? []);
  if (missingThesisCount > 0) warnings.push(`${missingThesisCount} position${missingThesisCount > 1 ? "s" : ""} without a thesis.`);

  // ── Loading ──
  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[calc(100vh-52px)]">
        <p className="font-mono text-xs uppercase tracking-[0.2em] text-muted-foreground animate-pulse">
          Loading portfolio…
        </p>
      </div>
    );
  }

  // ── Error ──
  if (loadError && holdings.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[calc(100vh-52px)] gap-4 text-center px-6">
        <p className="font-sans text-sm text-muted-foreground">{loadError}</p>
        <button onClick={() => void refresh({ spinner: true })} className="font-mono text-[10px] uppercase tracking-[0.2em] text-primary hover:text-primary/70 transition-colors border border-primary/30 px-4 py-2">
          Retry
        </button>
      </div>
    );
  }

  // ── Empty state ──
  if (holdings.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[calc(100vh-52px)] gap-6 text-center px-6">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: "easeOut" }}
          className="space-y-4"
        >
          <div className="w-full max-w-sm mx-auto">
            <div className="border-t-2 border-foreground pt-4 pb-4">
              <p className="font-display italic text-3xl text-foreground">Begin your ledger.</p>
            </div>
            <div className="border-b-2 border-foreground" />
          </div>
          <p className="font-sans text-sm text-muted-foreground max-w-xs leading-relaxed">
            Connect your broker or add a position to start investing with intention.
          </p>
        </motion.div>
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.4, ease: "easeOut", delay: 0.2 }}
          className="flex gap-4"
        >
          <Link href="/connect">
            <button className="px-5 py-2.5 font-mono text-[11px] uppercase tracking-[0.15em] bg-primary text-primary-foreground hover:bg-primary/90 transition-colors">
              Connect broker
            </button>
          </Link>
          <button
            onClick={() => setShowAddForm(true)}
            className="px-5 py-2.5 font-mono text-[11px] uppercase tracking-[0.15em] border border-border text-foreground/60 hover:text-foreground hover:border-foreground/40 transition-colors"
          >
            Add manually
          </button>
        </motion.div>
        {showAddForm && (
          <div className="w-full max-w-md text-left">
            <QuickAddHolding onAdd={() => { setShowAddForm(false); void refresh(); }} />
          </div>
        )}
      </div>
    );
  }

  // ── Main dashboard ──
  return (
    <div className="min-h-[calc(100vh-52px)]">

      {/* Draft review banner */}
      {draftStatus && draftStatus.ready > 0 && !draftBannerDismissed && (
        <div className="px-8 pt-4">
          <div className="flex items-center justify-between border border-primary/30 bg-primary/5 px-5 py-3">
            <div className="flex items-center gap-3">
              <span className="font-mono text-[9px] uppercase tracking-[0.2em] text-primary border border-primary/40 px-2 py-0.5">
                New
              </span>
              <p className="text-sm text-foreground">
                AI drafted {draftStatus.ready === 1 ? "a thesis" : `${draftStatus.ready} theses`} for your top position{draftStatus.ready > 1 ? "s" : ""} while you were setting up.
              </p>
            </div>
            <div className="flex items-center gap-4 shrink-0 ml-4">
              <Link
                href="/onboarding/review-drafts"
                className="font-mono text-[10px] uppercase tracking-[0.15em] text-primary hover:text-primary/70 transition-colors"
              >
                Review →
              </Link>
              <button
                onClick={() => setDraftBannerDismissed(true)}
                className="text-muted-foreground hover:text-foreground transition-colors text-xs"
              >
                ✕
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Onboarding banner */}
      <div className="px-8 pt-4 empty:hidden">
        <OnboardingBanner />
      </div>

      {/* ── Portfolio statement (centered, framed) ── */}
      {summary && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: "easeOut" }}
          className="text-center px-8 py-10"
        >
          {/* Top rule */}
          <div className="flex items-center gap-4 mb-6">
            <div className="flex-1 border-t border-foreground/20" />
            <p className="font-mono text-[10px] uppercase tracking-[0.3em] text-muted-foreground">
              Statement of Account
            </p>
            <div className="flex-1 border-t border-foreground/20" />
          </div>

          {/* Value */}
          <p className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground mb-3">
            Total Portfolio Value
          </p>
          <h1 className="font-display italic text-[4.25rem] leading-none text-foreground tracking-tight">
            {formatCurrency(summary.total_value)}
          </h1>
          <div className="flex items-center justify-center gap-2 mt-4">
            <span className={`font-mono text-lg tabular-nums ${summary.total_pnl >= 0 ? "text-emerald-700" : "text-red-600"}`}>
              {summary.total_pnl >= 0 ? "+" : ""}{formatCurrency(summary.total_pnl)}
            </span>
            <span className="text-muted-foreground/40 font-mono">·</span>
            <span className={`font-mono text-base tabular-nums ${summary.total_pnl >= 0 ? "text-emerald-700/70" : "text-red-600/70"}`}>
              {formatPercent(summary.total_pnl_pct)} total return
            </span>
          </div>

          {/* Meta stats */}
          <div className="flex items-center justify-center gap-8 mt-6">
            {[
              { label: "Positions", value: String(summary.holdings_count) },
              { label: "Monitored", value: String(summary.theses_active) },
              ...(reviewCount > 0 ? [{ label: "Need review", value: String(reviewCount), warn: true }] : []),
              ...(missingThesisCount > 0 ? [{ label: "No thesis", value: String(missingThesisCount), warn: true }] : []),
            ].map(({ label, value, warn }) => (
              <div key={label} className="text-center">
                <p className={`font-mono text-2xl tabular-nums ${warn ? "text-primary" : "text-foreground/80"}`}>{value}</p>
                <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground mt-1">{label}</p>
              </div>
            ))}
          </div>

          {/* Bottom rule + actions */}
          <div className="flex items-center gap-4 mt-6">
            <div className="flex-1 border-t border-foreground/20" />
            <div className="flex gap-3">
              <Link href="/dashboard/simulate">
                <button className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground hover:text-primary transition-colors border border-border px-4 py-1.5 hover:border-primary/40">
                  Trade Simulator
                </button>
              </Link>
              <button
                onClick={() => setShowAddForm(!showAddForm)}
                className={`font-mono text-[10px] uppercase tracking-[0.2em] transition-colors border px-4 py-1.5 ${
                  showAddForm
                    ? "text-muted-foreground border-border"
                    : "text-primary border-primary/40 hover:border-primary"
                }`}
              >
                {showAddForm ? "× Cancel" : "+ Add Position"}
              </button>
            </div>
            <div className="flex-1 border-t border-foreground/20" />
          </div>
        </motion.div>
      )}

      {/* Quarterly review prompt */}
      {quarterlyReview && quarterlyReview.pending_count > 0 && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.3, ease: "easeOut", delay: 0.1 }}
          className="mx-8 mb-0 border border-primary/25 bg-primary/8 flex items-center justify-between px-5 py-3"
        >
          <div className="flex items-center gap-4">
            <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-primary">
              {quarterlyReview.quarter}
            </span>
            <p className="font-sans text-sm text-foreground/80">
              Quarterly conviction review — {quarterlyReview.pending_count} position{quarterlyReview.pending_count > 1 ? "s" : ""} awaiting judgement
            </p>
          </div>
          <Link href="/dashboard/quarterly-review">
            <button className="font-mono text-[10px] uppercase tracking-[0.2em] text-primary hover:text-primary/70 transition-colors whitespace-nowrap">
              Begin review →
            </button>
          </Link>
        </motion.div>
      )}

      {/* Quick add form */}
      {showAddForm && (
        <div className="mx-8 mt-4 border border-border bg-card p-5">
          <QuickAddHolding onAdd={() => { setShowAddForm(false); void refresh(); }} />
        </div>
      )}

      {/* ── Two-column layout ── */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.4, ease: "easeOut", delay: 0.15 }}
        className="flex mt-4 border-t border-border"
      >

        {/* ── Holdings ledger (left, flex-1) ── */}
        <div className="flex-1 min-w-0 border-r border-border">

          {/* Section header */}
          <div className="flex items-center justify-between px-8 py-3 border-b border-border/60">
            <div className="flex items-center gap-3">
              <p className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
                Holdings
              </p>
              <span className="font-mono text-[10px] text-primary/60">({holdings.length})</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground pr-2 hidden sm:block">
                Ticker · Position · Value · P&L · Status
              </span>
            </div>
          </div>

          {/* Holdings */}
          <div className="px-8">
            {holdings.map((h, i) => (
              <HoldingCard
                key={h.id}
                holding={h}
                thesis={thesesByHolding[h.id]}
                pulse={pulseByHolding[h.id]}
                earnings={earningsByHolding[h.id]}
                onGenerateDraft={() => handleGenerateDraft(h.id, h.ticker)}
                index={i}
              />
            ))}
          </div>
        </div>

        {/* ── Field notes (right, sticky) ── */}
        <div className="w-64 xl:w-72 shrink-0">
          <div className="sticky top-[52px] h-[calc(100vh-52px)] overflow-y-auto px-6 py-6 space-y-7">

            {/* Label */}
            <div className="border-b border-border pb-3">
              <p className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
                Field Notes
              </p>
            </div>

            {allClear ? (
              <>
                {/* All-clear message */}
                <div className="space-y-2">
                  <p className="font-display italic text-[1.15rem] text-foreground leading-snug">
                    All positions<br />monitored and calm.
                  </p>
                  <p className="font-sans text-xs text-muted-foreground leading-relaxed">
                    Nothing needs your attention right now. The reasons hold.
                  </p>
                </div>

                {/* Meta info */}
                <div className="space-y-3 border-t border-border pt-4">
                  {[
                    {
                      key: "last-check",
                      label: "Last check",
                      value: latestCheck ? formatDate(latestCheck) : "Not yet run",
                    },
                    {
                      key: "next-event",
                      label: "Next event",
                      value: nextEarnings
                        ? `${nextEarnings.ticker} reports ${formatDate(nextEarnings.report_date)}`
                        : pulse?.next_digest_at
                          ? `Digest ${formatDate(pulse.next_digest_at)}`
                          : "No scheduled events",
                    },
                    {
                      key: "oldest-reason",
                      label: "Oldest thesis",
                      value: oldestReason
                        ? `${oldestReason.ticker} — ${oldestReason.days_since_thesis_update}d old`
                        : "All theses recent",
                    },
                  ].map(({ key, label, value }) => (
                    <div key={key}>
                      <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">{label}</p>
                      <p className="font-sans text-xs text-foreground/70 mt-0.5 leading-relaxed">{value}</p>
                    </div>
                  ))}
                </div>

                {/* Actions */}
                <div className="space-y-2 border-t border-border pt-4">
                  <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground mb-2">
                    Quick actions
                  </p>
                  {[
                    oldestReason ? { href: `/dashboard/positions/${oldestReason.ticker}`, label: `Revisit ${oldestReason.ticker} →` } : null,
                    { href: "/digests", label: "Latest digest →" },
                  ].filter(Boolean).map((link) => (
                    <Link key={link!.href} href={link!.href} className="block font-sans text-xs text-muted-foreground hover:text-primary transition-colors">
                      {link!.label}
                    </Link>
                  ))}
                  <button onClick={() => setShowAddForm(true)} className="block font-sans text-xs text-muted-foreground hover:text-primary transition-colors">
                    Add a position →
                  </button>
                </div>

                {/* Earnings */}
                {upcomingEarnings.length > 0 && (
                  <div className="space-y-2 border-t border-border pt-4">
                    <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground mb-2">
                      Upcoming earnings
                    </p>
                    {upcomingEarnings.slice(0, 5).map((e) => (
                      <Link key={e.holding_id} href={`/dashboard/positions/${e.ticker}`}
                        className="flex justify-between font-sans text-xs group"
                      >
                        <span className="font-mono text-primary/70 group-hover:text-primary transition-colors">{e.ticker}</span>
                        <span className="text-muted-foreground">
                          {e.days_until === 0 ? "today" : e.days_until === 1 ? "tomorrow" : `${e.days_until}d`}
                        </span>
                      </Link>
                    ))}
                  </div>
                )}
              </>
            ) : (
              <>
                {/* Pulse feed */}
                <PulseStream insights={insights} warnings={warnings} />

                {upcomingEarnings.length > 0 && (
                  <div className="space-y-2 border-t border-border pt-4">
                    <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground mb-2">
                      Upcoming earnings
                    </p>
                    {upcomingEarnings.slice(0, 4).map((e) => (
                      <Link key={e.holding_id} href={`/dashboard/positions/${e.ticker}`}
                        className="flex justify-between font-sans text-xs group"
                      >
                        <span className="font-mono text-primary/70 group-hover:text-primary transition-colors">{e.ticker}</span>
                        <span className="text-muted-foreground">
                          {e.days_until <= 1 ? (e.days_until === 0 ? "today" : "tomorrow") : `${e.days_until}d`}
                        </span>
                      </Link>
                    ))}
                  </div>
                )}

                {/* Actions */}
                <div className="space-y-2 border-t border-border pt-4">
                  <Link href="/digests" className="block font-sans text-xs text-muted-foreground hover:text-primary transition-colors">
                    Latest digest →
                  </Link>
                  <button onClick={() => setShowAddForm(true)} className="block font-sans text-xs text-muted-foreground hover:text-primary transition-colors">
                    Add a position →
                  </button>
                </div>
              </>
            )}
          </div>
        </div>

      </motion.div>
    </div>
  );
}
