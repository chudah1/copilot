"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import {
  ArrowRight,
  BellRing,
  CalendarClock,
  CircleAlert,
} from "lucide-react";
import useSWR from "swr";
import { api, fetcher } from "@/lib/api";
import { formatAssumptionLabel } from "@/lib/assumption-label";
import { getErrorMessage } from "@/lib/errors";
import { buildDecisionInbox } from "@/lib/decision-inbox";
import type { DecisionInboxEntry } from "@/lib/decision-inbox";
import { formatCurrency, formatPercent } from "@/lib/utils";
import { OnboardingBanner } from "@/components/onboarding/onboarding-banner";
import { QuickAddHolding } from "@/components/portfolio/quick-add-holding";
import { SinceLastVisit } from "@/components/portfolio/since-last-visit";
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
  PortfolioTrend,
  Thesis,
  PortfolioPulse,
  QuarterlyReviewCurrent,
  UpcomingEarnings,
} from "@/types";

interface RecentReviewBannerState {
  ticker: string;
  action: "reaffirmed" | "ignored" | "lowered_confidence" | "invalidated" | "not_relevant";
  assumption_label: string | null;
  resolved_all: boolean;
  thesis_status: Thesis["status"];
  saved_at: string;
}

// Extracted PositionCard and AttentionCard to src/components/portfolio/

function dashboardCopy(investorProfile: "thesis_driven" | "hearsay_driven" | null) {
  if (investorProfile === "thesis_driven") {
    return {
      emptyBody:
        "The market will test your assumptions. Add your positions below and write down exactly why you own them so you can tell when the thesis changes.",
      draftBanner:
        "Drafts are ready for {count}. Review them before monitoring takes over.",
      quarterly:
        "Quarterly review — {count} position{plural} due",
    };
  }

  if (investorProfile === "hearsay_driven") {
    return {
      emptyBody:
        "The market will test the story. Add your positions below and write down why you own them so you can tell signal from panic when things move fast.",
      draftBanner:
        "Drafts are ready for {count}. Review them before monitoring takes over.",
      quarterly:
        "Quarterly review — {count} position{plural} due",
    };
  }

  return {
    emptyBody:
      "The market will test you. Add your positions below and write down exactly why you own them so you don't panic sell when things get tough.",
    draftBanner:
      "Drafts are ready for {count}. Review them before monitoring takes over.",
    quarterly:
      "Quarterly review — {count} position{plural} due",
  };
}

function dashboardStateCopy(
  investorProfile: "thesis_driven" | "hearsay_driven" | null,
  counts: { review: number; watch: number; missing: number },
  nextEarnings: UpcomingEarnings | null,
  topAttention: PortfolioPulse["pulses"][number] | null,
  recentReview: RecentReviewBannerState | null,
) {
  const topAttentionLabel = formatAssumptionLabel(topAttention?.assumption_label, investorProfile, { maxLength: 72 });
  if (counts.review > 0) {
    return {
      tone: "border-amber-500/25 bg-amber-500/8",
      eyebrow: "Needs a decision",
      title:
        investorProfile === "hearsay_driven"
          ? `${counts.review} position${counts.review > 1 ? "s need" : " needs"} a call.`
          : `${counts.review} position${counts.review > 1 ? "s need" : " needs"} a call.`,
      body:
        topAttention
          ? `${cleanTicker(topAttention.ticker)} first. ${topAttentionLabel} is closest to a call.${recentReview ? ` ${cleanTicker(recentReview.ticker)} cleared.` : ""}`
          : counts.watch > 0
            ? `${counts.watch} more position${counts.watch > 1 ? "s are" : " is"} on watch behind it.`
            : "Start with the review items.",
    };
  }

  if (counts.watch > 0) {
    return {
      tone: "border-sky-500/25 bg-sky-500/8",
      eyebrow: "Changed",
      title:
        investorProfile === "hearsay_driven"
          ? `${counts.watch} position${counts.watch > 1 ? "s need" : " needs"} a look.`
          : `${counts.watch} position${counts.watch > 1 ? "s need" : " needs"} a look.`,
      body: topAttention
        ? `${cleanTicker(topAttention.ticker)} first. ${topAttentionLabel} is still unresolved.${recentReview ? ` ${cleanTicker(recentReview.ticker)} cleared.` : ""}`
        : "Nothing looks broken. These names still need a look.",
    };
  }

  if (counts.missing > 0) {
    return {
      tone: "border-border bg-card",
      eyebrow: "Needs a written case",
      title:
        investorProfile === "hearsay_driven"
          ? `${counts.missing} position${counts.missing > 1 ? "s need" : " needs"} a reason.`
          : `${counts.missing} position${counts.missing > 1 ? "s need" : " needs"} a thesis.`,
      body:
        investorProfile === "hearsay_driven"
          ? "Price and news are visible. Your reason is not."
          : "Price and news are visible. Your thesis is not.",
    };
  }

  return {
    tone: "border-emerald-500/25 bg-emerald-500/8",
    eyebrow: "Calm",
    title: "Nothing needs a call right now.",
    body: nextEarnings
      ? `${cleanTicker(nextEarnings.ticker)} is the next likely decision point in ${nextEarnings.days_until === 0 ? "today" : nextEarnings.days_until === 1 ? "1 day" : `${nextEarnings.days_until} days`}.${recentReview ? ` ${cleanTicker(recentReview.ticker)} was just resolved.` : ""}`
      : recentReview
        ? `${cleanTicker(recentReview.ticker)} was just resolved. Nothing else needs attention right now.`
        : "No live pressure. Tighten an overdue or weak case next.",
  };
}

function dashboardStateCta(args: {
  primaryEntry: DecisionInboxEntry | null;
  nearTermEarnings: UpcomingEarnings | null;
}) {
  const { primaryEntry, nearTermEarnings } = args;
  if (!primaryEntry) return null;
  const ticker = primaryEntry.holding.ticker;

  if (primaryEntry.decisionState.kind === "needs_decision") {
    return {
      href: `/dashboard/positions/${ticker}?tab=monitoring`,
      label: `Review ${cleanTicker(ticker)} →`,
    };
  }

  if (primaryEntry.decisionState.kind === "changed") {
    return {
      href: `/dashboard/positions/${ticker}?tab=monitoring`,
      label: `Open ${cleanTicker(ticker)} →`,
    };
  }

  if (primaryEntry.decisionState.kind === "needs_written_case") {
    return {
      href: `/dashboard/positions/${ticker}?source=dashboard_blind_spot`,
      label: `Write ${cleanTicker(ticker)} →`,
    };
  }

  if (nearTermEarnings?.holding_id === primaryEntry.holding.id) {
    return {
      href: `/dashboard/positions/${ticker}`,
      label: `Open ${cleanTicker(ticker)} before earnings →`,
    };
  }

  return {
    href: `/dashboard/positions/${ticker}`,
    label: `Open ${cleanTicker(ticker)} →`,
  };
}

function isRecentIsoDate(value: string | null | undefined, days: number) {
  if (!value) return false;
  const ts = new Date(value).getTime();
  if (Number.isNaN(ts)) return false;
  return Date.now() - ts <= days * 24 * 60 * 60 * 1000;
}

function isRecentIsoHours(value: string | null | undefined, hours: number) {
  if (!value) return false;
  const ts = new Date(value).getTime();
  if (Number.isNaN(ts)) return false;
  return Date.now() - ts <= hours * 60 * 60 * 1000;
}

function daysUntilLabel(days: number) {
  if (days === 0) return "today";
  if (days === 1) return "tomorrow";
  return `${days} days`;
}

function activationBannerCopy(args: {
  investorProfile: "thesis_driven" | "hearsay_driven" | null;
  count: number;
  tickers: string[];
}) {
  const { investorProfile, count, tickers } = args;
  const joinedTickers = tickers.length > 0 ? tickers.join(", ") : "your positions";

  if (investorProfile === "hearsay_driven") {
    return {
      eyebrow: "Portfolio activated",
      title:
        count === 1
          ? `Monitoring is live for ${joinedTickers}.`
          : `Monitoring is live for ${joinedTickers}.`,
      body:
        "We'll stay quiet unless the story gets tested.",
    };
  }

  if (investorProfile === "thesis_driven") {
    return {
      eyebrow: "Portfolio activated",
      title:
        count === 1
          ? `Monitoring is live for ${joinedTickers}.`
          : `Monitoring is live for ${joinedTickers}.`,
      body:
        "We'll stay quiet unless an assumption gets tested.",
    };
  }

  return {
    eyebrow: "Portfolio activated",
    title:
      count === 1
        ? `Monitoring is live for ${joinedTickers}.`
        : `Monitoring is live for ${joinedTickers}.`,
    body:
      "We'll stay quiet unless something important changes.",
  };
}

function recentReviewBannerCopy(
  review: RecentReviewBannerState,
  investorProfile: "thesis_driven" | "hearsay_driven" | null,
) {
  const target = formatAssumptionLabel(review.assumption_label, investorProfile, {
    maxLength: 64,
    sentenceCaseFallback: true,
  });
  const ticker = cleanTicker(review.ticker);

  if (review.action === "invalidated" || review.thesis_status === "invalidated") {
    return {
      eyebrow: "Reviewed just now",
      title: `${target} was marked broken for ${ticker}.`,
      body:
        investorProfile === "hearsay_driven"
          ? "That position now needs a rewritten reason or an exit call."
          : "That position now needs a rewritten thesis or an exit call.",
      href: `/dashboard/positions/${review.ticker}`,
      cta: investorProfile === "hearsay_driven" ? "Rewrite →" : "Rewrite →",
    };
  }

  return {
    eyebrow: "Reviewed just now",
    title: `${target} was reviewed for ${ticker}.`,
    body: review.resolved_all
      ? (investorProfile === "hearsay_driven"
          ? "That reason is back to quiet unless the story gets tested again."
          : "That thesis is back to quiet unless it gets tested again.")
      : "That review is on record. Other items are still waiting.",
    href: `/dashboard/positions/${review.ticker}`,
    cta: "Open position →",
  };
}

// ── Dashboard ──────────────────────────────────────────────────────────────

function DashboardInner() {
  const searchParams = useSearchParams();
  const [draftBannerDismissed, setDraftBannerDismissed] = useState(false);
  const [showAddForm, setShowAddForm] = useState(false);
  const [onboardingBannerVisible, setOnboardingBannerVisible] = useState(false);
  const [activationBannerDismissed, setActivationBannerDismissed] = useState(() => {
    if (typeof window === "undefined") return false;
    return window.localStorage.getItem("dashboard_activation_banner_dismissed") === "1";
  });
  const [recentReviewBanner, setRecentReviewBanner] = useState<RecentReviewBannerState | null>(() => {
    if (typeof window === "undefined") return null;
    const raw = window.localStorage.getItem("dashboard_recent_review");
    if (!raw) return null;
    try {
      const parsed = JSON.parse(raw) as RecentReviewBannerState;
      if (!isRecentIsoHours(parsed.saved_at, 2)) {
        window.localStorage.removeItem("dashboard_recent_review");
        return null;
      }
      return parsed;
    } catch {
      return null;
    }
  });

  // SWR queries
  const { data: holdings, error: holdingsError, mutate: mutateHoldings } = useSWR<Holding[]>("/api/portfolio/holdings", fetcher);
  const { data: summary, error: summaryError, mutate: mutateSummary } = useSWR<PortfolioSummary>("/api/portfolio/summary", fetcher);
  const { data: trend = null } = useSWR<PortfolioTrend>("/api/portfolio/summary/trend", fetcher);
  const { data: currentTheses, error: thesesError, mutate: mutateTheses } = useSWR<Thesis[]>("/api/theses/current", fetcher);
  const { data: pulse, error: pulseError, mutate: mutatePulse } = useSWR<PortfolioPulse>("/api/portfolio/pulse", fetcher);
  const { data: upcomingEarnings = [] } = useSWR<UpcomingEarnings[]>("/api/portfolio/upcoming-earnings", fetcher, { fallbackData: [] });
  const { data: quarterlyReview = null } = useSWR<QuarterlyReviewCurrent>("/api/quarterly-review/current", fetcher);
  const { data: draftStatus = null, mutate: mutateDraftStatus } = useSWR<DraftStatus>("/api/portfolio/draft-status", fetcher);
  const { data: onboardingState = null } = useSWR<OnboardingState>("/api/onboarding/state", fetcher);
  const investorProfile = onboardingState?.investor_profile ?? null;
  const copy = dashboardCopy(investorProfile);

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
  const decisionInbox = useMemo(() => buildDecisionInbox({
    holdings: holdings ?? [],
    theses: currentTheses ?? [],
    pulses: pulse?.pulses ?? [],
    upcomingEarnings,
  }), [holdings, currentTheses, pulse, upcomingEarnings]);
  const thesesByHolding = decisionInbox.thesesByHoldingId;

  const hasLivePrices = Object.keys(livePrices).length > 0;
  const liveTotalValue = useMemo(() => {
    if (!holdings || !hasLivePrices) return null;
    return holdings.reduce((sum, h) => sum + (livePrices[h.ticker]?.current_value ?? h.current_value ?? 0), 0);
  }, [holdings, livePrices, hasLivePrices]);

  const displayTotalValue = liveTotalValue ?? summary?.total_value ?? 0;
  const livePnl = liveTotalValue != null && summary ? liveTotalValue - summary.total_cost : null;
  const livePnlPct = livePnl != null && summary && summary.total_cost > 0 ? (livePnl / summary.total_cost) * 100 : null;

  const pulseByHolding = decisionInbox.pulsesByHoldingId;
  const earningsByHolding = decisionInbox.earningsByHoldingId;
  const needsAttention = decisionInbox.attentionEntries.flatMap((entry) => entry.pulse ? [entry.pulse] : []);
  const reviewCount = decisionInbox.counts.needsDecision;
  const missingThesisCount = decisionInbox.counts.needsWrittenCase;
  const nearTermEarnings = decisionInbox.nearTermEarnings;
  const visibleEarnings = decisionInbox.visibleEarnings;
  const dashboardState = dashboardStateCopy(
    onboardingState?.investor_profile ?? null,
    { review: reviewCount, watch: decisionInbox.counts.changed, missing: missingThesisCount },
    nearTermEarnings,
    needsAttention[0] ?? null,
    recentReviewBanner,
  );
  const dashboardStatePrimaryCta = dashboardStateCta({
    primaryEntry: decisionInbox.primaryEntry,
    nearTermEarnings,
  });
  const caseQualityStats = decisionInbox.caseQualityCounts;
  const weakestHolding = decisionInbox.weakestCaseEntry?.holding ?? null;
  const weakestQuality = decisionInbox.weakestCaseEntry?.caseQuality ?? null;
  const caseQualityHeadline =
    caseQualityStats.missing > 0
      ? weakestHolding
        ? investorProfile === "hearsay_driven"
          ? `${cleanTicker(weakestHolding.ticker)} has no reason yet.`
          : `${cleanTicker(weakestHolding.ticker)} has no thesis yet.`
        : investorProfile === "hearsay_driven"
          ? `${caseQualityStats.missing} ${caseQualityStats.missing === 1 ? "position has" : "positions have"} no reason yet.`
          : `${caseQualityStats.missing} ${caseQualityStats.missing === 1 ? "position has" : "positions have"} no thesis yet.`
      : caseQualityStats.weak > 0
        ? `${caseQualityStats.weak} ${caseQualityStats.weak === 1 ? "thesis is" : "theses are"} still too fuzzy.`
        : caseQualityStats.review_overdue > 0
          ? `${caseQualityStats.review_overdue} ${caseQualityStats.review_overdue === 1 ? "thesis is" : "theses are"} overdue for a fresh read.`
          : caseQualityStats.workable > 0
            ? `${caseQualityStats.workable} ${caseQualityStats.workable === 1 ? "thesis is" : "theses are"} usable but not sharp yet.`
            : "Your written thinking looks sharp across the portfolio.";
  const caseQualityDetail =
    caseQualityStats.missing > 0
      ? investorProfile === "hearsay_driven"
        ? "Write the reason, then monitoring can judge it."
        : "Write the thesis, then monitoring can judge it."
      : caseQualityStats.weak > 0
        ? "These theses are still too fuzzy to trust under pressure."
      : caseQualityStats.review_overdue > 0
        ? "Nothing changed, but old reasoning is harder to rely on when the next decision arrives."
        : caseQualityStats.workable > 0
          ? "Usable, but still not crisp enough to trust fully under pressure."
          : "Most positions now have explicit, current thinking behind them."
  const caseQualityCta = weakestHolding
    ? {
        href: `/dashboard/positions/${weakestHolding.ticker}`,
        label:
          weakestQuality?.kind === "missing"
            ? investorProfile === "hearsay_driven"
              ? `Write ${cleanTicker(weakestHolding.ticker)} →`
              : `Write ${cleanTicker(weakestHolding.ticker)} →`
            : weakestQuality?.kind === "review_overdue"
              ? `Refresh ${cleanTicker(weakestHolding.ticker)} →`
            : weakestQuality?.kind === "weak" || weakestQuality?.kind === "workable"
              ? `Tighten ${cleanTicker(weakestHolding.ticker)} →`
              : `Open ${cleanTicker(weakestHolding.ticker)} →`,
      }
    : null;

  const sortedHoldings = decisionInbox.entries.map((entry) => entry.holding);

  const recentActivation = isRecentIsoDate(onboardingState?.wizard_completed_at, 7) || isRecentIsoDate(onboardingState?.drafts_reviewed_at, 7);
  const activationSource = searchParams.get("source");
  const forcedActivationContext = activationSource === "review_drafts" || activationSource === "onboarding";
  const activatedTickers = useMemo(() => {
    if (!currentTheses) return [];
    return currentTheses
      .slice()
      .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())
      .slice(0, 3)
      .map((thesis) => {
        const holding = holdings?.find((item) => item.id === thesis.holding_id);
        return holding ? cleanTicker(holding.ticker) : null;
      })
      .filter((ticker): ticker is string => Boolean(ticker));
  }, [currentTheses, holdings]);
  const showActivationBanner = (recentActivation || forcedActivationContext) && !activationBannerDismissed && (currentTheses?.length ?? 0) > 0;
  const activationCopy = activationBannerCopy({
    investorProfile: onboardingState?.investor_profile ?? null,
    count: currentTheses?.length ?? 0,
    tickers: activatedTickers,
  });
  useEffect(() => {
    if (showActivationBanner) {
      window.localStorage.setItem("dashboard_activation_banner_dismissed", "1");
      // eslint-disable-next-line react-hooks/set-state-in-effect -- persist once-shown; behavior predates this change
      setActivationBannerDismissed(true);
    }
  }, [showActivationBanner]);

  const showRecentReviewBanner = Boolean(
    recentReviewBanner && isRecentIsoHours(recentReviewBanner.saved_at, 2),
  );
  const recentReviewCopy = recentReviewBanner
    ? recentReviewBannerCopy(recentReviewBanner, onboardingState?.investor_profile ?? null)
    : null;
  const shouldRenderOnboardingBanner = missingThesisCount === 0;

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
          {/* Single CTA — /connect already presents Manual, CSV, and
              Trading 212 as tabs (Manual is the default), so a "Connect
              broker" label plus a broken "Add manually" split button was
              both incorrect and confusing. */}
          <Link href="/connect">
            <button className="px-5 py-2.5 font-mono text-[11px] uppercase tracking-[0.15em] bg-primary text-primary-foreground hover:bg-primary/90 transition-colors">
              Add position
            </button>
          </Link>
        </motion.div>
      </div>
    );
  }

  // ── Main dashboard ───────────────────────────────────────────────────
  return (
    <div className="min-h-[calc(100vh-84px)] flex flex-col pb-8">
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.35 }}
        className="relative border-b border-border/80 px-4 py-5 sm:px-8 sm:py-7"
      >
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(121,83,48,0.18),transparent_30%),linear-gradient(180deg,rgba(255,255,255,0.35),transparent_80%)]"
        />
        <div className="relative">
          <section id="dashboard-overview" className="product-panel product-panel-muted overflow-hidden p-5 sm:p-6 scroll-mt-24">
            <div className="grid gap-5 lg:grid-cols-[minmax(0,1.55fr)_minmax(17rem,23rem)]">
              <div className="space-y-4">
                <div>
                  <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-muted-foreground">
                    Decision inbox
                  </p>
                  <h1 className="mt-2 font-display text-[2rem] italic leading-tight text-foreground sm:text-[2.5rem]">
                    What needs your attention.
                  </h1>
                </div>

                <div className={`border px-5 py-5 sm:px-6 sm:py-6 ${dashboardState.tone}`}>
                  <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-foreground/60">
                    {dashboardState.eyebrow}
                  </p>
                  <p className="mt-2 font-display text-[1.65rem] italic leading-tight text-foreground sm:text-[2rem]">
                    {dashboardState.title}
                  </p>
                  <p className="mt-2 max-w-2xl font-sans text-sm leading-relaxed text-foreground/85">
                    {dashboardState.body}
                  </p>
                  {dashboardStatePrimaryCta && (
                    <Link
                      href={dashboardStatePrimaryCta.href}
                      className="mt-5 inline-flex items-center gap-2 border border-primary/25 bg-background/70 px-3 py-2 font-mono text-[10px] uppercase tracking-[0.16em] text-primary transition-colors hover:border-primary/50"
                    >
                      {dashboardStatePrimaryCta.label.replace(" →", "")}
                      <ArrowRight className="h-3.5 w-3.5" />
                    </Link>
                  )}
                </div>

                {summary && (
                  <SinceLastVisit summary={summary} trend={trend} />
                )}
              </div>

              <aside className="border border-border/80 bg-background/70 p-4 sm:p-5">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                      Portfolio snapshot
                    </p>
                    <div className="mt-3 flex flex-wrap items-baseline gap-2">
                      <span className="font-display text-[1.9rem] italic leading-none tracking-tight text-foreground">
                        {formatCurrency(displayTotalValue)}
                      </span>
                      {(livePnlPct != null ? livePnlPct : summary?.total_pnl_pct) != null && (
                        <span className={`font-mono text-[10px] tabular-nums ${
                          (livePnl ?? summary?.total_pnl ?? 0) >= 0 ? "text-emerald-700" : "text-red-600"
                        }`}>
                          {formatPercent(livePnlPct ?? summary?.total_pnl_pct ?? 0)}
                        </span>
                      )}
                    </div>
                    <p className="mt-2 font-sans text-xs text-muted-foreground">
                      {holdings.length} position{holdings.length === 1 ? "" : "s"}
                      {hasLivePrices ? " · prices checked recently" : ""}
                    </p>
                  </div>
                </div>

                <div className="mt-5 space-y-3 border-t border-border/60 pt-4">
                  <div className="flex items-start gap-3">
                    <CircleAlert className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                    <div className="space-y-1">
                      <p className="font-sans text-sm leading-relaxed text-foreground/85">
                        {caseQualityHeadline}
                      </p>
                      <p className="font-sans text-xs leading-relaxed text-muted-foreground">
                        {caseQualityDetail}
                      </p>
                      {caseQualityCta && (
                        <Link href={caseQualityCta.href} className="inline-flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-[0.14em] text-primary hover:text-primary/75">
                          {caseQualityCta.label.replace(" →", "")}
                          <ArrowRight className="h-3 w-3" />
                        </Link>
                      )}
                    </div>
                  </div>

                  <div className="flex items-start gap-3 border-t border-border/60 pt-3">
                    <CalendarClock className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                    <p className="font-sans text-sm leading-relaxed text-foreground/85">
                      {nearTermEarnings
                        ? `${cleanTicker(nearTermEarnings.ticker)} reports ${daysUntilLabel(nearTermEarnings.days_until)}.`
                        : "No earnings need preparation in the next three weeks."}
                    </p>
                  </div>

                  {pulse?.next_digest_at && (
                    <div className="flex items-start gap-3 border-t border-border/60 pt-3">
                      <BellRing className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                      <div className="space-y-1">
                        <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
                          Next written digest
                        </p>
                        <DigestCountdown nextDigestAt={pulse.next_digest_at} />
                      </div>
                    </div>
                  )}
                </div>

                <div className="mt-5 flex flex-wrap gap-2 border-t border-border/60 pt-4">
                  <Link href="/dashboard/simulate" className="border border-border/80 px-3 py-2 font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground hover:text-foreground">
                    Simulate trade
                  </Link>
                  <Link href="/connect?return=dashboard" className="border border-border/80 px-3 py-2 font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground hover:text-foreground">
                    Import data
                  </Link>
                </div>
              </aside>
            </div>
          </section>
        </div>
      </motion.div>

      {/* ── Banners ─────────────────────────────────────────────────── */}
      <div className="px-4 pt-3 sm:px-8 space-y-2 empty:hidden">
        {/* Only one contextual banner at a time — recent review takes priority over activation */}
        {showActivationBanner && !showRecentReviewBanner && (
          <div className="flex items-center justify-between gap-4 border border-emerald-500/20 bg-emerald-500/8 px-5 py-3">
            <div className="space-y-1">
              <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-emerald-700">
                {activationCopy.eyebrow}
              </p>
              <p className="font-sans text-sm text-foreground/85">
                {activationCopy.title}
              </p>
              <p className="font-sans text-xs text-foreground/80">
                {activationCopy.body}
              </p>
            </div>
            <button
              onClick={() => {
                setActivationBannerDismissed(true);
                if (typeof window !== "undefined") {
                  window.localStorage.setItem("dashboard_activation_banner_dismissed", "1");
                }
              }}
              className="text-muted-foreground hover:text-foreground text-sm leading-none transition-colors shrink-0"
              aria-label="Dismiss activation banner"
            >
              ✕
            </button>
          </div>
        )}

        {showRecentReviewBanner && recentReviewCopy && (
          <div className="flex items-center justify-between gap-4 border border-sky-500/25 bg-sky-500/8 px-5 py-3">
            <div className="space-y-1">
              <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-sky-700">
                {recentReviewCopy.eyebrow}
              </p>
              <p className="font-sans text-sm text-foreground/85">
                {recentReviewCopy.title}
              </p>
              <p className="font-sans text-xs text-foreground/80">
                {recentReviewCopy.body}
              </p>
              <Link
                href={recentReviewCopy.href}
                className="inline-block font-mono text-[10px] uppercase tracking-[0.15em] text-primary hover:text-primary/75 transition-colors"
              >
                {recentReviewCopy.cta}
              </Link>
            </div>
            <button
              onClick={() => {
                setRecentReviewBanner(null);
                if (typeof window !== "undefined") {
                  window.localStorage.removeItem("dashboard_recent_review");
                }
              }}
              className="text-muted-foreground hover:text-foreground text-sm leading-none transition-colors shrink-0"
              aria-label="Dismiss recent review banner"
            >
              ✕
            </button>
          </div>
        )}

        {shouldRenderOnboardingBanner && (
          <ErrorBoundary>
            <OnboardingBanner onVisibilityChange={setOnboardingBannerVisible} />
          </ErrorBoundary>
        )}

        {(() => {
          const noTheses = (summary?.theses_active ?? 0) === 0;
          const showDraft = !onboardingBannerVisible && (draftStatus?.ready ?? 0) > 0 && !draftBannerDismissed;
          const showQuarterly = !noTheses && (quarterlyReview?.pending_count ?? 0) > 0;
          if (!showDraft && !showQuarterly) return null;
          const draftCta = onboardingState?.investor_profile === "thesis_driven" ? "Review theses →"
            : onboardingState?.investor_profile === "hearsay_driven" ? "Review reasons →"
            : "Review →";
          const draftCount = draftStatus?.ready ?? 0;
          return (
            <div className="flex items-center justify-between border border-primary/25 bg-primary/5 px-5 py-2.5">
              <div className="flex items-center gap-3 min-w-0 flex-1">
                <span className="font-mono text-[10px] uppercase tracking-[0.15em] text-primary border border-primary/30 px-1.5 py-0.5 shrink-0">
                  {showQuarterly && quarterlyReview ? quarterlyReview.quarter : "New"}
                </span>
                <p className="font-sans text-sm text-foreground/80 truncate">
                  {showDraft && showQuarterly
                    ? `${draftCount === 1 ? "1 position" : `${draftCount} positions`} to review · ${quarterlyReview!.pending_count} quarterly check${quarterlyReview!.pending_count > 1 ? "s" : ""} due`
                    : showDraft
                      ? copy.draftBanner.replace("{count}", draftCount === 1 ? "1 position" : `${draftCount} positions`)
                      : copy.quarterly
                          .replace("{count}", String(quarterlyReview!.pending_count))
                          .replace("{plural}", quarterlyReview!.pending_count > 1 ? "s" : "")}
                </p>
              </div>
              <div className="flex items-center gap-4 shrink-0 ml-4">
                {showDraft && (
                  <Link href="/onboarding/review-drafts" className="font-mono text-[10px] uppercase tracking-[0.15em] text-primary hover:text-primary/70 transition-colors whitespace-nowrap">
                    {draftCta}
                  </Link>
                )}
                {showQuarterly && (
                  <Link href="/dashboard/quarterly-review" className="font-mono text-[10px] uppercase tracking-[0.15em] text-primary hover:text-primary/70 transition-colors whitespace-nowrap">
                    Quarterly →
                  </Link>
                )}
                {showDraft && (
                  <button onClick={() => setDraftBannerDismissed(true)} className="text-muted-foreground hover:text-foreground text-xs transition-colors">
                    ✕
                  </button>
                )}
              </div>
            </div>
          );
        })()}
      </div>


      <AnimatePresence>
        {needsAttention.length > 0 && (
          <motion.div
            id="live-pressure"
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, delay: 0.1 }}
            className="px-4 sm:px-8 pt-5 scroll-mt-24"
          >
            <div className="product-panel p-4 sm:p-5">
              <div className="mb-4 flex items-center justify-between gap-3">
                <div>
                  <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                    What changed
                  </p>
                  <p className="mt-1 font-sans text-sm text-foreground/80">
                    Evidence connected to something you wrote.
                  </p>
                </div>
                <span className="border border-primary/20 bg-primary/6 px-2 py-1 font-mono text-[10px] uppercase tracking-[0.14em] text-primary/75">
                  {needsAttention.length} to read
                </span>
              </div>
              <ErrorBoundary>
                <div className="flex gap-3 overflow-x-auto pb-1 scrollbar-hide">
                  {needsAttention.map((p, i) => {
                    const holding = holdings.find((h) => h.id === p.holding_id);
                    if (!holding) return null;
                    return (
                      <AttentionCard
                        key={p.holding_id}
                        holding={holding}
                        pulse={p}
                        investorProfile={onboardingState?.investor_profile ?? null}
                        index={i}
                      />
                    );
                  })}
                </div>
              </ErrorBoundary>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Positions grid ───────────────────────────────────────────── */}
      <div id="positions" className="px-4 sm:px-8 pt-6 pb-8 flex-1 scroll-mt-24">
        <div className="product-panel p-4 sm:p-5">
          <div className="mb-4 flex items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2">
                <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                  Positions
                </p>
                <span className="font-mono text-[10px] text-primary/50">({holdings.length})</span>
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <button
                onClick={() => setShowAddForm((v) => !v)}
                className={`border px-3 py-2 font-mono text-[10px] uppercase tracking-[0.16em] transition-colors ${
                  showAddForm
                    ? "border-border/80 text-muted-foreground"
                    : "border-primary/30 bg-primary/5 text-primary hover:border-primary/60"
                }`}
              >
                {showAddForm ? "Cancel" : "+ Add"}
              </button>
            </div>
          </div>

          <AnimatePresence>
            {showAddForm && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                transition={{ duration: 0.2 }}
                className="overflow-hidden mb-4"
              >
                <QuickAddHolding onAdd={() => { setShowAddForm(false); void refresh(); }} />
              </motion.div>
            )}
          </AnimatePresence>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5">
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
      </div>

      {/* ── Footer strip ─────────────────────────────────────────────── */}
      {(visibleEarnings.length > 0) && (
        <ErrorBoundary>
          <div className="px-4 sm:px-8">
            <div className="product-panel mb-2 px-4 py-3 sm:px-5">
              <div className="flex items-center gap-6 overflow-x-auto">
                <p className="shrink-0 font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                  Upcoming earnings
                </p>
                <div className="flex items-center gap-4">
                  {visibleEarnings.slice(0, 6).map((e) => (
                    <Link
                      key={e.holding_id}
                      href={`/dashboard/positions/${e.ticker}`}
                      className="group flex items-center gap-2 shrink-0"
                    >
                      <span className="font-mono text-[10px] font-medium text-primary/70 transition-colors group-hover:text-primary">
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
          </div>
        </ErrorBoundary>
      )}
    </div>
  );
}

export default function DashboardPage() {
  return (
    <Suspense>
      <DashboardInner />
    </Suspense>
  );
}
