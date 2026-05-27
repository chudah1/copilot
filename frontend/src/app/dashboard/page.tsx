"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
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
  const topAttentionLabel =
    topAttention?.assumption_label?.trim() ||
    (investorProfile === "hearsay_driven" ? "the original story" : "the core assumption");
  const topAttentionIsCadencePressure = Boolean(topAttention?.reason?.includes("review cadence"));
  const recentReviewLabel =
    recentReview?.assumption_label?.trim() ||
    (investorProfile === "hearsay_driven" ? "the original story" : "the core assumption");
  if (counts.review > 0) {
    return {
      tone: "border-amber-500/25 bg-amber-500/8",
      eyebrow: "Decisions pending",
      title:
        investorProfile === "hearsay_driven"
          ? `${counts.review} position${counts.review > 1 ? "s" : ""} need a fresh look before you trust the story.`
          : `${counts.review} position${counts.review > 1 ? "s" : ""} need thesis review before you treat them as conviction.`,
      body:
        topAttention
          ? topAttentionIsCadencePressure
            ? `${cleanTicker(topAttention.ticker)} is first in line — ${topAttentionLabel} is overdue for a re-read.${recentReview ? ` You just cleared ${recentReviewLabel} on ${cleanTicker(recentReview.ticker)}.` : ""}`
            : `${cleanTicker(topAttention.ticker)} is first in line — ${topAttentionLabel} is closest to needing a call.${recentReview ? ` You just cleared ${recentReviewLabel} on ${cleanTicker(recentReview.ticker)}.` : ""}`
          : counts.watch > 0
            ? `${counts.watch} more position${counts.watch > 1 ? "s are" : " is"} worth watching, but the review items come first.`
            : "Start with the review items first; the rest of the portfolio can wait.",
    };
  }

  if (counts.watch > 0) {
    return {
      tone: "border-sky-500/25 bg-sky-500/8",
      eyebrow: "Worth watching",
      title:
        investorProfile === "hearsay_driven"
          ? `${counts.watch} position${counts.watch > 1 ? "s are" : " is"} testing the original story, but nothing looks broken yet.`
          : `${counts.watch} position${counts.watch > 1 ? "s are" : " is"} testing a thesis pillar, but nothing looks broken yet.`,
      body: topAttention
        ? topAttentionIsCadencePressure
          ? `${cleanTicker(topAttention.ticker)} is the clearest watch item because ${topAttentionLabel} is overdue for review even though nothing looks broken yet.${recentReview ? ` You already cleared ${recentReviewLabel} in ${cleanTicker(recentReview.ticker)}.` : ""}`
          : `${cleanTicker(topAttention.ticker)} is the clearest watch item because ${topAttentionLabel} has the freshest pressure on it.${recentReview ? ` You already cleared ${recentReviewLabel} in ${cleanTicker(recentReview.ticker)}.` : ""}`
        : "Watch items show which assumptions are wobbling — still below the review queue.",
    };
  }

  if (counts.missing > 0) {
    return {
      tone: "border-border bg-card",
      eyebrow: "Monitoring gap",
      title:
        investorProfile === "hearsay_driven"
          ? `${counts.missing} position${counts.missing > 1 ? "s still need" : " still needs"} a real written reason.`
          : `${counts.missing} position${counts.missing > 1 ? "s still need" : " still needs"} a written thesis before monitoring means much.`,
      body: "Nothing urgent right now — but you won't know what news matters on these until you write what would change your mind.",
    };
  }

  return {
    tone: "border-emerald-500/25 bg-emerald-500/8",
    eyebrow: "Nothing needs a decision",
    title:
      investorProfile === "hearsay_driven"
        ? "Your written reasons are calm right now."
        : "Your written theses look calm right now.",
    body: nextEarnings
      ? `${cleanTicker(nextEarnings.ticker)} is the next likely decision point in ${nextEarnings.days_until === 0 ? "today" : nextEarnings.days_until === 1 ? "1 day" : `${nextEarnings.days_until} days`}.${recentReview ? ` You just resolved ${recentReviewLabel} in ${cleanTicker(recentReview.ticker)}.` : ""}`
      : recentReview
        ? `You just resolved ${recentReviewLabel} in ${cleanTicker(recentReview.ticker)}. Nothing else is asking for immediate thought right now.`
        : "Nothing needs a decision today. When you have a minute, re-read the reasons you wrote — stale words are how positions drift.",
  };
}

function dashboardStateCta(args: {
  investorProfile: "thesis_driven" | "hearsay_driven" | null;
  needsAttention: PortfolioPulse["pulses"];
  holdings: Holding[];
  missingHolding: Holding | null;
  nextUpcomingEarnings: UpcomingEarnings | null;
}) {
  const { investorProfile, needsAttention, holdings, missingHolding, nextUpcomingEarnings } = args;
  const pulseTargetLabel = (pulse: PortfolioPulse["pulses"][number]) =>
    pulse.assumption_label?.trim() ||
    (investorProfile === "hearsay_driven" ? "the story" : "the thesis");
  const topReview = needsAttention.find((pulse) => pulse.pulse_status === "review") ?? null;
  if (topReview) {
    return {
      href: `/dashboard/positions/${topReview.ticker}`,
      label:
        investorProfile === "hearsay_driven"
          ? `Open ${cleanTicker(topReview.ticker)} and review ${pulseTargetLabel(topReview)} →`
          : `Open ${cleanTicker(topReview.ticker)} and review ${pulseTargetLabel(topReview)} →`,
    };
  }

  const topWatch = needsAttention.find((pulse) => pulse.pulse_status === "watch") ?? null;
  if (topWatch) {
    return {
      href: `/dashboard/positions/${topWatch.ticker}`,
      label:
        investorProfile === "hearsay_driven"
          ? `Open ${cleanTicker(topWatch.ticker)} and see why ${pulseTargetLabel(topWatch)} is under pressure →`
          : `Open ${cleanTicker(topWatch.ticker)} and see why ${pulseTargetLabel(topWatch)} is under pressure →`,
    };
  }

  if (missingHolding) {
    return {
      href: `/dashboard/positions/${missingHolding.ticker}?source=dashboard_blind_spot`,
      label:
        investorProfile === "hearsay_driven"
          ? `Write the real reason for ${cleanTicker(missingHolding.ticker)} →`
          : `Write the thesis for ${cleanTicker(missingHolding.ticker)} →`,
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
          ? `We are now watching the reason behind ${joinedTickers}.`
          : `We are now watching the reasons behind ${joinedTickers}.`,
      body:
        "We'll only ping you when something hits the story you wrote. Quiet means nothing important landed yet.",
    };
  }

  if (investorProfile === "thesis_driven") {
    return {
      eyebrow: "Portfolio activated",
      title:
        count === 1
          ? `We are now watching the thesis behind ${joinedTickers}.`
          : `We are now watching the theses behind ${joinedTickers}.`,
      body:
        "We'll only ping you when an assumption gets tested. Quiet means your theses look intact for now.",
    };
  }

  return {
    eyebrow: "Portfolio activated",
    title:
      count === 1
        ? `We are now watching the reason behind ${joinedTickers}.`
        : `We are now watching the reasons behind ${joinedTickers}.`,
    body:
      "This dashboard is now tied to what you actually wrote down. Quiet means nothing important changed yet.",
  };
}

function recentReviewBannerCopy(
  review: RecentReviewBannerState,
  investorProfile: "thesis_driven" | "hearsay_driven" | null,
) {
  const target = review.assumption_label?.trim() || (investorProfile === "hearsay_driven" ? "the original story" : "the core assumption");
  const ticker = cleanTicker(review.ticker);

  if (review.action === "invalidated" || review.thesis_status === "invalidated") {
    return {
      eyebrow: "Reviewed just now",
      title:
        investorProfile === "hearsay_driven"
          ? `You marked ${target} as broken for ${ticker}.`
          : `You marked ${target} as broken for ${ticker}.`,
      body:
        investorProfile === "hearsay_driven"
          ? "That position now needs a rewritten reason or an exit decision before it counts as conviction again."
          : "That position now needs a rewritten thesis or an exit decision before it counts as conviction again.",
      href: `/dashboard/positions/${review.ticker}`,
      cta: investorProfile === "hearsay_driven" ? "Rewrite the reason →" : "Rewrite the thesis →",
    };
  }

  return {
    eyebrow: "Reviewed just now",
    title:
      investorProfile === "hearsay_driven"
        ? `You reviewed ${target} for ${ticker}.`
        : `You reviewed ${target} for ${ticker}.`,
    body: review.resolved_all
      ? (investorProfile === "hearsay_driven"
          ? "That assumption is back in a monitored quiet state. The next interruption should only happen if the story is tested again."
          : "That assumption is back in a monitored quiet state. The next interruption should only happen if the thesis is tested again.")
      : "There are still other items waiting, but the assumption you just reviewed is now on record.",
    href: `/dashboard/positions/${review.ticker}`,
    cta: "Open the position →",
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

  const missingThesisCount = summary?.theses_missing ?? 0;
  const nextUpcomingEarnings = useMemo(() => {
    if (!upcomingEarnings.length) return null;
    return [...upcomingEarnings].sort((a, b) => a.days_until - b.days_until)[0] ?? null;
  }, [upcomingEarnings]);
  const dashboardState = dashboardStateCopy(
    onboardingState?.investor_profile ?? null,
    { review: reviewCount, watch: needsAttention.filter((p) => p.pulse_status === "watch").length, missing: missingThesisCount },
    nextUpcomingEarnings,
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
    investorProfile: onboardingState?.investor_profile ?? null,
    needsAttention,
    holdings: holdings ?? [],
    missingHolding,
    nextUpcomingEarnings,
  });

  const sortedHoldings = useMemo(() => {
    if (!holdings) return [];
    return [...holdings].sort((a, b) => {
      const pulseA = pulseByHolding[a.id];
      const pulseB = pulseByHolding[b.id];
      const groupOrder = (holding: Holding, pulse?: PortfolioPulse["pulses"][number]) => {
        if (pulse?.has_thesis && pulse.pulse_status === "review") return 0;
        if (pulse?.has_thesis && pulse.pulse_status === "watch") return 1;
        if (!thesesByHolding[holding.id]) return 2;
        return 3;
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
      setActivationBannerDismissed(true);
    }
  }, [showActivationBanner]);

  const showRecentReviewBanner = Boolean(
    recentReviewBanner && isRecentIsoHours(recentReviewBanner.saved_at, 2),
  );
  const recentReviewCopy = recentReviewBanner
    ? recentReviewBannerCopy(recentReviewBanner, onboardingState?.investor_profile ?? null)
    : null;

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
                    {formatPercent(livePnlPct ?? summary?.total_pnl_pct ?? 0)}
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
            {needsAttention[0] && (
              <>
                <div className="hidden xl:flex flex-col text-right max-w-[220px]">
                  <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground/70">
                    Hottest assumption
                  </span>
                  <span className="font-sans text-xs text-foreground/80 truncate">
                    {cleanTicker(needsAttention[0].ticker)} · {needsAttention[0].assumption_label?.trim() || (onboardingState?.investor_profile === "hearsay_driven" ? "Original story" : "Core assumption")}
                  </span>
                </div>
                <div className="h-4 w-px bg-border hidden xl:block" />
              </>
            )}
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
        {showActivationBanner && (
          <div className="flex items-center justify-between gap-4 border border-emerald-500/20 bg-emerald-50 px-5 py-3">
            <div className="space-y-1">
              <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-emerald-700">
                {activationCopy.eyebrow}
              </p>
              <p className="font-sans text-sm text-foreground/85">
                {activationCopy.title}
              </p>
              <p className="font-sans text-xs text-foreground/65">
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
          <div className="flex items-center justify-between gap-4 border border-sky-500/20 bg-sky-50 px-5 py-3">
            <div className="space-y-1">
              <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-sky-700">
                {recentReviewCopy.eyebrow}
              </p>
              <p className="font-sans text-sm text-foreground/85">
                {recentReviewCopy.title}
              </p>
              <p className="font-sans text-xs text-foreground/65">
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

        <ErrorBoundary>
          <OnboardingBanner onVisibilityChange={setOnboardingBannerVisible} />
        </ErrorBoundary>

        {(() => {
          const showDraft = !onboardingBannerVisible && (draftStatus?.ready ?? 0) > 0 && !draftBannerDismissed;
          const showQuarterly = (quarterlyReview?.pending_count ?? 0) > 0;
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
            className="overflow-hidden px-8 pt-3"
          >
            <div className="border border-border bg-card p-5">
              <QuickAddHolding onAdd={() => { setShowAddForm(false); void refresh(); }} />
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Attention section ────────────────────────────────────────── */}
      <div className="px-8 pt-5">
        <motion.div
          initial={{ opacity: 0, y: -4 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.25 }}
          className={`border px-5 py-4 space-y-2 ${dashboardState.tone}`}
        >
          <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-foreground/60">
            {dashboardState.eyebrow}
          </p>
          <p className="font-display italic text-[1.4rem] leading-tight text-foreground">
            {dashboardState.title}
          </p>
          {needsAttention.length === 0 && (
            <p className="font-sans text-sm text-foreground/75 leading-relaxed">
              {dashboardState.body}
            </p>
          )}
          {dashboardStatePrimaryCta && (
            <Link
              href={dashboardStatePrimaryCta.href}
              className="inline-block font-mono text-[10px] uppercase tracking-[0.15em] text-primary hover:text-primary/75 transition-colors"
            >
              {dashboardStatePrimaryCta.label}
            </Link>
          )}
        </motion.div>
      </div>

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
