"use client";

import { Suspense, startTransition, useEffect, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { api } from "@/lib/api";
import { getErrorMessage } from "@/lib/errors";
import { ageInDays, getCaseReviewPressure } from "@/lib/decision-state";
import {
  loadPositionWorkspace,
  selectActiveThesis,
  selectLatestInvalidatedThesis,
} from "@/lib/position-workspace";
import { formatCurrency, formatDate } from "@/lib/utils";
import { toast } from "sonner";
import { ThesisCard } from "@/components/thesis/thesis-card";
import { ThesisDiffView } from "@/components/thesis/thesis-diff-view";
import { ConvictionLog } from "@/components/thesis/conviction-log";
import { ThesisDecompositionReview } from "@/components/thesis/thesis-decomposition-review";
import { HistoricalAuditCard } from "@/components/thesis/historical-audit-card";
import { ThesisEditor } from "@/components/thesis/thesis-editor";
import { InvalidateDialog } from "./invalidate-dialog";
import { MonitoringTab } from "./monitoring-tab";
import { PositionDecisions } from "./position-decisions";
import { PositionHeader } from "./position-header";
import { ThesisHealthCheck } from "@/components/thesis/thesis-health-check";
import { CounterThesisCard } from "@/components/thesis/counter-thesis-card";
import { EarningsReviewModal } from "@/components/thesis/earnings-review-modal";
import type {
  CheckNowResponse,
  ConfirmDecompositionRequest,
  ConvictionLogResponse,
  HealthCheckResult,
  HistoricalAuditResponse,
  Holding,
  HoldingPulse,
  MonitoringEvent,
  MonitoringGap,
  OnboardingState,
  PortfolioPulse,
  ReviewedItem,
  SubmitClaimReviewsResponse,
  SupportingItem,
  Thesis,
  ThesisAssistResponse,
  ThesisDecompositionEnvelope,
  ThesisHealthSnapshot,
  UpcomingEarnings,
} from "@/types";


import type {
  TabId,
  ThesisSubTab,
  NextStepNotice,
} from "./position-helpers";
import {
  cleanTicker,
  getThesisInsights,
  positionCopy,
  getDecisionPrompt,
  getThesisHandoffPrompt,
  getBlindSpotArrivalCopy,
  getMonitoringCalmState,
  describeWatchHint,
  getMonitoringPreviewItems,
  buildPostSaveNotice,
  buildPostDecompositionNotice,
  buildPostConfirmationNotice,
  buildPostReviewClearNotice,
  buildPostInvalidationNotice,
  buildCheckNowNotice,
  isRecentEvent,
} from "./position-helpers";

function PositionDetailInner() {
  const { ticker } = useParams<{ ticker: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const requestedTab = searchParams.get("tab");
  const [activeTab, setActiveTab] = useState<TabId>(
    requestedTab === "monitoring" || requestedTab === "decisions" ? requestedTab : "thesis",
  );
  useEffect(() => {
    if (requestedTab === "monitoring" || requestedTab === "decisions") {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- navigation can change the requested tab without remounting this route
      setActiveTab(requestedTab);
    }
  }, [requestedTab]);
  const [holdings, setHoldings] = useState<Holding[]>([]);
  const [theses, setTheses] = useState<Thesis[]>([]);
  const [events, setEvents] = useState<MonitoringEvent[]>([]);
  const [decompositionEnvelope, setDecompositionEnvelope] = useState<ThesisDecompositionEnvelope | null>(null);
  const [editing, setEditing] = useState(false);
  const [invalidateOpen, setInvalidateOpen] = useState(false);
  const [invalidateReason, setInvalidateReason] = useState("");
  const [reaffirming, setReaffirming] = useState(false);
  const [decompositionLoading, setDecompositionLoading] = useState(false);
  const [decompositionSaving, setDecompositionSaving] = useState(false);
  const [convictionLog, setConvictionLog] = useState<ConvictionLogResponse | null>(null);
  const [convictionLogLoading, setConvictionLogLoading] = useState(false);
  const [noteSaving, setNoteSaving] = useState(false);
  const [upcomingEarnings, setUpcomingEarnings] = useState<UpcomingEarnings | null>(null);
  const [pulse, setPulse] = useState<HoldingPulse | null>(null);
  const [reviewedItems, setReviewedItems] = useState<ReviewedItem[]>([]);
  const [supportingItems, setSupportingItems] = useState<SupportingItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [healthCheck, setHealthCheck] = useState<HealthCheckResult | null>(null);
  const [healthCheckLoading, setHealthCheckLoading] = useState(false);
  const [healthSnapshots, setHealthSnapshots] = useState<ThesisHealthSnapshot[]>([]);
  const [showCounterThesis, setShowCounterThesis] = useState(false);
  const [showAnalysis, setShowAnalysis] = useState(false);
  const [showPositionDetails, setShowPositionDetails] = useState(false);
  const [showEarningsReview, setShowEarningsReview] = useState(false);
  const [onboardingState, setOnboardingState] = useState<OnboardingState | null>(null);
  const [nextStepNotice, setNextStepNotice] = useState<NextStepNotice | null>(null);
  const [hasPromptedBlindSpotEditor, setHasPromptedBlindSpotEditor] = useState(false);
  const [deleteConfirming, setDeleteConfirming] = useState(false);
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [thesisSubTab, setThesisSubTab] = useState<ThesisSubTab>("thesis");
  const [headerCollapsed, setHeaderCollapsed] = useState(false);
  const [allGaps, setAllGaps] = useState<MonitoringGap[]>([]);
  const [historicalAudit, setHistoricalAudit] = useState<HistoricalAuditResponse | null>(null);
  const [historicalAuditThesisId, setHistoricalAuditThesisId] = useState<string | null>(null);

  const holding = holdings.find((h) => h.ticker === ticker);
  const activeThesis = selectActiveThesis(theses);
  const currentHistoricalAudit =
    historicalAuditThesisId === activeThesis?.id ? historicalAudit : null;
  const fromOnboarding = searchParams.get("source") === "onboarding";
  const fromBlindSpot = searchParams.get("source") === "dashboard_blind_spot";
  const latestInvalidatedThesis = selectLatestInvalidatedThesis(theses);

  const refreshPulse = async (holdingId: string) => {
    const portfolioPulse = await api.get<PortfolioPulse>("/api/portfolio/pulse").catch(() => null);
    setPulse(portfolioPulse?.pulses.find((p) => p.holding_id === holdingId) ?? null);
  };

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        setHistoricalAudit(null);
        setHistoricalAuditThesisId(null);
        setDecompositionLoading(true);
        const workspace = await loadPositionWorkspace(api, ticker);
        if (cancelled) return;
        setHoldings(workspace.holdings);
        setTheses(workspace.theses);
        setEvents(workspace.events);
        setConvictionLog(workspace.convictionLog);
        setUpcomingEarnings(workspace.upcomingEarnings);
        setOnboardingState(workspace.onboardingState);
        setAllGaps(workspace.monitoringGaps);
        setPulse(workspace.pulse);
        setReviewedItems(workspace.reviewedItems);
        setSupportingItems(workspace.supportingItems);
        setDecompositionEnvelope(workspace.decompositionEnvelope);
        if (workspace.activeThesis) {
          const latestThesis = workspace.activeThesis;
            // Background health check — detects recent earnings without requiring a monitoring event
            void api.post<HealthCheckResult>(`/api/theses/${latestThesis.id}/health-check`)
              .then(setHealthCheck)
              .catch(() => null);
            void api.get<ThesisHealthSnapshot[]>(`/api/theses/${latestThesis.id}/health-history`)
              .then(setHealthSnapshots)
              .catch(() => null);
        }
        // Auto-switch to monitoring if there are unreviewed events
        if (workspace.events.some((event) => !event.review_action)) {
          setActiveTab("monitoring");
        }
      } catch (err) {
        if (!cancelled) console.error(err);
      } finally {
        if (!cancelled) {
          setDecompositionLoading(false);
          setLoading(false);
        }
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [ticker]);

  useEffect(() => {
    if (
      loading ||
      hasPromptedBlindSpotEditor ||
      editing ||
      !fromBlindSpot ||
      activeThesis ||
      latestInvalidatedThesis
    ) {
      return;
    }

    const timeoutId = window.setTimeout(() => {
      startTransition(() => {
        setActiveTab("thesis");
        setEditing(true);
        setHasPromptedBlindSpotEditor(true);
      });
    }, 0);

    return () => window.clearTimeout(timeoutId);
  }, [
    activeThesis,
    editing,
    fromBlindSpot,
    hasPromptedBlindSpotEditor,
    latestInvalidatedThesis,
    loading,
  ]);

  useEffect(() => {
    const onScroll = () => setHeaderCollapsed(window.scrollY > 80);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  // Arriving from onboarding, the backend kicks off a first monitoring pass in
  // the background. Poll briefly so its results land live on this page instead of
  // forcing a manual refresh — turning "we'll watch this" into "we already checked".
  useEffect(() => {
    if (loading || !fromOnboarding) return;
    const match = holdings.find((h) => h.ticker === ticker);
    if (!match) return;

    let cancelled = false;
    let attempts = 0;
    const MAX_ATTEMPTS = 6; // ~30s at 5s spacing

    const poll = async () => {
      attempts += 1;
      try {
        const fresh = await api.get<MonitoringEvent[]>(`/api/monitoring/holdings/${match.id}/events`);
        if (cancelled) return;
        setEvents((prev) => (fresh.length > prev.length ? fresh : prev));
        if (fresh.some((ev) => !ev.review_action)) {
          setActiveTab("monitoring"); // surface what the first pulse found
          return; // results are in — stop polling
        }
      } catch {
        // best-effort; the page already has whatever loaded on mount
      }
      if (!cancelled && attempts < MAX_ATTEMPTS) {
        timer = window.setTimeout(poll, 5000);
      }
    };

    let timer = window.setTimeout(poll, 5000);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [loading, fromOnboarding, ticker, holdings]);

  useEffect(() => {
    if (!activeThesis) return;
    if (!decompositionEnvelope || !["confirmed", "partially_confirmed"].includes(decompositionEnvelope.status)) return;
    if (currentHistoricalAudit && currentHistoricalAudit.status !== "pending") return;

    const thesisId = activeThesis.id;
    let cancelled = false;
    let attempts = 0;
    const FAST_ATTEMPTS = 20;
    const MAX_ATTEMPTS = 40; // ~60s fast, then slow retries through the 10m stale-job window

    const poll = async () => {
      attempts += 1;
      try {
        const result = await api.get<HistoricalAuditResponse>(
          `/api/theses/${thesisId}/historical-audit`
        );
        if (cancelled) return;
        setHistoricalAuditThesisId(thesisId);
        setHistoricalAudit(result);
        if (result.status !== "pending") return;
      } catch {
        // silently ignore — audit card is non-critical
      }
      if (!cancelled && attempts < MAX_ATTEMPTS) {
        timer = window.setTimeout(poll, attempts < FAST_ATTEMPTS ? 3000 : 30000);
      }
    };

    let timer: number | undefined;
    void poll();
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [activeThesis?.id, currentHistoricalAudit?.status, decompositionEnvelope?.status, historicalAuditThesisId]); // eslint-disable-line react-hooks/exhaustive-deps

  const runHealthCheck = async (thesisId: string) => {
    try {
      setHealthCheckLoading(true);
      const result = await api.post<HealthCheckResult>(`/api/theses/${thesisId}/health-check`);
      setHealthCheck(result);
    } catch (err) {
      console.error("Health check failed:", err);
    } finally {
      setHealthCheckLoading(false);
    }
  };

  const refreshCurrentThesis = async () => {
    if (!holding) return;
    const refreshed = await api.get<Thesis[]>(`/api/theses/holding/${holding.id}`);
    setTheses(refreshed);
  };

  const refreshEvents = async () => {
    if (!holding) return;
    const refreshed = await api.get<MonitoringEvent[]>(`/api/monitoring/holdings/${holding.id}/events`);
    setEvents(refreshed);
    return refreshed;
  };

  const refreshConvictionLog = async () => {
    if (!holding) return;
    try {
      setConvictionLogLoading(true);
      const refreshed = await api.get<ConvictionLogResponse>(`/api/portfolio/holdings/${holding.id}/conviction-log`);
      setConvictionLog(refreshed);
    } catch (error) {
      console.error(error);
    } finally {
      setConvictionLogLoading(false);
    }
  };

  const handleAssist = async (draft: {
    why_own_it: string;
    must_remain_true: string;
    what_would_change_my_mind: string;
  }): Promise<ThesisAssistResponse> => {
    if (!holding) throw new Error("Holding not found");
    return api.post<ThesisAssistResponse>("/api/theses/assist", {
      holding_id: holding.id,
      draft_text: draft.why_own_it,
      why_own_it: draft.why_own_it,
      must_remain_true: draft.must_remain_true,
      what_would_change_my_mind: draft.what_would_change_my_mind,
    });
  };

  const handleSave = async (data: {
    thesis_kind: "company";
    why_own_it: string;
    must_remain_true: string | null;
    what_would_change_my_mind: string;
    confidence: "high" | "medium" | "low";
    review_cadence_days: number;
    ai_summary: string | null;
    interpretation: Record<string, unknown> | null;
    source: "user" | "ai_assisted";
    status: "active";
  }) => {
    try {
      let savedThesisId: string | null = null;
      if (activeThesis) {
        const updated = await api.put<Thesis>(`/api/theses/${activeThesis.id}`, data);
        setTheses((current) => current.map((t) => (t.id === updated.id ? updated : t)));
        savedThesisId = updated.id;
      } else if (holding) {
        try {
          const created = await api.post<Thesis>("/api/theses", { holding_id: holding.id, ...data });
          setTheses((current) => [created, ...current]);
          savedThesisId = created.id;
        } catch (error) {
          const message = getErrorMessage(error, "");
          if (message === "A current thesis already exists for this holding") {
            const refreshed = await api.get<Thesis[]>(`/api/theses/holding/${holding.id}`);
            setTheses(refreshed);
            const existing = refreshed.find((item) => item.status === "active" || item.status === "draft" || item.status === "needs_review");
            if (!existing) {
              throw error;
            }
            const updated = await api.put<Thesis>(`/api/theses/${existing.id}`, data);
            setTheses((current) => current.map((t) => (t.id === updated.id ? updated : t)));
            savedThesisId = updated.id;
            toast.message("Updated the existing reason for this holding.");
          } else {
            throw error;
          }
        }
      }
      setDecompositionEnvelope(null);
      setHistoricalAudit(null);
      setHistoricalAuditThesisId(null);
      setEditing(false);
      if (savedThesisId) {
        runHealthCheck(savedThesisId);
        setShowCounterThesis(true);
        setShowAnalysis(true);
        setActiveTab("thesis");
        setThesisSubTab("thesis");
        setNextStepNotice(buildPostSaveNotice({
          investorProfile: onboardingState?.investor_profile ?? null,
          blindSpotStart: fromBlindSpot && !activeThesis && !latestInvalidatedThesis,
        }));
      }
      await refreshConvictionLog();
    } catch (err) {
      console.error(err);
      toast.error(getErrorMessage(err, "Failed to save reason"));
    }
  };

  const handleInvalidate = async () => {
    if (!activeThesis) return;
    try {
      const updated = await api.post<Thesis>(`/api/theses/${activeThesis.id}/invalidate`, { reason: invalidateReason });
      setTheses(theses.map((t) => (t.id === updated.id ? updated : t)));
      setDecompositionEnvelope(null);
      setInvalidateOpen(false);
      setInvalidateReason("");
      await refreshConvictionLog();
    } catch (err) {
      console.error(err);
    }
  };

  const handleReaffirm = async () => {
    if (!activeThesis) return;
    try {
      setReaffirming(true);
      const updated = await api.post<Thesis>(`/api/theses/${activeThesis.id}/reaffirm`);
      setTheses(theses.map((t) => (t.id === updated.id ? updated : t)));
      await refreshConvictionLog();
    } catch (err) {
      console.error(err);
    } finally {
      setReaffirming(false);
    }
  };

  const handleGenerateDecomposition = async () => {
    if (!activeThesis) return;
    try {
      setDecompositionLoading(true);
      const envelope = await api.post<ThesisDecompositionEnvelope>(`/api/theses/${activeThesis.id}/decompose`);
      setDecompositionEnvelope(envelope);
      setActiveTab("thesis");
      setThesisSubTab("signals");
      setNextStepNotice(buildPostDecompositionNotice(envelope, onboardingState?.investor_profile ?? null));
      await refreshCurrentThesis();
    } catch (error) {
      const message = getErrorMessage(error, "Failed to generate thesis signals");
      setDecompositionEnvelope({ status: "failed", message, decomposition: null });
    } finally {
      setDecompositionLoading(false);
    }
  };

  const handleConfirmDecomposition = async (payload: ConfirmDecompositionRequest) => {
    if (!activeThesis) return;
    setHistoricalAuditThesisId(activeThesis.id);
    setHistoricalAudit({ status: "pending", results: null });
    try {
      setDecompositionSaving(true);
      const envelope = await api.post<ThesisDecompositionEnvelope>(`/api/theses/${activeThesis.id}/decomposition/confirm`, payload);
      const confirmedSignalCount =
        envelope.decomposition?.claims.reduce(
          (sum, claim) =>
            sum +
            claim.entities.reduce(
              (entitySum, entity) => entitySum + entity.signals.filter((signal) => signal.active).length,
              0,
            ),
          0,
        ) ?? 0;
      setDecompositionEnvelope(envelope);
      setActiveTab("monitoring");
      setNextStepNotice(
        buildPostConfirmationNotice({
          investorProfile: onboardingState?.investor_profile ?? null,
          activeSignalCount: confirmedSignalCount,
        }),
      );
      await refreshCurrentThesis();
      await refreshConvictionLog();
    } catch (error) {
      toast.error(getErrorMessage(error, "Failed to save signal setup"));
    } finally {
      setDecompositionSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!holding) return;
    try {
      setDeleteLoading(true);
      await api.delete(`/api/portfolio/holdings/${holding.id}`);
      toast.success("Position removed");
      router.push("/dashboard");
    } catch (error) {
      toast.error(getErrorMessage(error, "Failed to remove position"));
      setDeleteConfirming(false);
    } finally {
      setDeleteLoading(false);
    }
  };

  const handleFlagEvent = async (eventId: string) => {
    try {
      await api.post(`/api/monitoring/events/${eventId}/review`, { action: "not_relevant" });
      await Promise.all([refreshEvents(), refreshConvictionLog()]);
    } catch (error) {
      console.error(error);
      toast.error("Failed to flag the event");
      throw error;
    }
  };

  const handleCheckInComplete = async (
    result: SubmitClaimReviewsResponse,
    thesisAction: "keep_lowered" | "rewrite" | "invalidate" | null,
  ) => {
    const [refreshedEvents] = await Promise.all([refreshEvents(), refreshConvictionLog(), refreshCurrentThesis()]);
    if (thesisAction === "invalidate") {
      setActiveTab("thesis");
      setNextStepNotice(buildPostInvalidationNotice(onboardingState?.investor_profile ?? null));
    } else if (thesisAction === "rewrite") {
      setActiveTab("thesis");
      setEditing(true);
    } else if (refreshedEvents && refreshedEvents.every((candidate) => candidate.review_action)) {
      setNextStepNotice(buildPostReviewClearNotice(onboardingState?.investor_profile ?? null));
    }
    if (typeof window !== "undefined") {
      window.localStorage.setItem(
        "dashboard_recent_review",
        JSON.stringify({
          ticker: holding?.ticker,
          action: thesisAction ?? "check_in",
          assumption_label: null,
          resolved_all: Boolean(refreshedEvents && refreshedEvents.every((candidate) => candidate.review_action)),
          thesis_status: result.thesis_status,
          saved_at: new Date().toISOString(),
        }),
      );
    }
  };

  const handleAddManualNote = async (content: string) => {
    if (!holding) return;
    try {
      setNoteSaving(true);
      await api.post(`/api/portfolio/holdings/${holding.id}/conviction-log`, { content });
      await refreshConvictionLog();
    } catch (error) {
      console.error(error);
    } finally {
      setNoteSaving(false);
    }
  };

  const handleCheckNowComplete = async (result: CheckNowResponse) => {
    await refreshEvents();
    await refreshCurrentThesis();
    if (holding) {
      await refreshPulse(holding.id);
      // The relevance filter can produce fresh reviewed-but-dropped items on
      // this same pass, so pull them alongside events/pulse — otherwise the
      // 'Reviewed this week' block stays stale until a full reload.
      const [nextReviewed, nextSupporting] = await Promise.all([
        api.get<ReviewedItem[]>(`/api/monitoring/holdings/${holding.id}/reviewed`)
          .catch(() => [] as ReviewedItem[]),
        api.get<SupportingItem[]>(`/api/monitoring/holdings/${holding.id}/supporting`)
          .catch(() => [] as SupportingItem[]),
      ]);
      setReviewedItems(nextReviewed);
      setSupportingItems(nextSupporting);
    }
    setActiveTab("monitoring");
    setNextStepNotice(buildCheckNowNotice({
      result,
      investorProfile: onboardingState?.investor_profile ?? null,
    }));
  };

  // ── Loading ──────────────────────────────────────────────────────────────

  if (loading) return (
    <div className="min-h-[calc(100vh-53px)] animate-pulse">
      <div className="sticky top-[52px] z-20 bg-background border-b border-border/60">
        <div className="max-w-5xl mx-auto px-6 lg:px-10">
          <div className="flex items-center justify-between pt-4 pb-2">
            <div className="h-2.5 w-20 bg-muted rounded" />
            <div className="h-7 w-24 bg-muted rounded" />
          </div>
          <div className="flex items-end justify-between gap-6 pb-3">
            <div>
              <div className="h-14 w-32 bg-muted rounded" />
              <div className="h-3 w-40 bg-muted rounded mt-2" />
            </div>
            <div className="text-right space-y-1.5">
              <div className="h-8 w-28 bg-muted rounded" />
              <div className="h-4 w-20 bg-muted rounded" />
            </div>
          </div>
          <div className="flex gap-1 pb-3">
            <div className="h-3 w-20 bg-muted/60 rounded" />
            <div className="h-3 w-24 bg-muted/40 rounded ml-3" />
          </div>
          <div className="flex gap-6 pb-0.5">
            <div className="h-8 w-24 bg-muted/50 rounded" />
            <div className="h-8 w-24 bg-muted/30 rounded" />
          </div>
        </div>
      </div>
      <div className="max-w-5xl mx-auto px-6 lg:px-10 py-8 space-y-4">
        <div className="flex gap-6 mb-2">
          <div className="h-3 w-14 bg-muted rounded" />
          <div className="h-3 w-14 bg-muted/50 rounded" />
          <div className="h-3 w-10 bg-muted/40 rounded" />
        </div>
        <div className="border border-border/60 bg-card rounded-sm p-6 space-y-4">
          <div className="h-3 w-16 bg-muted rounded" />
          <div className="space-y-2">
            <div className="h-4 w-full bg-muted rounded" />
            <div className="h-4 w-5/6 bg-muted rounded" />
            <div className="h-4 w-3/4 bg-muted rounded" />
          </div>
          <div className="grid grid-cols-3 gap-3 pt-2">
            {[1, 2, 3].map(i => (
              <div key={i} className="h-16 bg-muted/40 rounded" />
            ))}
          </div>
        </div>
        <div className="border border-border/60 bg-card/50 rounded-sm p-5 space-y-3">
          <div className="h-3 w-20 bg-muted rounded" />
          {[1, 2].map(i => (
            <div key={i} className="border border-border/40 p-3 rounded-sm space-y-2">
              <div className="flex items-center gap-2">
                <div className="h-2 w-2 bg-muted rounded-full" />
                <div className="h-3 w-32 bg-muted rounded" />
              </div>
              <div className="h-2.5 w-5/6 bg-muted/60 rounded ml-4" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );

  if (!holding) return (
    <div className="max-w-4xl mx-auto px-8 py-8">
      <p className="text-sm text-muted-foreground">Holding not found for ticker {ticker}</p>
    </div>
  );

  // ── Derived state ────────────────────────────────────────────────────────

  const cost = holding.quantity * holding.average_cost_basis;
  // No market price yet (manual add not synced, or data fetch failed) — don't
  // render a misleading £0.00 / -100%; show a neutral "unavailable" instead.
  const hasPrice = (holding.current_value ?? 0) > 0 || (holding.current_price ?? 0) > 0;
  const value = holding.current_value || 0;
  const pnl = value - cost;
  const pnlPct = cost > 0 ? ((pnl / cost) * 100).toFixed(1) : "0.0";
  const thesisInsights = getThesisInsights(
    activeThesis,
    events,
    onboardingState?.investor_profile ?? null,
  );
  const copy = positionCopy(onboardingState?.investor_profile ?? null);
  const recentEarningsEvent =
    events.find(
      (e) => ["earnings_surprise", "earnings_call_transcript"].includes(e.event_type) && !e.review_action && isRecentEvent(e.created_at, 14),
    ) ?? null;

  // Show the post-earnings review prompt only off an actual recent earnings event
  // (gated to 14 days and cleared once reviewed). The old fallback keyed off
  // health_check.recent_earnings_surprise_pct, which is just last quarter's
  // standing surprise with no recency bound — so the prompt never went away, even
  // after running a check or when the next report was months out.
  const showEarningsBanner = Boolean(recentEarningsEvent);
  const hasSignals = Boolean(decompositionEnvelope?.decomposition);
  const hasActiveSignals =
    decompositionEnvelope?.decomposition?.claims.some((claim) =>
      claim.entities.some((entity) => entity.signals.some((signal) => signal.active)),
    ) ?? false;
  const watchHints = Array.isArray(activeThesis?.interpretation?.watch_hints)
    ? activeThesis.interpretation.watch_hints.filter((hint): hint is Record<string, unknown> => typeof hint === "object" && hint !== null)
    : [];
  const monitoringPreviewItems = getMonitoringPreviewItems(decompositionEnvelope, watchHints);
  const earningsWatchList = watchHints.map((h) => describeWatchHint(h)).filter((h): h is string => Boolean(h)).slice(0, 3);
  const unreviewedEvents = events.filter((e) => !e.review_action).length;
  const reviewedEventsCount = events.filter((e) => Boolean(e.review_action)).length;
  const decisionPrompt = getDecisionPrompt(
    activeThesis,
    events,
    onboardingState?.investor_profile ?? null,
  );
  const thesisHandoffPrompt = getThesisHandoffPrompt({
    hasThesis: Boolean(activeThesis),
    hasSignals,
    hasActiveSignals,
    investorProfile: onboardingState?.investor_profile ?? null,
  });
  const onboardingMonitoringMessage = decompositionLoading
    ? "Turning your first reason into watchable signals."
    : decompositionEnvelope?.decomposition
        ? "Your first reason is live and watchable."
        : "Your first reason is live. Next, confirm what to watch.";
  const onboardingMonitoringNextStep = decompositionLoading
    ? "Next: give us a moment to finish the signal candidates."
    : decompositionEnvelope?.decomposition
      ? "Next: confirm these signals."
      : "Next: review the first monitoring rules and tighten anything vague.";

  const tabs: { id: TabId; label: string; badge?: number | string }[] = [
    { id: "thesis", label: "Original case" },
    { id: "monitoring", label: "What changed", badge: unreviewedEvents > 0 ? unreviewedEvents : undefined },
    { id: "decisions", label: "Decisions" },
  ];

  const lastReviewedEvent = events.filter((e) => e.review_action).sort((a, b) =>
    new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  )[0];
  const activeSignalCount =
    decompositionEnvelope?.decomposition?.claims.reduce(
      (sum, claim) =>
        sum +
        claim.entities.reduce(
          (entitySum, entity) => entitySum + entity.signals.filter((signal) => signal.active).length,
          0,
        ),
      0,
    ) ?? 0;
  const monitoringCalmState = getMonitoringCalmState({
    hasReviewedEvents: events.some((event) => Boolean(event.review_action)),
    lastReviewedEventAgeDays: lastReviewedEvent ? ageInDays(lastReviewedEvent.created_at) : null,
    upcomingEarnings,
    monitoringPreviewItems,
    watchHints: earningsWatchList,
    activeSignalCount,
    investorProfile: onboardingState?.investor_profile ?? null,
  });
  const invalidatedTheses = theses.filter((t) => t.status === "invalidated");
  const blindSpotArrivalCopy = getBlindSpotArrivalCopy(onboardingState?.investor_profile ?? null);
  const editorSeedThesis = activeThesis ?? latestInvalidatedThesis ?? null;
  const stalePressure = getCaseReviewPressure(activeThesis);
  const editorMode: "write" | "first_write" | "tighten" | "rewrite" =
    !activeThesis && latestInvalidatedThesis
      ? "rewrite"
      : !activeThesis && fromBlindSpot
        ? "first_write"
      : activeThesis && thesisInsights.qualityLabel === "Weak signals"
        ? "tighten"
        : "write";
  const firstWriteGuide = latestInvalidatedThesis
    ? {
        eyebrow: onboardingState?.investor_profile === "thesis_driven" ? "Rewrite from the last thesis" : "Rewrite from the last reason",
        title:
          onboardingState?.investor_profile === "thesis_driven"
            ? "Keep the part of the case you still believe. Replace the part that already broke."
            : "Keep the part of the story you still believe. Replace the part that already broke.",
        body:
          onboardingState?.investor_profile === "thesis_driven"
            ? "Start from the previous thesis, remove the failed assumption, and write the version you would still buy today."
            : "Start from the previous reason, remove the broken story, and write the version you would still buy today.",
        cta: onboardingState?.investor_profile === "thesis_driven" ? "Rewrite the thesis" : "Rewrite the reason",
      }
    : {
        eyebrow: onboardingState?.investor_profile === "hearsay_driven" ? "Turn the story into a system" : "Turn the position into a system",
        title:
          onboardingState?.investor_profile === "hearsay_driven"
            ? "Write the case that tells penKeep what to watch."
            : "Write the thesis that tells penKeep what to watch.",
        body:
          onboardingState?.investor_profile === "hearsay_driven"
            ? "Once the reason is explicit, this page becomes a real review surface."
            : "Once the thesis is explicit, this page becomes a real review surface.",
        cta: copy.noReasonCta,
      };
  const firstWriteChecklist =
    onboardingState?.investor_profile === "hearsay_driven"
      ? [
          { label: "Why this is in the portfolio", detail: "Name the business reason, in one or two sentences." },
          { label: "What must stay true", detail: "List the condition that would keep your confidence intact." },
          { label: "What would break it", detail: "Define the evidence that should force a rethink." },
        ]
      : [
          { label: "Why you own it", detail: "Write the core belief that makes this position worth holding." },
          { label: "What must remain true", detail: "Spell out the assumption that should stay intact." },
          { label: "What would change your mind", detail: "Define the evidence that should trigger a real decision." },
        ];
  const firstWriteUnlocks =
    onboardingState?.investor_profile === "hearsay_driven"
      ? [
          "Signals get matched to the written story instead of generic price noise.",
          "Review prompts land when the business case moves, regardless of the tape.",
          "The next digest explains what matters for this position in plain language.",
        ]
      : [
          "Signals get tied to explicit assumptions instead of generic headlines.",
          "Review prompts fire on evidence that hits your thesis, regardless of price.",
          "The next digest reads like a portfolio memo, not a watchlist alert.",
        ];
  const suppressSecondaryThesisPrompts = Boolean(decisionPrompt || showEarningsBanner);

  const handleNextStepAction = () => {
    if (!nextStepNotice?.action) return;
    const action = nextStepNotice.action;
    setNextStepNotice(null);
    if (action === "edit") {
      setEditing(true);
      setActiveTab("thesis");
      return;
    }
    if (action === "generate_signals") {
      setActiveTab("thesis");
      setThesisSubTab("signals");
      void handleGenerateDecomposition();
      return;
    }
    setActiveTab("monitoring");
  };

  // ── Render ───────────────────────────────────────────────────────────────

  return (
    <div className="min-h-[calc(100vh-53px)]">

      {/* ── Sticky header ────────────────────────────────────────────────── */}
      <PositionHeader
        holding={holding}
        activeThesis={activeThesis}
        pulse={pulse}
        investorProfile={onboardingState?.investor_profile ?? null}
        headerCollapsed={headerCollapsed}
        hasPrice={hasPrice}
        value={value}
        pnl={pnl}
        pnlPct={pnlPct}
        stalePressure={stalePressure}
        tabs={tabs}
        activeTab={activeTab}
        unreviewedEvents={unreviewedEvents}
        deleteConfirming={deleteConfirming}
        deleteLoading={deleteLoading}
        onDelete={handleDelete}
        onSetDeleteConfirming={setDeleteConfirming}
        onCheckNowComplete={handleCheckNowComplete}
        onSelectTab={(id) => { setActiveTab(id); if (id === "thesis") setThesisSubTab("thesis"); }}
      />

      {/* ── Contextual banners ───────────────────────────────────────────── */}
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-10">

        {fromOnboarding && activeThesis && (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-5 border border-emerald-500/25 bg-emerald-500/8 px-5 py-4 space-y-4"
          >
            <div className="space-y-2">
              <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-emerald-700">
                ● First holding activated
              </p>
              <p className="font-sans text-sm text-foreground/80 leading-relaxed">
                {onboardingMonitoringMessage}
              </p>
            </div>

            {monitoringPreviewItems.length > 0 && (
              <div className="space-y-2">
                <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-foreground/60">
                  What we&apos;re starting to watch
                </p>
                <div className="grid gap-2">
                  {monitoringPreviewItems.map((item) => (
                    <div key={item.key} className="border border-emerald-600/10 bg-background/70 px-3 py-2.5">
                      <p className="font-sans text-sm text-foreground">{item.label}</p>
                      <p className="font-sans text-xs text-muted-foreground mt-1 leading-relaxed">{item.detail}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <p className="font-sans text-xs text-foreground/80 leading-relaxed">
              {onboardingMonitoringNextStep}
            </p>
          </motion.div>
        )}

        {fromBlindSpot && !activeThesis && !editing && (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-5 border border-amber-500/25 bg-amber-500/8 px-5 py-4 space-y-3"
          >
            <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-amber-700">
              {blindSpotArrivalCopy.eyebrow}
            </p>
            <div className="space-y-1.5">
              <p className="font-display italic text-[1.35rem] leading-tight text-foreground">
                {blindSpotArrivalCopy.title}
              </p>
              <p className="font-sans text-sm text-foreground/80 leading-relaxed">
                {blindSpotArrivalCopy.body}
              </p>
            </div>
            <button
              onClick={() => setEditing(true)}
              className="font-mono text-[10px] uppercase tracking-[0.15em] text-primary hover:text-primary/80 transition-colors"
            >
              {blindSpotArrivalCopy.cta}
            </button>
          </motion.div>
        )}

        {nextStepNotice && (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-5 border border-primary/20 bg-primary/5 px-5 py-4 space-y-3"
          >
            <div className="flex items-start justify-between gap-4">
              <div className="space-y-2">
                <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-primary">
                  {nextStepNotice.eyebrow}
                </p>
                <div className="space-y-1">
                  <p className="font-display italic text-[1.35rem] leading-tight text-foreground">
                    {nextStepNotice.title}
                  </p>
                  <p className="font-sans text-sm text-foreground/80 leading-relaxed">
                    {nextStepNotice.body}
                  </p>
                </div>
              </div>
              <button
                onClick={() => setNextStepNotice(null)}
                className="font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground hover:text-foreground transition-colors"
              >
                Dismiss
              </button>
            </div>
            {nextStepNotice.ctaLabel && nextStepNotice.action && (
              <button
                onClick={handleNextStepAction}
                className="font-mono text-[10px] uppercase tracking-[0.15em] text-primary hover:text-primary/80 transition-colors"
              >
                {nextStepNotice.ctaLabel}
              </button>
            )}
          </motion.div>
        )}

        {decisionPrompt && activeThesis && !(fromBlindSpot && !activeThesis && !editing) && (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            className={`mt-5 border px-5 py-4 space-y-3 ${decisionPrompt.tone}`}
          >
            <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-foreground/70">
              {decisionPrompt.eyebrow}
            </p>
            <div className="space-y-1.5">
              <p className="font-display italic text-[1.35rem] leading-tight text-foreground">
                {decisionPrompt.title}
              </p>
              <p className="font-sans text-sm text-foreground/80 leading-relaxed">
                {decisionPrompt.body}
              </p>
            </div>
            <button
              onClick={() => {
                if (decisionPrompt.action === "edit") {
                  setEditing(true);
                  setActiveTab("thesis");
                  return;
                }
                setActiveTab("monitoring");
              }}
              className="font-mono text-[10px] uppercase tracking-[0.15em] text-primary hover:text-primary/80 transition-colors"
            >
              {decisionPrompt.ctaLabel}
            </button>
          </motion.div>
        )}

        {activeThesis && upcomingEarnings && upcomingEarnings.days_until <= 14 && (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-5 border border-sky-500/25 bg-sky-500/8 px-5 py-4 space-y-3"
          >
            <div className="flex items-center gap-3">
              <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-sky-700">
                ● Earnings in {upcomingEarnings.days_until === 0 ? "today" : upcomingEarnings.days_until === 1 ? "tomorrow" : `${upcomingEarnings.days_until} days`}
              </span>
              <span className="font-mono text-[10px] text-muted-foreground">{formatDate(upcomingEarnings.report_date)}</span>
            </div>
            {earningsWatchList.length > 0 ? (
              <div className="flex flex-wrap gap-2">
                {earningsWatchList.map((item) => (
                  <span key={item} className="font-sans text-xs text-foreground/70 border border-border/60 bg-card px-3 py-1">
                    {item}
                  </span>
                ))}
              </div>
            ) : (
              <p className="font-sans text-xs text-muted-foreground">
                {copy.earningsEmpty}
              </p>
            )}
          </motion.div>
        )}

        {showEarningsBanner && (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-5 border border-amber-500/25 bg-amber-500/8 px-5 py-4 space-y-4"
          >
            <div>
              <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-amber-700">
                ● Earnings just landed
              </span>
              <p className="font-sans text-sm text-foreground/80 leading-relaxed mt-1">
                {recentEarningsEvent
                  ? (recentEarningsEvent.ai_analysis || recentEarningsEvent.evidence_summary || recentEarningsEvent.summary)
                  : healthCheck?.recent_earnings_surprise_pct !== null && healthCheck?.recent_earnings_surprise_pct !== undefined
                    ? `${cleanTicker(ticker)} reported earnings with a ${healthCheck.recent_earnings_surprise_pct > 0 ? "+" : ""}${healthCheck.recent_earnings_surprise_pct.toFixed(1)}% surprise. ${copy.postEarningsReview}`
                    : `${cleanTicker(ticker)} recently reported earnings. ${copy.postEarningsReview}`
                }
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                onClick={() => setShowEarningsReview(true)}
                className="font-mono text-[10px] uppercase tracking-[0.15em] border border-amber-600/40 text-amber-700 bg-amber-50 hover:bg-amber-100 px-4 py-2 transition-colors"
              >
                {onboardingState?.investor_profile === "thesis_driven"
                  ? "Review thesis claim by claim →"
                  : onboardingState?.investor_profile === "hearsay_driven"
                    ? "Review the reason claim by claim →"
                    : "Review reason claim by claim →"}
              </button>
            </div>
          </motion.div>
        )}
      </div>

      {showEarningsReview && activeThesis && (
        <EarningsReviewModal
          thesisId={activeThesis.id}
          ticker={cleanTicker(ticker)}
          investorProfile={onboardingState?.investor_profile ?? null}
          onClose={() => setShowEarningsReview(false)}
        />
      )}

      {/* ── Tab content ─────────────────────────────────────────────────── */}
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-10">
        <AnimatePresence mode="wait">
          <motion.div
            key={activeTab}
            initial={{ opacity: 0, y: 5 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -5 }}
            transition={{ duration: 0.16, ease: "easeOut" }}
            className="py-8 space-y-8"
          >

            {/* ─── THESIS TAB ──────────────────────────────────────────── */}
            {activeTab === "thesis" && (
              <>
                {/* Action prompt */}
                {thesisInsights.canReaffirm && !editing && !suppressSecondaryThesisPrompts && (
                  <div className="border-l-2 border-primary/30 pl-4 py-1 flex items-start justify-between gap-4">
                    <p className="font-sans text-sm text-foreground/80 leading-relaxed max-w-xl">
                      {thesisInsights.nextStep}
                    </p>
                    <div className="flex gap-2 shrink-0">
                      {activeThesis && thesisInsights.canReaffirm && (
                        <button
                          onClick={handleReaffirm}
                          disabled={reaffirming}
                          className="font-mono text-[10px] uppercase tracking-[0.15em] border border-primary/40 text-primary px-4 py-2 hover:border-primary transition-colors disabled:opacity-40"
                        >
                          {reaffirming ? "Reaffirming…" : "Still holding"}
                        </button>
                      )}
                      {activeThesis && (
                        <button
                          onClick={() => setShowEarningsReview(true)}
                          className="font-mono text-[10px] uppercase tracking-[0.15em] border border-border text-muted-foreground hover:text-foreground px-4 py-2 transition-colors"
                        >
                          {copy.afterEarningsCta}
                        </button>
                      )}
                    </div>
                  </div>
                )}

                {thesisHandoffPrompt && !editing && !suppressSecondaryThesisPrompts && (
                  <div className="border-l-2 border-sky-500/30 pl-4 py-1 flex items-start justify-between gap-4">
                    <div className="space-y-1">
                      <p className="font-sans text-sm text-foreground/90 leading-relaxed max-w-xl">
                        {thesisHandoffPrompt.title}
                      </p>
                      <p className="font-sans text-sm text-muted-foreground leading-relaxed max-w-xl">
                        {thesisHandoffPrompt.body}
                      </p>
                    </div>
                    <button
                      onClick={() => {
                        setActiveTab("thesis");
                        setThesisSubTab("signals");
                        if (thesisHandoffPrompt.action === "generate") {
                          void handleGenerateDecomposition();
                        }
                      }}
                      className="font-mono text-[10px] uppercase tracking-[0.15em] text-primary px-4 py-2 hover:text-primary/80 transition-colors shrink-0"
                    >
                      {thesisHandoffPrompt.ctaLabel}
                    </button>
                  </div>
                )}

                {/* Editor */}
                {editing && (
                  <ThesisEditor
                    thesis={editorSeedThesis}
                    investorProfile={onboardingState?.investor_profile ?? null}
                    mode={editorMode}
                    onSave={handleSave}
                    onAssist={handleAssist}
                    onCancel={() => setEditing(false)}
                  />
                )}

                {/* ── Sub-tabs (when thesis exists and not editing) ───────── */}
                {activeThesis && !editing && (
                  <>
                    <div className="flex gap-1 -mx-1 border-b border-border/40">
                      {(
                        [
                          { id: "thesis" as ThesisSubTab, label: "Thesis" },
                          { id: "signals" as ThesisSubTab, label: "Signals", badge: hasActiveSignals ? activeSignalCount : undefined },
                          { id: "log" as ThesisSubTab, label: "History", badge: (convictionLog?.entries.length ?? 0) > 0 ? convictionLog!.entries.length : undefined },
                        ]
                      ).map((sub) => (
                        <button
                          key={sub.id}
                          onClick={() => setThesisSubTab(sub.id)}
                          className="relative pb-3 px-3 font-mono text-[10px] uppercase tracking-[0.18em] transition-colors flex items-center gap-1.5"
                          style={{ color: thesisSubTab === sub.id ? "var(--primary)" : "var(--muted-foreground)" }}
                        >
                          {sub.label}
                          {sub.badge !== undefined && (
                            <span className="font-mono text-[9px] text-muted-foreground/70 tabular-nums">{sub.badge}</span>
                          )}
                          {thesisSubTab === sub.id && (
                            <motion.div layoutId="thesis-sub-indicator" className="absolute bottom-0 left-0 right-0 h-px bg-primary" transition={{ type: "spring", stiffness: 400, damping: 35 }} />
                          )}
                        </button>
                      ))}
                    </div>

                    {/* ── Thesis sub-tab ──────────────────────────────────── */}
                    {thesisSubTab === "thesis" && (
                      <div className="space-y-6">
                        <ThesisCard
                          thesis={activeThesis}
                          decomposition={decompositionEnvelope?.decomposition ?? null}
                          investorProfile={onboardingState?.investor_profile ?? null}
                          monitoringGaps={allGaps.filter((g) => g.thesis_id === activeThesis.id)}
                          onEdit={() => setEditing(true)}
                          onInvalidate={() => setInvalidateOpen(true)}
                        />
                        {(healthCheck || healthCheckLoading || showCounterThesis) && (
                          <div className="product-panel p-5 sm:p-6">
                            <div className="flex items-center justify-between gap-4">
                              <div className="space-y-1">
                                <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                                  Review tools
                                </p>
                              </div>
                              <button onClick={() => setShowAnalysis((s) => !s)} className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground hover:text-foreground transition-colors shrink-0">
                                {showAnalysis ? "Hide" : "Show"}
                              </button>
                            </div>
                            {showAnalysis && (
                              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className={`mt-4 grid gap-4 ${showCounterThesis && (healthCheck || healthCheckLoading) ? "lg:grid-cols-2" : ""}`}>
                                {(healthCheck || healthCheckLoading) && (
                                  <ThesisHealthCheck result={healthCheck} loading={healthCheckLoading} investorProfile={onboardingState?.investor_profile ?? null} />
                                )}
                                {showCounterThesis && <CounterThesisCard thesisId={activeThesis.id} investorProfile={onboardingState?.investor_profile ?? null} />}
                              </motion.div>
                            )}
                          </div>
                        )}
                        <div className="border-t border-border/40 pt-5">
                          <button onClick={() => setShowPositionDetails((s) => !s)} className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground hover:text-foreground transition-colors">
                            {showPositionDetails ? "▲" : "▼"} Details
                          </button>
                          {showPositionDetails && (
                            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="grid grid-cols-2 md:grid-cols-5 gap-3 mt-4">
                              {[
                                // Price & avg cost in the instrument's native currency (USD for a US
                                // stock); value, P&L and the portfolio total stay in the account
                                // currency (GBP) — the standard multi-currency broker split.
                                { label: "Shares", value: String(holding.quantity) },
                                { label: "Price", value: holding.current_price != null ? formatCurrency(holding.current_price, holding.currency || "GBP") : "—" },
                                { label: "Avg cost", value: holding.average_cost_native != null
                                    ? formatCurrency(holding.average_cost_native, holding.currency || "GBP")
                                    : formatCurrency(holding.average_cost_basis) },
                                { label: "Current value", value: formatCurrency(value) },
                                { label: "P&L", value: `${pnl >= 0 ? "+" : ""}${formatCurrency(pnl)}`, colored: true },
                              ].map(({ label, value: v, colored }) => (
                                <div key={label} className="border border-border/60 bg-card px-4 py-3">
                                  <p className="font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground">{label}</p>
                                  <p className={`font-mono text-lg tabular-nums mt-1.5 ${colored ? (pnl >= 0 ? "text-emerald-700" : "text-red-600") : "text-foreground"}`}>{v}</p>
                                </div>
                              ))}
                            </motion.div>
                          )}
                        </div>
                      </div>
                    )}

                    {/* ── Signals sub-tab ─────────────────────────────────── */}
                    {thesisSubTab === "signals" && (
                      <div className="space-y-8">
                        {decompositionEnvelope?.decomposition ? (
                          <ThesisDiffView
                            decomposition={decompositionEnvelope.decomposition}
                            monitoringEvents={events}
                            healthSnapshots={healthSnapshots}
                          />
                        ) : (
                          !decompositionLoading && (
                            <div className="space-y-6">
                              {monitoringPreviewItems.length > 0 && (
                                <div className="product-panel p-5 sm:p-6 space-y-4">
                                  <div className="space-y-1.5">
                                    <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                                      Current watch rules
                                    </p>
                                    <p className="font-sans text-sm text-foreground/80 leading-relaxed">
                                      These rules are already attached to the thesis. Generate the full signal map to connect them to claims, entities, and evidence.
                                    </p>
                                  </div>
                                  <div className="grid gap-3">
                                    {monitoringPreviewItems.map((item) => (
                                      <div key={item.key} className="border border-border/60 bg-background/70 px-4 py-3 space-y-1.5">
                                        <p className="font-sans text-sm text-foreground">{item.label}</p>
                                        <p className="font-sans text-xs text-muted-foreground leading-relaxed">{item.detail}</p>
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              )}
                              <div className="py-6 text-center space-y-3">
                                <p className="font-display italic text-xl text-foreground/50">
                                  {monitoringPreviewItems.length > 0 ? "No structured signal map yet." : "No signals defined yet."}
                                </p>
                                <p className="font-sans text-sm text-muted-foreground max-w-md mx-auto leading-relaxed">
                                  {monitoringPreviewItems.length > 0
                                    ? "Generate signals to turn these watch rules into the full claim, entity, and signal map."
                                    : "Generate signals from the thesis."}
                                </p>
                                <button onClick={handleGenerateDecomposition} className="font-mono text-[10px] uppercase tracking-[0.15em] border border-primary/40 text-primary px-5 py-2.5 hover:border-primary transition-colors">
                                  Generate signals
                                </button>
                              </div>
                            </div>
                          )
                        )}
                        <div className={decompositionEnvelope?.decomposition ? "border-t border-border/40 pt-6 space-y-3" : ""}>
                          {decompositionEnvelope?.decomposition && (
                            <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">Signal setup</p>
                          )}
                          <ThesisDecompositionReview
                            key={`${decompositionEnvelope?.decomposition?.id ?? "empty"}:${decompositionEnvelope?.status ?? "none"}`}
                            envelope={decompositionEnvelope}
                            loading={decompositionLoading}
                            saving={decompositionSaving}
                            onGenerate={handleGenerateDecomposition}
                            onConfirm={handleConfirmDecomposition}
                          />
                        </div>

                        {/* ── Historical audit card ──────────────────────── */}
                        {activeThesis && (decompositionEnvelope?.status === "confirmed" || decompositionEnvelope?.status === "partially_confirmed") && (
                          <HistoricalAuditCard audit={currentHistoricalAudit} />
                        )}
                      </div>
                    )}

                    {/* ── Log sub-tab ─────────────────────────────────────── */}
                    {thesisSubTab === "log" && (
                      <>
                        <ConvictionLog
                          data={convictionLog}
                          loading={convictionLogLoading}
                          saving={noteSaving}
                          onAddNote={activeThesis ? handleAddManualNote : undefined}
                          investorProfile={onboardingState?.investor_profile ?? null}
                        />
                        {invalidatedTheses.length > 0 && (
                          <div className="border-t border-border/40 pt-6 space-y-3">
                            <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                              {onboardingState?.investor_profile === "thesis_driven" ? "Previous theses" : "Previous reasons"}
                            </p>
                            {invalidatedTheses.map((t) => (
                              <div key={t.id} className="border-l-2 border-border/60 pl-4 py-3 space-y-1.5">
                                <p className="font-sans text-sm text-foreground/85 leading-relaxed italic">&ldquo;{t.why_own_it}&rdquo;</p>
                                {t.invalidation_reason && (
                                  <p className="font-sans text-xs text-muted-foreground">Closed: {t.invalidation_reason}</p>
                                )}
                                <p className="font-mono text-[10px] text-muted-foreground/60">{formatDate(t.updated_at)}</p>
                              </div>
                            ))}
                          </div>
                        )}
                      </>
                    )}
                  </>
                )}

                {/* No thesis empty state */}
                {!activeThesis && !editing && (
                  <div className="grid gap-5 lg:grid-cols-[minmax(0,1.2fr)_minmax(16rem,20rem)]">
                    <section className="product-panel product-panel-muted overflow-hidden p-5 sm:p-6">
                      <div className="space-y-5">
                        <div className="space-y-2">
                          <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-primary">
                            {firstWriteGuide.eyebrow}
                          </p>
                          <div className="space-y-2">
                            <p className="font-display italic text-[1.6rem] leading-tight text-foreground sm:text-[1.85rem]">
                              {firstWriteGuide.title}
                            </p>
                            <p className="font-sans text-sm text-foreground/80 leading-relaxed max-w-2xl">
                              {firstWriteGuide.body}
                            </p>
                          </div>
                        </div>

                        <div className="grid gap-3 sm:grid-cols-3">
                          {firstWriteChecklist.map((item) => (
                            <div key={item.label} className="border border-border/70 bg-background/75 p-4">
                              <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                                {item.label}
                              </p>
                              <p className="mt-2 font-sans text-sm leading-relaxed text-foreground/85">
                                {item.detail}
                              </p>
                            </div>
                          ))}
                        </div>

                        <div className="flex flex-wrap items-center gap-3">
                          <button
                            onClick={() => setEditing(true)}
                            className="bg-primary px-5 py-2.5 font-mono text-[10px] uppercase tracking-[0.18em] text-primary-foreground transition-colors hover:bg-primary/90"
                          >
                            {firstWriteGuide.cta}
                          </button>
                          <p className="font-sans text-xs leading-relaxed text-muted-foreground">
                            {latestInvalidatedThesis
                              ? "We will preload the last version so you can rewrite from something real."
                              : "You only need a short, specific draft to unlock monitoring."}
                          </p>
                        </div>
                      </div>
                    </section>

                    <aside className="product-panel p-5 sm:p-6">
                      <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                        What this unlocks
                      </p>
                      <div className="mt-4 space-y-3">
                        {firstWriteUnlocks.map((item) => (
                          <div key={item} className="border-l-2 border-primary/20 pl-3">
                            <p className="font-sans text-sm leading-relaxed text-foreground/80">
                              {item}
                            </p>
                          </div>
                        ))}
                      </div>
                    </aside>
                  </div>
                )}

              </>
            )}

            {/* ─── MONITORING TAB ──────────────────────────────────────── */}
            {activeTab === "monitoring" && (
              <div>
                <MonitoringTab
                  hasThesis={Boolean(activeThesis)}
                  thesisId={activeThesis?.id ?? null}
                  ticker={holding?.ticker ?? ticker}
                  writtenCase={{
                    whyOwnIt: activeThesis?.why_own_it ?? "",
                    stillTrueIf: activeThesis?.must_remain_true ?? null,
                    breaksIf: activeThesis?.what_would_change_my_mind ?? null,
                  }}
                  investorProfile={onboardingState?.investor_profile ?? null}
                  events={events}
                  unreviewedEvents={unreviewedEvents}
                  activeSignalCount={activeSignalCount}
                  hasSignals={hasSignals}
                  calmState={monitoringCalmState}
                  decompositionLoading={decompositionLoading}
                  emptyCopy={{ title: copy.monitoringEmptyTitle, body: copy.monitoringEmptyBody, cta: copy.monitoringEmptyCta }}
                  reviewedItems={reviewedItems}
                  supportingItems={supportingItems}
                  onFlagEvent={handleFlagEvent}
                  onAfterCheckIn={handleCheckInComplete}
                  onWriteThesis={() => { setEditing(true); setActiveTab("thesis"); }}
                />
              </div>
            )}

            {/* ─── DECISIONS TAB ───────────────────────────────────────── */}
            {activeTab === "decisions" && holding && (
              <PositionDecisions holdingId={holding.id} reloadKey={reviewedEventsCount} />
            )}

          </motion.div>
        </AnimatePresence>
      </div>

      {/* ── Invalidate dialog ────────────────────────────────────────────── */}
      <InvalidateDialog
        open={invalidateOpen}
        onOpenChange={setInvalidateOpen}
        investorProfile={onboardingState?.investor_profile ?? null}
        reason={invalidateReason}
        onReasonChange={setInvalidateReason}
        onConfirm={handleInvalidate}
      />
    </div>
  );
}

export default function PositionDetailPage() {
  return (
    <Suspense>
      <PositionDetailInner />
    </Suspense>
  );
}
