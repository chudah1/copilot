"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import { api } from "@/lib/api";
import { getErrorMessage } from "@/lib/errors";
import { formatCurrency, formatPercent } from "@/lib/utils";
import { OnboardingBanner } from "@/components/onboarding/onboarding-banner";
import { QuickAddHolding } from "@/components/portfolio/quick-add-holding";
import { DigestCountdown } from "@/components/portfolio/digest-countdown";
import { toast } from "sonner";
import type {
  DraftStatus,
  Holding,
  LivePrice,
  PortfolioSummary,
  Thesis,
  HoldingPulse,
  PortfolioPulse,
  QuarterlyReviewCurrent,
  UpcomingEarnings,
} from "@/types";

// ── Data fetching ──────────────────────────────────────────────────────────

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
  const [holdings, summary, currentTheses, pulse, upcomingEarnings, quarterlyReview, draftStatus] =
    await Promise.all([
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

// ── Position card ──────────────────────────────────────────────────────────

const PULSE_DOT: Record<string, string> = {
  intact: "bg-emerald-500",
  watch: "bg-amber-400",
  review: "bg-red-500",
};

const PULSE_RING: Record<string, string> = {
  review: "ring-1 ring-red-200",
  watch: "ring-1 ring-amber-200",
};

function cleanTicker(ticker: string) {
  return ticker.replace(/_US_EQ$/, "").replace(/_EQ$/, "");
}

interface PositionCardProps {
  holding: Holding;
  thesis?: Thesis;
  pulse?: HoldingPulse;
  earnings?: UpcomingEarnings;
  livePrice?: LivePrice;
  totalValue: number;
  onGenerateDraft?: () => void;
  index: number;
}

function PositionCard({ holding, thesis, pulse, earnings, livePrice, totalValue, onGenerateDraft, index }: PositionCardProps) {
  const value = livePrice?.current_value ?? holding.current_value ?? 0;
  const cost = holding.quantity * holding.average_cost_basis;
  const pnl = value - cost;
  const pnlPct = cost > 0 ? (pnl / cost) * 100 : 0;
  const allocationPct = totalValue > 0 ? (value / totalValue) * 100 : 0;

  const pulseStatus = pulse?.pulse_status ?? (thesis ? "intact" : null);
  const dotColor = pulseStatus ? (PULSE_DOT[pulseStatus] ?? "bg-border") : "bg-border";
  const ringClass = pulseStatus ? (PULSE_RING[pulseStatus] ?? "") : "";

  return (
    <motion.div
      className="h-full"
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: index * 0.04, ease: "easeOut" }}
    >
      <Link href={`/dashboard/positions/${holding.ticker}`} className="block h-full">
        <div
          className={`h-full group relative flex flex-col gap-3 border border-border bg-card p-4 transition-all duration-150 hover:border-foreground/20 hover:shadow-md cursor-pointer ${ringClass}`}
        >
          {/* Allocation bar — top edge */}
          <div className="absolute top-0 left-0 right-0 h-[3px] bg-border overflow-hidden">
            <motion.div
              className="h-full bg-primary"
              initial={{ width: 0 }}
              animate={{ width: `${Math.min(allocationPct * 4, 100)}%` }}
              transition={{ duration: 0.6, delay: index * 0.05 + 0.2, ease: "easeOut" }}
            />
          </div>

          {/* Header row */}
          <div className="flex items-start justify-between pt-1">
            <div className="min-w-0">
              <p className="font-mono text-[11px] font-semibold tracking-[0.2em] text-primary">
                {cleanTicker(holding.ticker)}
              </p>
              <p className="font-sans text-[11px] text-muted-foreground mt-0.5 truncate max-w-[140px]">
                {holding.name}
              </p>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              {earnings && earnings.days_until <= 5 && (
                <span className="font-mono text-[8px] uppercase tracking-[0.12em] text-violet-600 border border-violet-200 px-1 py-px">
                  {earnings.days_until === 0 ? "today" : earnings.days_until === 1 ? "tmrw" : `${earnings.days_until}d`}
                </span>
              )}
              <span className={`h-2 w-2 rounded-full flex-shrink-0 ${dotColor}`} />
            </div>
          </div>

          {/* Value + P&L */}
          <div>
            <p className="font-mono text-[1.05rem] tabular-nums text-foreground font-medium leading-tight">
              {formatCurrency(value)}
            </p>
            <p className={`font-mono text-[11px] tabular-nums mt-0.5 ${pnl >= 0 ? "text-emerald-700" : "text-red-600"}`}>
              {pnl >= 0 ? "+" : ""}{formatCurrency(pnl)}{" "}
              <span className="opacity-70">({formatPercent(pnlPct)})</span>
            </p>
          </div>

          {/* Allocation % with bar */}
          <div className="space-y-1">
            <div className="flex items-center justify-between">
              <span className="font-mono text-[9px] uppercase tracking-[0.15em] text-muted-foreground/60">
                Portfolio weight
              </span>
              <span className="font-mono text-[10px] text-muted-foreground">
                {allocationPct.toFixed(1)}%
              </span>
            </div>
            <div className="h-px bg-border overflow-hidden">
              <motion.div
                className="h-full bg-foreground/20"
                initial={{ width: 0 }}
                animate={{ width: `${Math.min(allocationPct * 4, 100)}%` }}
                transition={{ duration: 0.5, delay: index * 0.05 + 0.25, ease: "easeOut" }}
              />
            </div>
          </div>

          {/* Spacer — pushes thesis/CTA flush to bottom */}
          <div className="flex-1" />

          {/* Thesis snippet or CTA */}
          {thesis?.why_own_it ? (
            <p className="font-sans text-[11px] italic text-muted-foreground leading-relaxed line-clamp-2 border-t border-border/60 pt-2.5">
              {thesis.why_own_it}
            </p>
          ) : (
            <button
              onClick={(e) => { e.preventDefault(); e.stopPropagation(); onGenerateDraft?.(); }}
              className="font-mono text-[9px] uppercase tracking-[0.15em] text-muted-foreground/50 hover:text-primary transition-colors border-t border-border/60 pt-2.5 text-left"
            >
              + Draft thesis with AI
            </button>
          )}
        </div>
      </Link>
    </motion.div>
  );
}

// ── Attention card ─────────────────────────────────────────────────────────

interface AttentionCardProps {
  holding: Holding;
  pulse: HoldingPulse;
  index: number;
}

function AttentionCard({ holding, pulse, index }: AttentionCardProps) {
  const isReview = pulse.pulse_status === "review";
  return (
    <motion.div
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.25, delay: index * 0.06 }}
    >
      <Link href={`/dashboard/positions/${holding.ticker}`}>
        <div className={`w-56 shrink-0 border bg-card p-4 space-y-2 transition-all hover:shadow-md cursor-pointer ${
          isReview
            ? "border-l-2 border-l-red-500 border-border hover:border-l-red-600"
            : "border-l-2 border-l-amber-400 border-border hover:border-l-amber-500"
        }`}>
          <div className="flex items-center justify-between">
            <span className="font-mono text-[11px] font-semibold tracking-[0.2em] text-primary">
              {cleanTicker(holding.ticker)}
            </span>
            <span className={`font-mono text-[9px] uppercase tracking-[0.15em] ${isReview ? "text-red-600" : "text-amber-700"}`}>
              {isReview ? "Review" : "Watch"}
            </span>
          </div>
          <p className="font-sans text-[11px] text-foreground/80 leading-relaxed line-clamp-3">
            {pulse.latest_event_summary ?? pulse.reason ?? "Monitoring event requires attention"}
          </p>
          {pulse.recent_event_count > 0 && (
            <p className="font-mono text-[9px] text-muted-foreground/60">
              {pulse.recent_event_count} recent event{pulse.recent_event_count !== 1 ? "s" : ""} →
            </p>
          )}
        </div>
      </Link>
    </motion.div>
  );
}

// ── Dashboard ──────────────────────────────────────────────────────────────

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
  const [livePrices, setLivePrices] = useState<Record<string, LivePrice>>({});

  const fetchLivePrices = async () => {
    try {
      const prices = await api.get<LivePrice[]>("/api/portfolio/live-prices");
      setLivePrices(Object.fromEntries(prices.map((p) => [p.ticker, p])));
    } catch {
      // Silently ignore — fall back to DB values
    }
  };

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
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
          void fetchLivePrices();
        }
      });
    return () => { cancelled = true; };
  }, []);

  // Refresh live prices every 60 seconds while the tab is visible
  useEffect(() => {
    const interval = setInterval(() => {
      if (!document.hidden) void fetchLivePrices();
    }, 60_000);
    return () => clearInterval(interval);
  }, []);

  const handleGenerateDraft = async (holdingId: string, ticker: string) => {
    try {
      const draft = await api.post<{ why_own_it: string; must_remain_true: string; what_would_change_my_mind: string }>(
        "/api/theses/draft", { ticker }
      );
      await api.post("/api/theses", {
        holding_id: holdingId,
        thesis_kind: "company",
        ...draft,
        status: "active",
        confidence: "medium",
        source: "ai_assisted",
        review_cadence_days: 30,
      });
      toast.success(`Draft thesis saved for ${ticker}`);
      void refresh();
    } catch (err) {
      toast.error(getErrorMessage(err, "Failed to generate draft"));
    }
  };

  // ── Derived state ─────────────────────────────────────────────────────
  const thesesByHolding = Object.fromEntries(currentTheses.map((t) => [t.holding_id, t]));

  // Live portfolio total: sum current_value from live prices where available,
  // fall back to DB value for holdings not yet refreshed.
  const hasLivePrices = Object.keys(livePrices).length > 0;
  const liveTotalValue = hasLivePrices
    ? holdings.reduce((sum, h) => sum + (livePrices[h.ticker]?.current_value ?? h.current_value ?? 0), 0)
    : null;
  const displayTotalValue = liveTotalValue ?? summary?.total_value ?? 0;
  const livePnl = liveTotalValue != null && summary ? liveTotalValue - summary.total_cost : null;
  const livePnlPct = livePnl != null && summary && summary.total_cost > 0 ? (livePnl / summary.total_cost) * 100 : null;
  const pulseByHolding = Object.fromEntries((pulse?.pulses ?? []).map((p) => [p.holding_id, p]));
  const earningsByHolding = Object.fromEntries(upcomingEarnings.map((e) => [e.holding_id, e]));

  const needsAttention = (pulse?.pulses ?? []).filter(
    (p) => p.pulse_status === "review" || p.pulse_status === "watch"
  );
  const reviewCount = needsAttention.filter((p) => p.pulse_status === "review").length;
  const missingThesisCount = summary?.theses_missing ?? 0;

  // Sort: review first, then watch, then intact; within each group sort by value desc
  const sortedHoldings = [...holdings].sort((a, b) => {
    const pa = pulseByHolding[a.id]?.pulse_status ?? "intact";
    const pb = pulseByHolding[b.id]?.pulse_status ?? "intact";
    const order: Record<string, number> = { review: 0, watch: 1, intact: 2 };
    const diff = (order[pa] ?? 2) - (order[pb] ?? 2);
    if (diff !== 0) return diff;
    return (b.current_value ?? 0) - (a.current_value ?? 0);
  });

  // ── Loading ─────────────────────────────────────────────────────────
  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[calc(100vh-54px)]">
        <p className="font-mono text-[10px] uppercase tracking-[0.3em] text-muted-foreground animate-pulse">
          Loading…
        </p>
      </div>
    );
  }

  // ── Error ────────────────────────────────────────────────────────────
  if (loadError && holdings.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[calc(100vh-54px)] gap-4 text-center px-6">
        <p className="font-sans text-sm text-muted-foreground">{loadError}</p>
        <button
          onClick={() => void refresh({ spinner: true })}
          className="font-mono text-[10px] uppercase tracking-[0.2em] text-primary border border-primary/30 px-4 py-2 hover:bg-primary/5 transition-colors"
        >
          Retry
        </button>
      </div>
    );
  }

  // ── Empty state ──────────────────────────────────────────────────────
  if (holdings.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[calc(100vh-54px)] gap-8 text-center px-6">
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="space-y-3 max-w-sm"
        >
          <div className="border-t-2 border-foreground pt-4">
            <p className="font-display italic text-3xl text-foreground">Begin your ledger.</p>
          </div>
          <div className="border-b-2 border-foreground" />
          <p className="font-sans text-sm text-muted-foreground leading-relaxed pt-1">
            Import your holdings to start tracking your investment reasoning.
          </p>
        </motion.div>
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.4, delay: 0.2 }}
          className="flex gap-3"
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

  // ── Main dashboard ───────────────────────────────────────────────────
  return (
    <div className="min-h-[calc(100vh-54px)] flex flex-col">

      {/* ── Stat strip ─────────────────────────────────────────────── */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.35 }}
        className="border-b border-border bg-card px-8 py-4"
      >
        <div className="flex items-center justify-between gap-6 flex-wrap">
          {/* Left: portfolio total */}
          <div className="flex items-baseline gap-4">
            <div>
              <p className="font-mono text-[9px] uppercase tracking-[0.25em] text-muted-foreground mb-1">
                Portfolio
              </p>
              <div className="flex items-baseline gap-3">
                <span className="font-display italic text-[1.85rem] leading-none text-foreground tracking-tight">
                  {formatCurrency(displayTotalValue)}
                </span>
                {(livePnlPct != null ? livePnlPct : summary?.total_pnl_pct) != null && (
                  <span className={`font-mono text-sm tabular-nums ${(livePnl ?? summary?.total_pnl ?? 0) >= 0 ? "text-emerald-700" : "text-red-600"}`}>
                    {(livePnl ?? summary?.total_pnl ?? 0) >= 0 ? "+" : ""}{formatPercent(livePnlPct ?? summary?.total_pnl_pct ?? 0)}
                  </span>
                )}
                {hasLivePrices && (
                  <span className="flex items-center gap-1 font-mono text-[9px] uppercase tracking-[0.15em] text-emerald-600">
                    <span className="inline-block h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                    live
                  </span>
                )}
              </div>
            </div>

            {/* Divider */}
            <div className="h-8 w-px bg-border hidden sm:block" />

            {/* Key stats */}
            <div className="hidden sm:flex items-center gap-5">
              {[
                { label: "Positions", value: String(summary?.holdings_count ?? 0) },
                { label: "Monitored", value: String(summary?.theses_active ?? 0) },
                ...(reviewCount > 0 ? [{ label: "Review", value: String(reviewCount), accent: true }] : []),
                ...(missingThesisCount > 0 ? [{ label: "No thesis", value: String(missingThesisCount), accent: true }] : []),
              ].map(({ label, value, accent }) => (
                <div key={label} className="text-center">
                  <p className={`font-mono text-base tabular-nums font-medium ${accent ? "text-primary" : "text-foreground/80"}`}>
                    {value}
                  </p>
                  <p className="font-mono text-[9px] uppercase tracking-[0.18em] text-muted-foreground mt-0.5">
                    {label}
                  </p>
                </div>
              ))}
            </div>
          </div>

          {/* Right: digest + actions */}
          <div className="flex items-center gap-3 flex-wrap">
            {pulse?.next_digest_at && (
              <DigestCountdown nextDigestAt={pulse.next_digest_at} />
            )}
            <div className="h-4 w-px bg-border hidden sm:block" />
            <Link href="/dashboard/simulate">
              <button className="font-mono text-[9px] uppercase tracking-[0.18em] text-muted-foreground hover:text-foreground transition-colors border border-border px-3 py-1.5 hover:border-foreground/30">
                Simulate
              </button>
            </Link>
            <button
              onClick={() => setShowAddForm((v) => !v)}
              className={`font-mono text-[9px] uppercase tracking-[0.18em] transition-colors border px-3 py-1.5 ${
                showAddForm
                  ? "text-muted-foreground border-border"
                  : "text-primary border-primary/30 hover:border-primary/60"
              }`}
            >
              {showAddForm ? "× Cancel" : "+ Position"}
            </button>
          </div>
        </div>
      </motion.div>

      {/* ── Banners ─────────────────────────────────────────────────── */}
      <div className="px-8 pt-3 space-y-2 empty:hidden">
        <OnboardingBanner />

        {draftStatus && draftStatus.ready > 0 && !draftBannerDismissed && (
          <div className="flex items-center justify-between border border-primary/25 bg-primary/5 px-5 py-2.5">
            <div className="flex items-center gap-3">
              <span className="font-mono text-[8px] uppercase tracking-[0.2em] text-primary border border-primary/30 px-1.5 py-0.5">
                New
              </span>
              <p className="font-sans text-sm text-foreground/80">
                AI drafted {draftStatus.ready === 1 ? "a thesis" : `${draftStatus.ready} theses`} for your top position{draftStatus.ready > 1 ? "s" : ""}.
              </p>
            </div>
            <div className="flex items-center gap-4 shrink-0 ml-4">
              <Link href="/onboarding/review-drafts" className="font-mono text-[10px] uppercase tracking-[0.15em] text-primary hover:text-primary/70 transition-colors">
                Review →
              </Link>
              <button onClick={() => setDraftBannerDismissed(true)} className="text-muted-foreground hover:text-foreground text-xs transition-colors">
                ✕
              </button>
            </div>
          </div>
        )}

        {quarterlyReview && quarterlyReview.pending_count > 0 && (
          <div className="flex items-center justify-between border border-primary/20 bg-primary/5 px-5 py-2.5">
            <div className="flex items-center gap-3">
              <span className="font-mono text-[8px] uppercase tracking-[0.2em] text-primary">{quarterlyReview.quarter}</span>
              <p className="font-sans text-sm text-foreground/80">
                Quarterly review — {quarterlyReview.pending_count} position{quarterlyReview.pending_count > 1 ? "s" : ""} awaiting judgement
              </p>
            </div>
            <Link href="/dashboard/quarterly-review" className="font-mono text-[10px] uppercase tracking-[0.15em] text-primary hover:text-primary/70 transition-colors whitespace-nowrap shrink-0 ml-4">
              Begin →
            </Link>
          </div>
        )}
      </div>

      {/* ── Quick add form ───────────────────────────────────────────── */}
      <AnimatePresence>
        {showAddForm && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden px-8 pt-3"
          >
            <div className="border border-border bg-card p-5">
              <QuickAddHolding onAdd={() => { setShowAddForm(false); void refresh(); }} />
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Attention section ────────────────────────────────────────── */}
      <AnimatePresence>
        {needsAttention.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, delay: 0.1 }}
            className="px-8 pt-5"
          >
            <div className="flex items-center gap-3 mb-3">
              <p className="font-mono text-[9px] uppercase tracking-[0.25em] text-muted-foreground">
                Needs attention
              </p>
              <span className="font-mono text-[9px] text-primary/60">({needsAttention.length})</span>
            </div>
            <div className="flex gap-3 overflow-x-auto pb-1 scrollbar-hide">
              {needsAttention.map((p, i) => {
                const holding = holdings.find((h) => h.id === p.holding_id);
                if (!holding) return null;
                return (
                  <AttentionCard key={p.holding_id} holding={holding} pulse={p} index={i} />
                );
              })}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Positions grid ───────────────────────────────────────────── */}
      <div className="px-8 pt-6 pb-8 flex-1">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <p className="font-mono text-[9px] uppercase tracking-[0.25em] text-muted-foreground">
              All positions
            </p>
            <span className="font-mono text-[9px] text-primary/50">({holdings.length})</span>
          </div>
          <p className="font-mono text-[9px] uppercase tracking-[0.15em] text-muted-foreground/40 hidden sm:block">
            Sorted by status · value
          </p>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
          {sortedHoldings.map((h, i) => (
            <PositionCard
              key={h.id}
              holding={h}
              thesis={thesesByHolding[h.id]}
              pulse={pulseByHolding[h.id]}
              earnings={earningsByHolding[h.id]}
              livePrice={livePrices[h.ticker]}
              totalValue={summary?.total_value ?? 0}
              onGenerateDraft={() => handleGenerateDraft(h.id, h.ticker)}
              index={i}
            />
          ))}
        </div>
      </div>

      {/* ── Footer strip ─────────────────────────────────────────────── */}
      {(upcomingEarnings.length > 0) && (
        <div className="border-t border-border bg-card px-8 py-3">
          <div className="flex items-center gap-6 overflow-x-auto">
            <p className="font-mono text-[9px] uppercase tracking-[0.25em] text-muted-foreground shrink-0">
              Upcoming earnings
            </p>
            <div className="flex items-center gap-4">
              {upcomingEarnings.slice(0, 6).map((e) => (
                <Link
                  key={e.holding_id}
                  href={`/dashboard/positions/${e.ticker}`}
                  className="flex items-center gap-2 group shrink-0"
                >
                  <span className="font-mono text-[10px] font-medium text-primary/70 group-hover:text-primary transition-colors">
                    {cleanTicker(e.ticker)}
                  </span>
                  <span className="font-mono text-[9px] text-muted-foreground">
                    {e.days_until === 0 ? "today" : e.days_until === 1 ? "tomorrow" : `${e.days_until}d`}
                  </span>
                </Link>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
