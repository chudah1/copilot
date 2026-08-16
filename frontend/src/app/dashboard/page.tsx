"use client";

import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import {
  ArrowRight,
  BellRing,
  CalendarClock,
} from "lucide-react";
import useSWR from "swr";
import { api, fetcher } from "@/lib/api";
import { formatAssumptionLabel } from "@/lib/assumption-label";
import { getErrorMessage } from "@/lib/errors";
import { buildDecisionInbox } from "@/lib/decision-inbox";
import { formatPercent } from "@/lib/utils";
import { OnboardingBanner } from "@/components/onboarding/onboarding-banner";
import { BehavioralMemoryStrip } from "@/components/dashboard/behavioral-memory-strip";
import { QuickAddHolding } from "@/components/portfolio/quick-add-holding";
import { SinceLastVisit } from "@/components/portfolio/since-last-visit";
import { DigestCountdown } from "@/components/portfolio/digest-countdown";
import { PositionCard, cleanTicker } from "@/components/portfolio/position-card";
import { PositionPeek } from "@/components/portfolio/position-peek";
import { AnimatedCurrency } from "@/components/ui/animated-currency";
import { AttentionCard } from "@/components/portfolio/attention-card";
import { DashboardSkeleton } from "@/components/portfolio/dashboard-skeleton";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { InfoTip } from "@/components/ui/info-tip";
import { BlindSpotsSection } from "@/components/dashboard/blind-spots-section";
import { DashboardActionCenter } from "@/components/dashboard/dashboard-action-center";
import { deriveDashboardCoach } from "@/lib/dashboard-coach";
import { buildDashboardActionQueue } from "@/lib/dashboard-action-queue";
import { toast } from "sonner";
import type {
  DashboardCommandCenter,
  DashboardCoachMemory,
  DashboardOpenLoop,
  DashboardWorkspace,
  Digest,
  Holding,
  LivePrice,
  OnboardingState,
  PortfolioSummary,
  PortfolioTrend,
  Thesis,
  PortfolioPulse,
  QuarterlyReviewCurrent,
  UpcomingEarnings,
  UserPreferences,
} from "@/types";

function greetingForHour(hour: number) {
  if (hour < 5) return "Working late";
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

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
        "Drafts are ready for {count}. Review them before monitoring goes live.",
      quarterly:
        "Quarterly review ready for {count} position{plural}.",
    };
  }

  if (investorProfile === "hearsay_driven") {
    return {
      emptyBody:
        "The market will test the reason. Add your positions below and write down why you own them so you can tell signal from noise when things move fast.",
      draftBanner:
        "Drafts are ready for {count}. Review them before monitoring goes live.",
      quarterly:
        "Quarterly review ready for {count} position{plural}.",
    };
  }

  return {
    emptyBody:
      "The market will test you. Add your positions below and write down exactly why you own them so you can make steadier calls when things move fast.",
    draftBanner:
      "Drafts are ready for {count}. Review them before monitoring goes live.",
    quarterly:
      "Quarterly review ready for {count} position{plural}.",
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
        "We'll stay quiet unless the reason gets tested.",
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
      title: `${target} was marked as no longer holding for ${ticker}.`,
      body:
        investorProfile === "hearsay_driven"
          ? "That position now needs a clearer reason or an exit decision."
          : "That position now needs a clearer thesis or an exit decision.",
      href: `/dashboard/positions/${review.ticker}`,
      cta: investorProfile === "hearsay_driven" ? "Rewrite →" : "Rewrite →",
    };
  }

  return {
    eyebrow: "Reviewed just now",
    title: `${target} was reviewed for ${ticker}.`,
    body: review.resolved_all
      ? (investorProfile === "hearsay_driven"
          ? "That reason is back to quiet unless it gets tested again."
          : "That thesis is back to quiet unless it gets tested again.")
      : "That review is saved. Other items are still in play.",
    href: `/dashboard/positions/${review.ticker}`,
    cta: "See position →",
  };
}

// ── Dashboard ──────────────────────────────────────────────────────────────

function DashboardInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [showAddForm, setShowAddForm] = useState(false);
  const [peekHoldingId, setPeekHoldingId] = useState<string | null>(null);
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
  const { data: workspace = null, error: workspaceError, mutate: mutateWorkspace } = useSWR<DashboardWorkspace>("/api/dashboard/workspace", fetcher);
  const { data: commandCenter = null, mutate: mutateCommandCenter } = useSWR<DashboardCommandCenter>("/api/dashboard/command-center", fetcher);
  const { data: coachMemory = null, mutate: mutateCoachMemory } = useSWR<DashboardCoachMemory>("/api/dashboard/coach-memory", fetcher);
  const { data: pulse, error: pulseError, mutate: mutatePulse } = useSWR<PortfolioPulse>("/api/portfolio/pulse", fetcher);
  const { data: upcomingEarnings = [] } = useSWR<UpcomingEarnings[]>("/api/portfolio/upcoming-earnings", fetcher, { fallbackData: [] });
  const { data: quarterlyReview = null } = useSWR<QuarterlyReviewCurrent>("/api/quarterly-review/current", fetcher);
  const { data: openLoops = [] } = useSWR<DashboardOpenLoop[]>("/api/dashboard/open-loops", fetcher);
  const { data: digests = [], mutate: mutateDigests } = useSWR<Digest[]>("/api/digests", fetcher);
  const { data: onboardingState = null } = useSWR<OnboardingState>("/api/onboarding/state", fetcher);
  const { data: userPrefs = null } = useSWR<UserPreferences>("/api/settings", fetcher);
  const investorProfile = workspace?.investor_profile ?? onboardingState?.investor_profile ?? null;
  const copy = dashboardCopy(investorProfile);
  const displayName = userPrefs?.display_name?.trim() || null;
  const greeting = greetingForHour(new Date().getHours());
  const presentedCoachAdviceRef = useRef<string | null>(null);
  const [dismissedCoachAdviceKey, setDismissedCoachAdviceKey] = useState<string | null>(null);

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
      mutateWorkspace(),
      mutateCommandCenter(),
      mutatePulse(),
      mutateCoachMemory(),
      mutateDigests(),
    ]);
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
  const needsAttention = decisionInbox.attentionEntries
    .map((entry) => entry.pulse)
    .filter((pulse): pulse is PortfolioPulse["pulses"][number] => Boolean(pulse));
  const reviewCount = decisionInbox.counts.needsDecision;
  const missingThesisCount = decisionInbox.counts.needsWrittenCase;
  const nearTermEarnings = decisionInbox.nearTermEarnings;
  const visibleEarnings = decisionInbox.visibleEarnings;
  const caseQualityStats = decisionInbox.caseQualityCounts;
  const weakestHolding = decisionInbox.weakestCaseEntry?.holding ?? null;
  const weakestQuality = decisionInbox.weakestCaseEntry?.caseQuality ?? null;
  const coachPlan = useMemo(
    () => (workspace ? deriveDashboardCoach({ workspace, openLoops, coachMemory }) : null),
    [workspace, openLoops, coachMemory],
  );
  const visibleCoachPlan = coachPlan && coachPlan.adviceKey !== dismissedCoachAdviceKey ? coachPlan : null;
  const liveCaseCount = workspace?.summary_metrics.monitored_count ?? summary?.theses_active ?? 0;
  const blindSpotCount = workspace?.blind_spots.length
    ?? (caseQualityStats.missing + caseQualityStats.weak + caseQualityStats.review_overdue);
  const snapshotStats = [
    { label: "Monitored", value: String(liveCaseCount) },
    { label: "Reviews waiting", value: String(openLoops.length) },
    { label: "Needs attention", value: String(blindSpotCount) },
  ];

  const latestDigest = digests[0] ?? null;
  const weeklyDigestReady = Boolean(
    latestDigest &&
    ["ready", "sent"].includes(latestDigest.status) &&
    !latestDigest.reviewed_at,
  );
  const dashboardActions = buildDashboardActionQueue({
    commandCenter,
    latestDigest,
    weeklyDigestReady,
    quarterlyReview,
    investorProfile,
    coachPlan: visibleCoachPlan,
  });

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

  useEffect(() => {
    if (!visibleCoachPlan || presentedCoachAdviceRef.current === visibleCoachPlan.adviceKey) {
      return;
    }

    presentedCoachAdviceRef.current = visibleCoachPlan.adviceKey;
    void api.post("/api/dashboard/coach-feedback", {
      advice_key: visibleCoachPlan.adviceKey,
      mode: visibleCoachPlan.feedback.mode,
      event: "presented",
      holding_id: visibleCoachPlan.feedback.holdingId,
      thesis_id: visibleCoachPlan.feedback.thesisId,
      loop_key: visibleCoachPlan.feedback.loopKey,
      pattern_kind: visibleCoachPlan.feedback.patternKind,
    }).then(() => mutateCoachMemory());
  }, [visibleCoachPlan, mutateCoachMemory]);

  const recordCoachAction = async (
    event: "acted" | "skipped",
    actionLabel?: string,
  ) => {
    if (!visibleCoachPlan) return;
    await api.post("/api/dashboard/coach-feedback", {
      advice_key: visibleCoachPlan.adviceKey,
      mode: visibleCoachPlan.feedback.mode,
      event,
      holding_id: visibleCoachPlan.feedback.holdingId,
      thesis_id: visibleCoachPlan.feedback.thesisId,
      loop_key: visibleCoachPlan.feedback.loopKey,
      pattern_kind: visibleCoachPlan.feedback.patternKind,
      action_label: actionLabel ?? null,
    });
    await mutateCoachMemory();
  };

  const handleCoachAct = async (
    target: NonNullable<typeof visibleCoachPlan>["primaryCta"] | NonNullable<NonNullable<typeof visibleCoachPlan>["secondaryCta"]>,
  ) => {
    try {
      await recordCoachAction("acted", target.label);
    } catch (err) {
      toast.error(getErrorMessage(err, "Couldn't save coach response"));
    } finally {
      router.push(target.href);
    }
  };

  const handleCoachSkip = async () => {
    if (!visibleCoachPlan) return;
    try {
      await recordCoachAction("skipped");
      setDismissedCoachAdviceKey(visibleCoachPlan.adviceKey);
      toast.success("Coach suggestion hidden for now.");
    } catch (err) {
      toast.error(getErrorMessage(err, "Couldn't hide coach suggestion"));
    }
  };

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
  const loadError = holdingsError || summaryError || thesesError || pulseError || workspaceError;

  if (loadError && (!holdings || holdings.length === 0)) {
    return (
      <div className="flex min-h-[calc(100vh-84px)] items-center justify-center px-6 py-10">
        <div className="product-panel w-full max-w-xl border border-border/70 bg-background/82 p-8 text-center">
          <div className="space-y-3">
            <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
              Dashboard unavailable
            </p>
            <h1 className="font-display text-[2rem] italic leading-tight text-foreground">
              The portfolio did not load cleanly.
            </h1>
            <p className="mx-auto max-w-md font-sans text-sm leading-relaxed text-foreground/78">
              {getErrorMessage(loadError, "Failed to load portfolio")}
            </p>
          </div>
          <div className="mt-6 flex justify-center">
            <button
              onClick={() => void refresh()}
              className="border border-primary/30 bg-background/72 px-4 py-2 font-mono text-[10px] uppercase tracking-[0.2em] text-primary transition-colors hover:border-primary/55"
            >
              Retry load
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Empty state
  if (!holdings || holdings.length === 0) {
    return (
      <div className="flex min-h-[calc(100vh-84px)] items-center justify-center px-6 py-10">
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="product-panel w-full max-w-2xl border border-border/70 bg-[linear-gradient(180deg,rgba(163,126,79,0.06),rgba(255,255,255,0.96))] p-8 text-center"
        >
          <div className="mx-auto max-w-xl space-y-4">
            <div className="space-y-2">
              <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                Start the portfolio
              </p>
              <p className="font-display italic text-3xl leading-tight text-foreground">
                Give the portfolio its first position.
              </p>
            </div>
            <p className="font-sans text-sm leading-relaxed text-foreground/78">
              {copy.emptyBody}
            </p>
          </div>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.4, delay: 0.2 }}
            className="mt-7 flex flex-col items-center gap-4"
          >
            {/* Single CTA — /connect already presents Manual, CSV, and
                Trading 212 as tabs (Manual is the default), so a "Connect
                broker" label plus a broken "Add manually" split button was
                both incorrect and confusing. */}
            <Link href="/connect">
              <button className="bg-primary px-5 py-2.5 font-mono text-[11px] uppercase tracking-[0.15em] text-primary-foreground transition-colors hover:bg-primary/90">
                Add position
              </button>
            </Link>
            <p className="font-sans text-xs leading-relaxed text-muted-foreground">
              Manual entry, CSV import, and broker sync all start from the same flow.
            </p>
          </motion.div>
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
        className="relative order-2 border-b border-border/80 px-4 py-5 sm:px-8 sm:py-7"
      >
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(121,83,48,0.18),transparent_30%),linear-gradient(180deg,rgba(255,255,255,0.35),transparent_80%)]"
        />
        <div className="relative">
          <section
            id="dashboard-overview"
            className="product-panel overflow-hidden border border-border/70 bg-[linear-gradient(180deg,rgba(163,126,79,0.05),rgba(255,255,255,0.96))] p-5 sm:p-6 scroll-mt-24"
          >
            <div className="space-y-5">
              <div className="space-y-4">
                <div>
                  <div className="flex items-center gap-1.5">
                    <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-muted-foreground">
                      Portfolio command center
                    </p>
                    <InfoTip label="Command center" align="center">
                      One prioritized queue for your weekly review, decisions, and follow-through.
                    </InfoTip>
                  </div>
                  <h1 className="mt-2 font-display text-[2rem] italic leading-tight text-foreground sm:text-[2.5rem]">
                    {displayName ? `${greeting}, ${displayName}.` : `${greeting}.`}
                    <span className="block text-foreground/60 text-[0.72em] mt-1">
                      Here&apos;s where the portfolio needs you.
                    </span>
                  </h1>
                </div>

                <p className="max-w-2xl font-sans text-sm leading-relaxed text-foreground/72">
                  Start with the highest-priority action, then move through the rest when you are ready.
                </p>
              </div>

            </div>
          </section>
        </div>
      </motion.div>

      {dashboardActions.length > 0 && (
        <div className="order-4 px-4 pt-4 sm:px-8">
          <DashboardActionCenter
            actions={dashboardActions}
            onCoachAct={handleCoachAct}
            onCoachSkip={handleCoachSkip}
          />
        </div>
      )}

      {summary && (
        <div className="order-4 px-4 pt-3 sm:px-8">
          <SinceLastVisit summary={summary} trend={trend} />
        </div>
      )}

      {/* ── Banners ─────────────────────────────────────────────────── */}
      <div className="order-5 px-4 pt-3 sm:px-8 space-y-2 empty:hidden">
        {/* Only one contextual banner at a time — recent review takes priority over activation */}
        {showActivationBanner && !showRecentReviewBanner && (
          <div className="product-panel flex items-start justify-between gap-4 border border-emerald-500/20 bg-[linear-gradient(180deg,rgba(16,185,129,0.08),rgba(255,255,255,0.94))] px-5 py-4">
            <div className="space-y-1.5">
              <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-emerald-700">
                {activationCopy.eyebrow}
              </p>
              <p className="font-sans text-sm leading-relaxed text-foreground/85">
                {activationCopy.title}
              </p>
              <p className="font-sans text-xs leading-relaxed text-foreground/78">
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
          <div className="product-panel flex items-start justify-between gap-4 border border-sky-500/25 bg-[linear-gradient(180deg,rgba(14,165,233,0.08),rgba(255,255,255,0.94))] px-5 py-4">
            <div className="space-y-1.5">
              <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-sky-700">
                {recentReviewCopy.eyebrow}
              </p>
              <p className="font-sans text-sm leading-relaxed text-foreground/85">
                {recentReviewCopy.title}
              </p>
              <p className="font-sans text-xs leading-relaxed text-foreground/78">
                {recentReviewCopy.body}
              </p>
              <Link
                href={recentReviewCopy.href}
                className="inline-flex items-center border border-primary/25 bg-background/72 px-3 py-2 font-mono text-[10px] uppercase tracking-[0.15em] text-primary transition-colors hover:border-primary/45"
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
            <OnboardingBanner />
          </ErrorBoundary>
        )}

      </div>

      {workspace && (
        <div className="order-6 px-4 pt-4 sm:px-8">
          <BehavioralMemoryStrip
            workspace={workspace}
            coachMemory={coachMemory}
          />
        </div>
      )}


      <AnimatePresence>
        {!workspace && needsAttention.length > 0 && (
          <motion.div
            id="live-pressure"
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, delay: 0.1 }}
            className="order-4 px-4 sm:px-8 pt-5 scroll-mt-24"
          >
            <div className="product-panel p-4 sm:p-5">
              <div className="mb-4 flex items-center justify-between gap-3">
                <div>
                  <div className="flex items-center gap-1.5">
                    <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                      What changed
                    </p>
                    <InfoTip label="What changed" align="center">
                      Evidence appears here only when it touches something you wrote down. Open a position to see the assumption and the model read.
                    </InfoTip>
                  </div>
                  <p className="mt-1 font-sans text-sm text-foreground/80">
                    Evidence tied to something you already wrote down.
                  </p>
                </div>
                <span className="border border-primary/20 bg-primary/6 px-2 py-1 font-mono text-[10px] uppercase tracking-[0.14em] text-primary/75">
                  {needsAttention.length} need your read
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
      <div id="positions" className="order-1 px-4 sm:px-8 pt-6 pb-8 flex-1 scroll-mt-24">
        <div className="grid items-start gap-5 lg:grid-cols-[minmax(0,1fr)_20rem]">
        {/* Scrolls internally on large screens so the whole portfolio stays one
            view with the snapshot always visible beside it. */}
        <div className="product-panel p-4 sm:p-5 lg:max-h-[calc(100vh-8rem)] lg:overflow-y-auto">
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
                className={`px-3 py-2 font-mono text-[10px] uppercase tracking-[0.16em] transition-colors ${
                  showAddForm
                    ? "border border-border/80 bg-background/70 text-muted-foreground hover:text-foreground"
                    : "border border-primary/30 bg-primary/5 text-primary hover:border-primary/60"
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

          <div className={`grid grid-cols-1 gap-3 ${
            sortedHoldings.length === 1 ? "" : "sm:grid-cols-2 xl:grid-cols-3"
          }`}>
            {sortedHoldings.map((h, i) => (
              <PositionCard
                key={h.id}
                holding={h}
                thesis={thesesByHolding[h.id]}
                pulse={pulseByHolding[h.id]}
                earnings={earningsByHolding[h.id]}
                livePrice={livePrices[h.ticker]}
                totalValue={displayTotalValue}
                onPeek={() => setPeekHoldingId(h.id)}
                investorProfile={onboardingState?.investor_profile ?? null}
                index={i}
                featured={sortedHoldings.length === 1}
              />
            ))}
          </div>
        </div>

        <aside className="self-start space-y-5 lg:sticky lg:top-[96px]">
          <div className="product-panel p-4 sm:p-5">
            <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
              At a glance
            </p>
            <div className="mt-3 flex flex-wrap items-baseline gap-2">
              <AnimatedCurrency
                value={displayTotalValue}
                currency={summary?.portfolio_currency ?? "GBP"}
                className="font-display text-[1.9rem] italic leading-none tracking-tight text-foreground tabular-nums"
              />
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
              {hasLivePrices ? " · prices refreshed recently" : ""}
            </p>
            <div className="mt-4 grid grid-cols-3 gap-2">
              {snapshotStats.map((stat) => (
                <div key={stat.label} className="border border-border/60 bg-background/55 px-3 py-2">
                  <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
                    {stat.label}
                  </p>
                  <p className="mt-1 font-sans text-lg leading-none text-foreground">
                    {stat.value}
                  </p>
                </div>
              ))}
            </div>
            {summary?.fx_unavailable && (
              <div className="mt-3 border border-amber-500/20 bg-amber-500/6 px-3 py-2.5">
                <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-amber-800">
                  FX unavailable
                </p>
                <p className="mt-1 font-sans text-xs leading-relaxed text-foreground/78">
                  {summary.preferred_currency} conversion is temporarily unavailable. Values are shown in GBP.
                </p>
              </div>
            )}

            <div className="mt-5 space-y-3 border-t border-border/60 pt-4">
              <div className="flex items-start gap-3">
                <CalendarClock className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                <p className="font-sans text-sm leading-relaxed text-foreground/85">
                  {nearTermEarnings
                    ? `${cleanTicker(nearTermEarnings.ticker)} reports ${daysUntilLabel(nearTermEarnings.days_until)}.`
                    : "No earnings reports in the next three weeks."}
                </p>
              </div>

              {pulse?.next_digest_at && (
                <div className="flex items-start gap-3 border-t border-border/60 pt-3">
                  <BellRing className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                  <div className="space-y-1">
                    <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
                      Next digest
                    </p>
                    <DigestCountdown nextDigestAt={pulse.next_digest_at} />
                  </div>
                </div>
              )}
            </div>

            <div className="mt-5 space-y-3 border-t border-border/60 pt-4">
              <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                Next steps
              </p>
              <div className="grid gap-2">
                <Link href="/dashboard/simulate" className="flex items-center justify-between border border-border/80 bg-background/72 px-3 py-3 transition-colors hover:border-foreground/20">
                  <div>
                    <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-primary/80">
                      Preview an add
                    </p>
                    <p className="mt-1 font-sans text-xs leading-relaxed text-foreground/72">
                      Check sizing, concentration, and fit before you commit capital.
                    </p>
                  </div>
                  <ArrowRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                </Link>
                <Link href="/connect?return=dashboard" className="flex items-center justify-between border border-border/80 bg-background/72 px-3 py-3 transition-colors hover:border-foreground/20">
                  <div>
                    <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-primary/80">
                      Import another account
                    </p>
                    <p className="mt-1 font-sans text-xs leading-relaxed text-foreground/72">
                      Import another broker or refresh coverage.
                    </p>
                  </div>
                  <ArrowRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                </Link>
              </div>
            </div>
          </div>

          {workspace && (
            <BlindSpotsSection blindSpots={workspace.blind_spots} investorProfile={investorProfile} />
          )}
          {!workspace && weakestHolding && weakestQuality && (
            <div className="product-panel p-4 sm:p-5">
              <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                Needs attention
              </p>
              <p className="mt-2 font-sans text-sm leading-relaxed text-foreground/85">
                {caseQualityStats.missing > 0
                  ? investorProfile === "hearsay_driven"
                    ? `${cleanTicker(weakestHolding.ticker)} has no reason yet.`
                    : `${cleanTicker(weakestHolding.ticker)} has no thesis yet.`
                  : caseQualityStats.weak > 0
                    ? investorProfile === "hearsay_driven"
                      ? `${cleanTicker(weakestHolding.ticker)} needs a clearer reason.`
                      : investorProfile === "thesis_driven"
                        ? `${cleanTicker(weakestHolding.ticker)} needs a clearer thesis.`
                        : `${cleanTicker(weakestHolding.ticker)} needs a clearer reason.`
                    : caseQualityStats.review_overdue > 0
                      ? `${cleanTicker(weakestHolding.ticker)} is due for review.`
                      : `${cleanTicker(weakestHolding.ticker)} can be made more specific.`}
              </p>
            </div>
          )}
        </aside>
        </div>
      </div>

      {/* ── Position peek (slide-over) ───────────────────────────────── */}
      {(() => {
        const peeked = peekHoldingId ? holdings.find((h) => h.id === peekHoldingId) ?? null : null;
        return (
          <PositionPeek
            holding={peeked}
            thesis={peeked ? thesesByHolding[peeked.id] : undefined}
            pulse={peeked ? pulseByHolding[peeked.id] : undefined}
            earnings={peeked ? earningsByHolding[peeked.id] : undefined}
            livePrice={peeked ? livePrices[peeked.ticker] : undefined}
            totalValue={displayTotalValue}
            investorProfile={onboardingState?.investor_profile ?? null}
            onClose={() => setPeekHoldingId(null)}
          />
        );
      })()}

      {/* ── Footer strip ─────────────────────────────────────────────── */}
      {(visibleEarnings.length > 0) && (
        <ErrorBoundary>
          <div className="order-5 px-4 sm:px-8">
            <div className="product-panel mb-2 px-4 py-3 sm:px-5">
              <div className="flex flex-wrap items-center gap-3 overflow-x-auto">
                <p className="shrink-0 font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                  Upcoming earnings
                </p>
                <div className="flex items-center gap-2">
                  {visibleEarnings.slice(0, 6).map((e) => (
                    <Link
                      key={e.holding_id}
                      href={`/dashboard/positions/${e.ticker}`}
                      className="group flex items-center gap-2 shrink-0 border border-border/70 bg-background/72 px-2.5 py-1.5 transition-colors hover:border-foreground/20"
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
