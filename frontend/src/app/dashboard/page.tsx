"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import {
  ArrowRight,
  BellRing,
  CalendarClock,
  CircleAlert,
  FilePenLine,
  ShieldCheck,
} from "lucide-react";
import useSWR from "swr";
import { api, fetcher } from "@/lib/api";
import { formatAssumptionLabel } from "@/lib/assumption-label";
import { getErrorMessage } from "@/lib/errors";
import { classifyThesisQuality } from "@/lib/thesis-quality";
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
      "We drafted working reasons for {count}. Review them so the dashboard watches what actually matters.",
    quarterly:
      "Quarterly review — {count} position{plural} waiting for a fresh decision",
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
  const topAttentionIsCadencePressure = Boolean(topAttention?.reason?.includes("review cadence"));
  if (counts.review > 0) {
    return {
      tone: "border-amber-500/25 bg-amber-500/8",
      eyebrow: "Review queue",
      title:
        investorProfile === "hearsay_driven"
          ? `${counts.review} position${counts.review > 1 ? "s need" : " needs"} a call.`
          : `${counts.review} position${counts.review > 1 ? "s need" : " needs"} a call.`,
      body:
        topAttention
          ? topAttentionIsCadencePressure
            ? `${cleanTicker(topAttention.ticker)} is first up. ${topAttentionLabel} is overdue.${recentReview ? ` ${cleanTicker(recentReview.ticker)} was just cleared.` : ""}`
            : `${cleanTicker(topAttention.ticker)} is first up. ${topAttentionLabel} is closest to a call.${recentReview ? ` ${cleanTicker(recentReview.ticker)} was just cleared.` : ""}`
          : counts.watch > 0
            ? `${counts.watch} more position${counts.watch > 1 ? "s are" : " is"} on watch behind it.`
            : "Start with the review items.",
    };
  }

  if (counts.watch > 0) {
    return {
      tone: "border-sky-500/25 bg-sky-500/8",
      eyebrow: "Under watch",
      title:
        investorProfile === "hearsay_driven"
          ? `${counts.watch} position${counts.watch > 1 ? "s need" : " needs"} a look.`
          : `${counts.watch} position${counts.watch > 1 ? "s need" : " needs"} a look.`,
      body: topAttention
        ? topAttentionIsCadencePressure
          ? `${cleanTicker(topAttention.ticker)} leads the list because ${topAttentionLabel} is overdue.${recentReview ? ` ${cleanTicker(recentReview.ticker)} was already cleared.` : ""}`
          : `${cleanTicker(topAttention.ticker)} leads the list because ${topAttentionLabel} has the freshest pressure.${recentReview ? ` ${cleanTicker(recentReview.ticker)} was already cleared.` : ""}`
        : "Nothing looks broken yet, but these names deserve a look.",
    };
  }

  if (counts.missing > 0) {
    return {
      tone: "border-border bg-card",
      eyebrow: "Missing thesis",
      title:
        investorProfile === "hearsay_driven"
          ? `${counts.missing} position${counts.missing > 1 ? "s still need" : " still needs"} a written reason.`
          : `${counts.missing} position${counts.missing > 1 ? "s still need" : " still needs"} a written thesis.`,
      body:
        investorProfile === "hearsay_driven"
          ? "The app can see price and news, but not what matters to your story yet."
          : "The app can see price and news, but not what matters to your thesis yet.",
    };
  }

  return {
    tone: "border-emerald-500/25 bg-emerald-500/8",
    eyebrow: "All clear",
    title: "Nothing needs a call right now.",
    body: nextEarnings
      ? `${cleanTicker(nextEarnings.ticker)} is the next likely decision point in ${nextEarnings.days_until === 0 ? "today" : nextEarnings.days_until === 1 ? "1 day" : `${nextEarnings.days_until} days`}.${recentReview ? ` ${cleanTicker(recentReview.ticker)} was just resolved.` : ""}`
      : recentReview
        ? `${cleanTicker(recentReview.ticker)} was just resolved. Nothing else needs attention right now.`
        : "No live pressure right now. The next useful pass is tightening stale or weak theses.",
  };
}

function dashboardStateCta(args: {
  needsAttention: PortfolioPulse["pulses"];
  holdings: Holding[];
  missingHolding: Holding | null;
  nextUpcomingEarnings: UpcomingEarnings | null;
}) {
  const { needsAttention, holdings, missingHolding, nextUpcomingEarnings } = args;
  const topReview = needsAttention.find((pulse) => pulse.pulse_status === "review") ?? null;
  if (topReview) {
    return {
      href: `/dashboard/positions/${topReview.ticker}`,
      label: `Review ${cleanTicker(topReview.ticker)} →`,
    };
  }

  const topWatch = needsAttention.find((pulse) => pulse.pulse_status === "watch") ?? null;
  if (topWatch) {
    return {
      href: `/dashboard/positions/${topWatch.ticker}`,
      label: `Open ${cleanTicker(topWatch.ticker)} →`,
    };
  }

  if (missingHolding) {
    return {
      href: `/dashboard/positions/${missingHolding.ticker}?source=dashboard_blind_spot`,
      label: `Write ${cleanTicker(missingHolding.ticker)} →`,
    };
  }

  if (nextUpcomingEarnings) {
    return {
      href: `/dashboard/positions/${nextUpcomingEarnings.ticker}`,
      label: `Open ${cleanTicker(nextUpcomingEarnings.ticker)} before earnings →`,
    };
  }

  const largestHolding = holdings
    .slice()
    .sort((a, b) => (b.current_value ?? 0) - (a.current_value ?? 0))[0] ?? null;
  if (largestHolding) {
    return {
      href: `/dashboard/positions/${largestHolding.ticker}`,
      label: `Open ${cleanTicker(largestHolding.ticker)} →`,
    };
  }

  return null;
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

export default function DashboardPage() {
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
    return pulse.pulses
      .filter(
        (p) => (p.pulse_status === "review" || p.pulse_status === "watch") && p.has_thesis,
      )
      .sort((a, b) => b.urgency_score - a.urgency_score);
  }, [pulse]);

  const reviewCount = useMemo(() => {
    return needsAttention.filter((p) => p.pulse_status === "review").length;
  }, [needsAttention]);

  const missingThesisCount = useMemo(
    () => (holdings ?? []).filter((h) => !thesesByHolding[h.id]).length,
    [holdings, thesesByHolding],
  );
  const nextUpcomingEarnings = useMemo(() => {
    if (!upcomingEarnings.length) return null;
    return [...upcomingEarnings].sort((a, b) => a.days_until - b.days_until)[0] ?? null;
  }, [upcomingEarnings]);
  // Only frame earnings as "the next decision point" when they're actually near
  // term — surfacing one 58 days out as the headline reads as noise.
  const EARNINGS_HORIZON_DAYS = 21;
  const nearTermEarnings =
    nextUpcomingEarnings && nextUpcomingEarnings.days_until <= EARNINGS_HORIZON_DAYS
      ? nextUpcomingEarnings
      : null;
  // Same horizon for the footer calendar — don't list earnings weeks out as
  // "upcoming"; they're not actionable yet.
  const visibleEarnings = upcomingEarnings.filter((e) => e.days_until <= EARNINGS_HORIZON_DAYS);
  const dashboardState = dashboardStateCopy(
    onboardingState?.investor_profile ?? null,
    { review: reviewCount, watch: needsAttention.filter((p) => p.pulse_status === "watch").length, missing: missingThesisCount },
    nearTermEarnings,
    needsAttention[0] ?? null,
    recentReviewBanner,
  );
  const missingHolding = useMemo(() => {
    if (!holdings) return null;
    return holdings
      .filter((holding) => !thesesByHolding[holding.id])
      .sort((a, b) => (b.current_value ?? 0) - (a.current_value ?? 0))[0] ?? null;
  }, [holdings, thesesByHolding]);
  const dashboardStatePrimaryCta = dashboardStateCta({
    needsAttention,
    holdings: holdings ?? [],
    missingHolding,
    nextUpcomingEarnings: nearTermEarnings,
  });
  const thesisQualityStats = useMemo(() => {
    const counts = { missing: 0, review: 0, weak: 0, stale: 0, workable: 0, sharp: 0 };
    for (const holding of holdings ?? []) {
      const quality = classifyThesisQuality(thesesByHolding[holding.id]);
      counts[quality.kind] += 1;
    }
    return counts;
  }, [holdings, thesesByHolding]);
  const weakestHolding = useMemo(() => {
    if (!holdings) return null;
    return [...holdings]
      .sort((a, b) => {
        const qualityDiff = classifyThesisQuality(thesesByHolding[a.id]).rank - classifyThesisQuality(thesesByHolding[b.id]).rank;
        if (qualityDiff !== 0) return qualityDiff;
        return (b.current_value ?? 0) - (a.current_value ?? 0);
      })[0] ?? null;
  }, [holdings, thesesByHolding]);
  const thesisQualityHeadline =
    thesisQualityStats.missing > 0
      ? `${thesisQualityStats.missing} ${thesisQualityStats.missing === 1 ? "position still runs" : "positions still run"} without a written thesis.`
      : thesisQualityStats.review > 0
        ? `${thesisQualityStats.review} ${thesisQualityStats.review === 1 ? "thesis needs" : "theses need"} a fresh decision.`
        : thesisQualityStats.weak > 0
        ? `${thesisQualityStats.weak} ${thesisQualityStats.weak === 1 ? "thesis is" : "theses are"} still too fuzzy.`
        : thesisQualityStats.stale > 0
          ? `${thesisQualityStats.stale} ${thesisQualityStats.stale === 1 ? "thesis is" : "theses are"} drifting stale.`
          : thesisQualityStats.workable > 0
            ? `${thesisQualityStats.workable} ${thesisQualityStats.workable === 1 ? "thesis is" : "theses are"} usable but not sharp yet.`
            : "Your written thinking looks sharp across the portfolio.";
  const thesisQualityDetail =
    thesisQualityStats.missing > 0
      ? "Monitoring has nothing explicit to defend there yet."
      : thesisQualityStats.review > 0
        ? "These positions were tested and still need a verdict."
      : thesisQualityStats.weak > 0
        ? "These theses are still too fuzzy to trust under pressure."
      : thesisQualityStats.stale > 0
        ? "Nothing broke yet, but stale reasoning lowers the next decision quality."
        : thesisQualityStats.workable > 0
          ? "Usable, but still not crisp enough to trust fully under pressure."
          : "Most positions now have explicit, current thinking behind them."
  const thesisQualityCta = weakestHolding
    ? `/dashboard/positions/${weakestHolding.ticker}`
    : null;

  const sortedHoldings = useMemo(() => {
    if (!holdings) return [];
    return [...holdings].sort((a, b) => {
      const pulseA = pulseByHolding[a.id];
      const pulseB = pulseByHolding[b.id];
      const groupOrder = (holding: Holding, pulse?: PortfolioPulse["pulses"][number]) => {
        if (pulse?.has_thesis && pulse.pulse_status === "review") return 0;
        if (pulse?.has_thesis && pulse.pulse_status === "watch") return 1;
        if (!thesesByHolding[holding.id]) return 2;
        const quality = classifyThesisQuality(thesesByHolding[holding.id]).kind;
        if (quality === "weak") return 3;
        if (quality === "stale" || quality === "review") return 4;
        if (quality === "workable") return 5;
        return 6;
      };
      const groupDiff = groupOrder(a, pulseA) - groupOrder(b, pulseB);
      if (groupDiff !== 0) return groupDiff;
      const urgencyDiff = (pulseB?.urgency_score ?? 0) - (pulseA?.urgency_score ?? 0);
      if (urgencyDiff !== 0) return urgencyDiff;
      return (b.current_value ?? 0) - (a.current_value ?? 0);
    });
  }, [holdings, pulseByHolding, thesesByHolding]);

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
  const holdingsCount = holdings?.length ?? 0;
  const monitoredCount = summary?.theses_active ?? 0;
  const monitoredCoverage =
    holdingsCount > 0 ? Math.round((monitoredCount / holdingsCount) * 100) : 0;
  const quietCount = useMemo(() => {
    if (!holdings) return 0;
    return holdings.filter((holding) => {
      const thesis = thesesByHolding[holding.id];
      if (!thesis) return false;
      const pulse = pulseByHolding[holding.id];
      if (pulse?.pulse_status === "review" || pulse?.pulse_status === "watch") return false;
      const quality = classifyThesisQuality(thesis);
      return quality.kind === "sharp" || quality.kind === "workable";
    }).length;
  }, [holdings, thesesByHolding, pulseByHolding]);
  const totalAlertCount = needsAttention.length;

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
        <div className="relative grid gap-4 xl:grid-cols-[minmax(0,1.45fr)_minmax(18rem,24rem)]">
          <section id="dashboard-overview" className="product-panel product-panel-muted overflow-hidden p-5 sm:p-6 scroll-mt-24">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="space-y-4">
                {hasLivePrices && (
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="flex items-center gap-2 border border-emerald-500/20 bg-emerald-500/8 px-2.5 py-1 font-mono text-[10px] uppercase tracking-[0.14em] text-emerald-700">
                      <span className="inline-block h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                      Live pricing active
                    </span>
                  </div>
                )}

                <div className="space-y-2">
                  <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                    Portfolio value
                  </p>
                  <div className="flex flex-wrap items-baseline gap-x-3 gap-y-2">
                    <span className="font-display text-[2.4rem] italic leading-none tracking-tight text-foreground sm:text-[3rem]">
                      {formatCurrency(displayTotalValue)}
                    </span>
                    {(livePnlPct != null ? livePnlPct : summary?.total_pnl_pct) != null && (
                      <span
                        className={`border px-2 py-1 font-mono text-[11px] tabular-nums ${
                          (livePnl ?? summary?.total_pnl ?? 0) >= 0
                            ? "border-emerald-500/20 bg-emerald-500/8 text-emerald-700"
                            : "border-red-500/20 bg-red-500/8 text-red-600"
                        }`}
                      >
                        {formatPercent(livePnlPct ?? summary?.total_pnl_pct ?? 0)}
                      </span>
                    )}
                  </div>
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <Link
                  href="/dashboard/simulate"
                  className="border border-border/80 px-3 py-2 font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground transition-colors hover:border-foreground/20 hover:text-foreground"
                >
                  Stress test
                </Link>
                <Link
                  href="/connect?return=dashboard"
                  className="border border-border/80 px-3 py-2 font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground transition-colors hover:border-foreground/20 hover:text-foreground"
                >
                  Import data
                </Link>
                <button
                  onClick={() => setShowAddForm((v) => !v)}
                  className={`border px-3 py-2 font-mono text-[10px] uppercase tracking-[0.16em] transition-colors ${
                    showAddForm
                      ? "border-border/80 text-muted-foreground"
                      : "border-primary/30 bg-primary/5 text-primary hover:border-primary/60"
                  }`}
                >
                  {showAddForm ? "Cancel add" : "New position"}
                </button>
              </div>
            </div>

            <div className="mt-6 grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(17rem,22rem)]">
              <div className="space-y-3">
                <div className={`border px-4 py-4 ${dashboardState.tone}`}>
                  <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-foreground/60">
                    {dashboardState.eyebrow}
                  </p>
                  <p className="mt-2 font-display text-[1.55rem] italic leading-tight text-foreground sm:text-[1.8rem]">
                    {dashboardState.title}
                  </p>
                  <p className="mt-2 max-w-2xl font-sans text-sm leading-relaxed text-foreground/85">
                    {dashboardState.body}
                  </p>
                  {dashboardStatePrimaryCta && (
                    <Link
                      href={dashboardStatePrimaryCta.href}
                      className="mt-4 inline-flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.16em] text-primary transition-colors hover:text-primary/75"
                    >
                      {dashboardStatePrimaryCta.label.replace(" →", "")}
                      <ArrowRight className="h-3.5 w-3.5" />
                    </Link>
                  )}
                </div>

                <div className="grid gap-3 sm:grid-cols-3">
                  <div className="border border-border/80 bg-background/75 p-4">
                    <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                      Written
                    </p>
                    <p className="mt-2 font-display text-[1.6rem] italic leading-none text-foreground">
                      {monitoredCoverage}%
                    </p>
                    <p className="mt-2 font-sans text-xs leading-relaxed text-muted-foreground">
                      {monitoredCount} of {holdingsCount} positions have a thesis on file.
                    </p>
                  </div>
                  <div className="border border-border/80 bg-background/75 p-4">
                    <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                      Review
                    </p>
                    <p className="mt-2 font-display text-[1.6rem] italic leading-none text-foreground">
                      {reviewCount > 0 ? reviewCount : totalAlertCount}
                    </p>
                    <p className="mt-2 font-sans text-xs leading-relaxed text-muted-foreground">
                      {reviewCount > 0
                        ? `${reviewCount} ${reviewCount === 1 ? "position needs" : "positions need"} a verdict.`
                        : totalAlertCount > 0
                          ? `${totalAlertCount} monitored positions are under watch.`
                          : "No active pressure right now."}
                    </p>
                  </div>
                  <div className="border border-border/80 bg-background/75 p-4">
                    <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                      Stable
                    </p>
                    <p className="mt-2 font-display text-[1.6rem] italic leading-none text-foreground">
                      {quietCount}
                    </p>
                    <p className="mt-2 font-sans text-xs leading-relaxed text-muted-foreground">
                      Positions with a usable thesis and no active pressure.
                    </p>
                  </div>
                </div>
              </div>

              <div className="grid gap-3">
                <div className="border border-border/80 bg-background/75 p-4">
                  <div className="flex items-start gap-3">
                    <CircleAlert className="mt-0.5 h-4 w-4 text-primary" />
                    <div className="space-y-1">
                      <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                        Weakest area
                      </p>
                      <p className="font-sans text-sm leading-relaxed text-foreground/85">
                        {thesisQualityHeadline}
                      </p>
                      <p className="font-sans text-xs leading-relaxed text-muted-foreground">
                        {thesisQualityDetail}
                      </p>
                      {thesisQualityCta && (
                        <Link
                          href={thesisQualityCta}
                          className="inline-flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.15em] text-primary transition-colors hover:text-primary/75"
                        >
                          Open weakest position
                          <ArrowRight className="h-3.5 w-3.5" />
                        </Link>
                      )}
                    </div>
                  </div>
                </div>

                <div className="border border-border/80 bg-background/75 p-4">
                  <div className="flex items-start gap-3">
                    <BellRing className="mt-0.5 h-4 w-4 text-primary" />
                    <div className="space-y-2">
                      <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                        Digest
                      </p>
                      {pulse?.next_digest_at ? (
                        <DigestCountdown nextDigestAt={pulse.next_digest_at} />
                      ) : (
                        <p className="font-sans text-sm leading-relaxed text-foreground/80">
                          Digest timing appears once monitoring is active.
                        </p>
                      )}
                    </div>
                  </div>
                </div>

                <div className="border border-border/80 bg-background/75 p-4">
                  <div className="flex items-start gap-3">
                    {missingThesisCount > 0 ? (
                      <FilePenLine className="mt-0.5 h-4 w-4 text-primary" />
                    ) : nearTermEarnings ? (
                      <CalendarClock className="mt-0.5 h-4 w-4 text-primary" />
                    ) : (
                      <ShieldCheck className="mt-0.5 h-4 w-4 text-primary" />
                    )}
                    <div className="space-y-1">
                      <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                        Next up
                      </p>
                      <p className="font-sans text-sm leading-relaxed text-foreground/85">
                        {missingThesisCount > 0
                          ? `${missingThesisCount} ${missingThesisCount === 1 ? "position still needs" : "positions still need"} a written thesis.`
                          : nearTermEarnings
                            ? `${cleanTicker(nearTermEarnings.ticker)} reports ${daysUntilLabel(nearTermEarnings.days_until)}.`
                            : "The near-term calendar is quiet."}
                      </p>
                    </div>
                  </div>
                </div>

                <div className="border border-border/80 bg-background/75 p-4">
                  <div className="space-y-2">
                      <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                        Quality mix
                      </p>
                    <div className="grid gap-2 sm:grid-cols-2">
                      <div className="flex items-center justify-between border border-border/60 bg-background/70 px-3 py-2">
                        <span className="font-sans text-xs text-foreground/80">Sharp</span>
                        <span className="font-mono text-[10px] text-emerald-700">{thesisQualityStats.sharp}</span>
                      </div>
                      <div className="flex items-center justify-between border border-border/60 bg-background/70 px-3 py-2">
                        <span className="font-sans text-xs text-foreground/80">Stale</span>
                        <span className="font-mono text-[10px] text-amber-700">{thesisQualityStats.stale}</span>
                      </div>
                      <div className="flex items-center justify-between border border-border/60 bg-background/70 px-3 py-2">
                        <span className="font-sans text-xs text-foreground/80">Weak</span>
                        <span className="font-mono text-[10px] text-amber-700">{thesisQualityStats.weak}</span>
                      </div>
                      <div className="flex items-center justify-between border border-border/60 bg-background/70 px-3 py-2">
                        <span className="font-sans text-xs text-foreground/80">Workable</span>
                        <span className="font-mono text-[10px] text-foreground/70">{thesisQualityStats.workable}</span>
                      </div>
                      <div className="flex items-center justify-between border border-border/60 bg-background/70 px-3 py-2">
                        <span className="font-sans text-xs text-foreground/80">Missing</span>
                        <span className="font-mono text-[10px] text-red-600">{thesisQualityStats.missing}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
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

      {/* ── Quick add form ───────────────────────────────────────────── */}
      <AnimatePresence>
        {showAddForm && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden px-4 sm:px-8 pt-3"
          >
            <div className="product-panel p-5">
              <QuickAddHolding onAdd={() => { setShowAddForm(false); void refresh(); }} />
            </div>
          </motion.div>
        )}
      </AnimatePresence>

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
                    Live pressure
                  </p>
                  <p className="mt-1 font-sans text-sm text-foreground/80">
                    Fresh evidence touching a written thesis.
                  </p>
                </div>
                <span className="border border-primary/20 bg-primary/6 px-2 py-1 font-mono text-[10px] uppercase tracking-[0.14em] text-primary/75">
                  {needsAttention.length} live
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
              <p className="mt-1 font-sans text-sm text-foreground/80">
                Sorted by urgency, then value.
              </p>
            </div>
            <p className="hidden font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground/40 sm:block">
              Urgency first
            </p>
          </div>

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
