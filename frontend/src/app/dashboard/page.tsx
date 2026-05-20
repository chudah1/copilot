"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import useSWR from "swr";
import { api, fetcher } from "@/lib/api";
import { getErrorMessage } from "@/lib/errors";
import { formatCurrency, formatPercent } from "@/lib/utils";
import { OnboardingBanner } from "@/components/onboarding/onboarding-banner";
import { QuickAddHolding } from "@/components/portfolio/quick-add-holding";
import { DigestCountdown } from "@/components/portfolio/digest-countdown";
import { PositionCard, cleanTicker } from "@/components/portfolio/position-card";
import { AttentionCard } from "@/components/portfolio/attention-card";
import { DashboardSkeleton } from "@/components/portfolio/dashboard-skeleton";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { toast } from "sonner";
import type {
  DraftStatus,
  Holding,
  LivePrice,
  OnboardingState,
  PortfolioSummary,
  Thesis,
  PortfolioPulse,
  QuarterlyReviewCurrent,
  UpcomingEarnings,
} from "@/types";

// Extracted PositionCard and AttentionCard to src/components/portfolio/

function dashboardCopy(investorProfile: "thesis_driven" | "hearsay_driven" | null) {
  if (investorProfile === "thesis_driven") {
    return {
      emptyBody:
        "The market will test your assumptions. Add your positions below and write down exactly why you own them so you can tell when the thesis changes.",
      draftBanner:
        "We drafted working thesis notes for {count}. Review them and tighten the assumptions before monitoring does the rest.",
      quarterly:
        "Quarterly review — {count} position{plural} waiting for a fresh underwriting call",
    };
  }

  if (investorProfile === "hearsay_driven") {
    return {
      emptyBody:
        "The market will test the story. Add your positions below and write down why you own them so you can tell signal from panic when things move fast.",
      draftBanner:
        "We drafted clearer reasons for {count}. Review them and turn the story into something you can actually monitor.",
      quarterly:
        "Quarterly review — {count} position{plural} waiting to see if the original story still holds",
    };
  }

  return {
    emptyBody:
      "The market will test you. Add your positions below and write down exactly why you own them so you don&rsquo;t panic sell when things get tough.",
    draftBanner:
      "We found some notes to help articulate your conviction for {count}.",
    quarterly:
      "Quarterly review — {count} position{plural} awaiting judgement",
  };
}

// ── Dashboard ──────────────────────────────────────────────────────────────

export default function DashboardPage() {
  const [draftBannerDismissed, setDraftBannerDismissed] = useState(false);
  const [showAddForm, setShowAddForm] = useState(false);
  const [onboardingBannerVisible, setOnboardingBannerVisible] = useState(false);

  // SWR queries
  const { data: holdings, error: holdingsError, mutate: mutateHoldings } = useSWR<Holding[]>("/api/portfolio/holdings", fetcher);
  const { data: summary, error: summaryError, mutate: mutateSummary } = useSWR<PortfolioSummary>("/api/portfolio/summary", fetcher);
  const { data: currentTheses, error: thesesError, mutate: mutateTheses } = useSWR<Thesis[]>("/api/theses/current", fetcher);
  const { data: pulse, error: pulseError, mutate: mutatePulse } = useSWR<PortfolioPulse>("/api/portfolio/pulse", fetcher);
  const { data: upcomingEarnings = [] } = useSWR<UpcomingEarnings[]>("/api/portfolio/upcoming-earnings", fetcher, { fallbackData: [] });
  const { data: quarterlyReview = null } = useSWR<QuarterlyReviewCurrent>("/api/quarterly-review/current", fetcher);
  const { data: draftStatus = null, mutate: mutateDraftStatus } = useSWR<DraftStatus>("/api/portfolio/draft-status", fetcher);
  const { data: onboardingState = null } = useSWR<OnboardingState>("/api/onboarding/state", fetcher);
  const copy = dashboardCopy(onboardingState?.investor_profile ?? null);

  // Live prices (updates in background every 60s)
  const { data: livePricesRaw } = useSWR<LivePrice[]>("/api/portfolio/live-prices", fetcher, {
    refreshInterval: 60_000,
    revalidateOnFocus: true,
  });

  const livePrices = useMemo(() => {
    if (!livePricesRaw) return {};
    return Object.fromEntries(livePricesRaw.map((p) => [p.ticker, p]));
  }, [livePricesRaw]);

  const refresh = async () => {
    await Promise.all([
      mutateHoldings(),
      mutateSummary(),
      mutateTheses(),
      mutatePulse(),
      mutateDraftStatus(),
    ]);
  };

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
  const thesesByHolding = useMemo(() => {
    if (!currentTheses) return {};
    return Object.fromEntries(currentTheses.map((t) => [t.holding_id, t]));
  }, [currentTheses]);

  const hasLivePrices = Object.keys(livePrices).length > 0;
  const liveTotalValue = useMemo(() => {
    if (!holdings || !hasLivePrices) return null;
    return holdings.reduce((sum, h) => sum + (livePrices[h.ticker]?.current_value ?? h.current_value ?? 0), 0);
  }, [holdings, livePrices, hasLivePrices]);

  const displayTotalValue = liveTotalValue ?? summary?.total_value ?? 0;
  const livePnl = liveTotalValue != null && summary ? liveTotalValue - summary.total_cost : null;
  const livePnlPct = livePnl != null && summary && summary.total_cost > 0 ? (livePnl / summary.total_cost) * 100 : null;
  
  const pulseByHolding = useMemo(() => {
    if (!pulse?.pulses) return {};
    return Object.fromEntries(pulse.pulses.map((p) => [p.holding_id, p]));
  }, [pulse]);

  const earningsByHolding = useMemo(() => {
    if (!upcomingEarnings) return {};
    return Object.fromEntries(upcomingEarnings.map((e) => [e.holding_id, e]));
  }, [upcomingEarnings]);

  // Attention = real monitoring signals only (watch/review from events), not "no thesis" bookkeeping
  const needsAttention = useMemo(() => {
    if (!pulse?.pulses) return [];
    return pulse.pulses.filter(
      (p) => (p.pulse_status === "review" || p.pulse_status === "watch") && p.has_thesis,
    );
  }, [pulse]);

  const reviewCount = useMemo(() => {
    return needsAttention.filter((p) => p.pulse_status === "review").length;
  }, [needsAttention]);

  const missingThesisCount = summary?.theses_missing ?? 0;

  const sortedHoldings = useMemo(() => {
    if (!holdings) return [];
    return [...holdings].sort((a, b) => {
      const pa = pulseByHolding[a.id]?.pulse_status ?? "intact";
      const pb = pulseByHolding[b.id]?.pulse_status ?? "intact";
      const order: Record<string, number> = { review: 0, watch: 1, intact: 2 };
      const diff = (order[pa] ?? 2) - (order[pb] ?? 2);
      if (diff !== 0) return diff;
      return (b.current_value ?? 0) - (a.current_value ?? 0);
    });
  }, [holdings, pulseByHolding]);

  // Loading state
  const loading = !holdings && !holdingsError;

  if (loading) {
    return <DashboardSkeleton />;
  }

  // Error state
  const loadError = holdingsError || summaryError || thesesError || pulseError;

  if (loadError && (!holdings || holdings.length === 0)) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[calc(100vh-54px)] gap-4 text-center px-6">
        <p className="font-sans text-sm text-muted-foreground">
          {getErrorMessage(loadError, "Failed to load portfolio")}
        </p>
        <button
          onClick={() => void refresh()}
          className="font-mono text-[10px] uppercase tracking-[0.2em] text-primary border border-primary/30 px-4 py-2 hover:bg-primary/5 transition-colors"
        >
          Retry
        </button>
      </div>
    );
  }

  // Empty state
  if (!holdings || holdings.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[calc(100vh-54px)] gap-8 text-center px-6">
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="space-y-3 max-w-sm"
        >
          <div className="border-t-2 border-foreground pt-4">
            <p className="font-display italic text-3xl text-foreground">Write it down.</p>
          </div>
          <div className="border-b-2 border-foreground" />
          <p className="font-sans text-sm text-muted-foreground leading-relaxed pt-1">
            {copy.emptyBody}
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
              <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground mb-1">
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
                  <span className="flex items-center gap-1 font-mono text-[10px] uppercase tracking-[0.12em] text-emerald-600">
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
                  <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground mt-0.5">
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
              <button className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground hover:text-foreground transition-colors border border-border px-3 py-1.5 hover:border-foreground/30">
                Simulate
              </button>
            </Link>
            <button
              onClick={() => setShowAddForm((v) => !v)}
              className={`font-mono text-[10px] uppercase tracking-[0.14em] transition-colors border px-3 py-1.5 ${
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
        <ErrorBoundary>
          <OnboardingBanner onVisibilityChange={setOnboardingBannerVisible} />
        </ErrorBoundary>

        {!onboardingBannerVisible && draftStatus && draftStatus.ready > 0 && !draftBannerDismissed && (
          <div className="flex items-center justify-between border border-primary/25 bg-primary/5 px-5 py-2.5">
            <div className="flex items-center gap-3">
              <span className="font-mono text-[10px] uppercase tracking-[0.15em] text-primary border border-primary/30 px-1.5 py-0.5">
                New
              </span>
              <p className="font-sans text-sm text-foreground/80">
                {copy.draftBanner.replace(
                  "{count}",
                  draftStatus.ready === 1 ? "1 position" : `${draftStatus.ready} positions`,
                )}
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
              <span className="font-mono text-[10px] uppercase tracking-[0.15em] text-primary">{quarterlyReview.quarter}</span>
              <p className="font-sans text-sm text-foreground/80">
                {copy.quarterly
                  .replace("{count}", String(quarterlyReview.pending_count))
                  .replace("{plural}", quarterlyReview.pending_count > 1 ? "s" : "")}
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
              <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                Needs attention
              </p>
              <span className="font-mono text-[10px] text-primary/60">({needsAttention.length})</span>
            </div>
            <ErrorBoundary>
              <div className="flex gap-3 overflow-x-auto pb-1 scrollbar-hide">
                {needsAttention.map((p, i) => {
                  const holding = holdings.find((h) => h.id === p.holding_id);
                  if (!holding) return null;
                  return (
                    <AttentionCard key={p.holding_id} holding={holding} pulse={p} index={i} />
                  );
                })}
              </div>
            </ErrorBoundary>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Positions grid ───────────────────────────────────────────── */}
      <div className="px-8 pt-6 pb-8 flex-1">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
              All positions
            </p>
            <span className="font-mono text-[10px] text-primary/50">({holdings.length})</span>
          </div>
          <p className="font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground/40 hidden sm:block">
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
              investorProfile={onboardingState?.investor_profile ?? null}
              index={i}
            />
          ))}
        </div>
      </div>

      {/* ── Footer strip ─────────────────────────────────────────────── */}
      {(upcomingEarnings.length > 0) && (
        <ErrorBoundary>
          <div className="border-t border-border bg-card px-8 py-3">
            <div className="flex items-center gap-6 overflow-x-auto">
              <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground shrink-0">
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
                    <span className="font-mono text-[10px] text-muted-foreground">
                      {e.days_until === 0 ? "today" : e.days_until === 1 ? "tomorrow" : `${e.days_until}d`}
                    </span>
                  </Link>
                ))}
              </div>
            </div>
          </div>
        </ErrorBoundary>
      )}
    </div>
  );
}
