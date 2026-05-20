"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import { api } from "@/lib/api";
import { getErrorMessage } from "@/lib/errors";
import { formatCurrency, formatDate } from "@/lib/utils";
import { toast } from "sonner";
import { ThesisCard } from "@/components/thesis/thesis-card";
import { ConvictionLog } from "@/components/thesis/conviction-log";
import { ThesisDecompositionReview } from "@/components/thesis/thesis-decomposition-review";
import { ThesisEditor } from "@/components/thesis/thesis-editor";
import { EventTimeline } from "@/components/monitoring/event-timeline";
import { EventReviewStack } from "@/components/monitoring/event-review-stack";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { ThesisHealthCheck } from "@/components/thesis/thesis-health-check";
import { CounterThesisCard } from "@/components/thesis/counter-thesis-card";
import { CheckNowButton } from "@/components/monitoring/check-now-button";
import type {
  ConfirmDecompositionRequest,
  ConvictionLogResponse,
  HealthCheckResult,
  Holding,
  MonitoringEvent,
  MonitoringEventReviewResponse,
  Thesis,
  ThesisAssistResponse,
  ThesisDecompositionEnvelope,
  UpcomingEarnings,
} from "@/types";

type TabId = "thesis" | "monitoring" | "history";

function cleanTicker(ticker: string) {
  return ticker.replace(/_US_EQ$/, "").replace(/_EQ$/, "");
}

function ageInDays(dateString: string) {
  const now = Date.now();
  const then = new Date(dateString).getTime();
  return Math.max(0, Math.floor((now - then) / (1000 * 60 * 60 * 24)));
}

function getThesisInsights(thesis: Thesis | undefined, events: MonitoringEvent[]) {
  if (!thesis) {
    return {
      nextStep: "Write the first thesis for this position so monitoring has something real to watch.",
      qualityLabel: "No thesis yet",
      qualityTone: "bg-red-500/15 text-red-600",
      statusDot: "text-red-500",
      watchStatus: "This position is not being monitored against any explicit belief yet.",
      canReaffirm: false,
    };
  }

  const interpretation = thesis.interpretation ?? {};
  const monitorability = typeof interpretation.monitorability === "string" ? interpretation.monitorability : "medium";
  const ambiguity = typeof interpretation.ambiguity_note === "string" ? interpretation.ambiguity_note : "";
  const stale = ageInDays(thesis.updated_at) > 90;
  const latestEvent = events[0];

  if (thesis.status === "needs_review") {
    return {
      nextStep: latestEvent?.ai_analysis || "Review what changed and decide whether the thesis still holds.",
      qualityLabel: "Needs review",
      qualityTone: "bg-orange-500/15 text-orange-600",
      statusDot: "text-orange-500",
      watchStatus: "Monitoring found something worth revisiting in this thesis.",
      canReaffirm: true,
    };
  }

  if (stale) {
    return {
      nextStep: "This thesis is old. Re-read it and either reaffirm it or tighten the language.",
      qualityLabel: "Stale",
      qualityTone: "bg-amber-500/15 text-amber-700",
      statusDot: "text-amber-500",
      watchStatus: "Nothing necessarily broke, but this reasoning has not been reviewed in a while.",
      canReaffirm: true,
    };
  }

  if (monitorability === "low") {
    return {
      nextStep: ambiguity || "Tighten the thesis so the app can monitor something more precise.",
      qualityLabel: "Weak signals",
      qualityTone: "bg-muted text-muted-foreground",
      statusDot: "text-muted-foreground",
      watchStatus: "The current reason is too vague for high-confidence monitoring.",
      canReaffirm: false,
    };
  }

  return {
    nextStep: latestEvent ? latestEvent.ai_analysis || "Monitoring is active. Review the latest event if it still matters." : "The thesis looks healthy. No action needed.",
    qualityLabel: "Intact",
    qualityTone: "bg-emerald-500/15 text-emerald-700",
    statusDot: "text-emerald-500",
    watchStatus: latestEvent ? "Monitoring has context to evaluate new changes against this thesis." : "Monitoring is active, no material change flagged.",
    canReaffirm: false,
  };
}

const METRIC_LABELS: Record<string, string> = {
  revenue_growth_yoy: "Revenue growth (YoY)",
  earnings_growth_yoy: "Earnings growth (YoY)",
  pe_ratio: "P/E ratio",
  dividend_yield: "Dividend yield",
  gross_margin: "Gross margin",
  operating_margin: "Operating margin",
  debt_to_equity: "Debt / equity",
};

function describeWatchHint(hint: Record<string, unknown>) {
  if (hint.kind === "price_move_pct" && typeof hint.threshold === "number") {
    return `Price discipline if the stock moves ${hint.threshold}% or more.`;
  }
  if (
    hint.kind === "metric_threshold" &&
    typeof hint.metric === "string" &&
    typeof hint.operator === "string" &&
    typeof hint.threshold === "number"
  ) {
    const label = METRIC_LABELS[hint.metric] ?? hint.metric.replaceAll("_", " ");
    return `${label} stays ${hint.operator} ${hint.threshold}.`;
  }
  return null;
}

function isRecentEvent(dateString: string, days: number) {
  const ageMs = Date.now() - new Date(dateString).getTime();
  return ageMs >= 0 && ageMs <= days * 24 * 60 * 60 * 1000;
}

// ── Status dot colour ────────────────────────────────────────────────────────

const STATUS_DOT: Record<string, string> = {
  intact: "bg-emerald-500",
  needs_review: "bg-orange-500",
  stale: "bg-amber-400",
  no_thesis: "bg-red-500",
  low_signal: "bg-border",
};

// ── Page ─────────────────────────────────────────────────────────────────────

export default function PositionDetailPage() {
  const { ticker } = useParams<{ ticker: string }>();
  const [activeTab, setActiveTab] = useState<TabId>("thesis");
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
  const [reviewingEventId, setReviewingEventId] = useState<string | null>(null);
  const [convictionLog, setConvictionLog] = useState<ConvictionLogResponse | null>(null);
  const [convictionLogLoading, setConvictionLogLoading] = useState(false);
  const [noteSaving, setNoteSaving] = useState(false);
  const [upcomingEarnings, setUpcomingEarnings] = useState<UpcomingEarnings | null>(null);
  const [loading, setLoading] = useState(true);
  const [healthCheck, setHealthCheck] = useState<HealthCheckResult | null>(null);
  const [healthCheckLoading, setHealthCheckLoading] = useState(false);
  const [showCounterThesis, setShowCounterThesis] = useState(false);
  const [showAnalysis, setShowAnalysis] = useState(false);
  const [showPositionDetails, setShowPositionDetails] = useState(false);

  const holding = holdings.find((h) => h.ticker === ticker);
  const activeThesis = theses.find((t) => t.status === "active" || t.status === "draft" || t.status === "needs_review");

  useEffect(() => {
    async function load() {
      try {
        const h = await api.get<Holding[]>("/api/portfolio/holdings");
        setHoldings(h);
        const match = h.find((x) => x.ticker === ticker);
        if (match) {
          const [t, e, log, earnings] = await Promise.all([
            api.get<Thesis[]>(`/api/theses/holding/${match.id}`),
            api.get<MonitoringEvent[]>(`/api/monitoring/holdings/${match.id}/events`),
            api.get<ConvictionLogResponse>(`/api/portfolio/holdings/${match.id}/conviction-log`).catch(() => null),
            api.get<UpcomingEarnings[]>("/api/portfolio/upcoming-earnings").catch(() => []),
          ]);
          setTheses(t);
          setEvents(e);
          setConvictionLog(log);
          setUpcomingEarnings(earnings.find((item) => item.holding_id === match.id) ?? null);
          const latestThesis = t.find((item) => item.status === "active" || item.status === "draft" || item.status === "needs_review");
          if (latestThesis) {
            setDecompositionLoading(true);
            try {
              const envelope = await api.get<ThesisDecompositionEnvelope>(`/api/theses/${latestThesis.id}/decomposition`);
              setDecompositionEnvelope(envelope);
            } catch (error: unknown) {
              const message = getErrorMessage(error, "Failed to load decomposition");
              if (message.includes("Decomposition not found")) {
                setDecompositionEnvelope(null);
              } else {
                setDecompositionEnvelope({ status: "failed", message, decomposition: null });
              }
            } finally {
              setDecompositionLoading(false);
            }
          } else {
            setDecompositionEnvelope(null);
          }
          // Auto-switch to monitoring if there are unreviewed events
          if (e.some((ev) => !ev.review_action)) {
            setActiveTab("monitoring");
          }
        }
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [ticker]);

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
    what_would_change_my_mind: string | null;
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
            toast.message("Updated the existing thesis for this holding.");
          } else {
            throw error;
          }
        }
      }
      setDecompositionEnvelope(null);
      setEditing(false);
      if (savedThesisId) {
        runHealthCheck(savedThesisId);
        setShowCounterThesis(true);
        setShowAnalysis(true);
      }
      await refreshConvictionLog();
    } catch (err) {
      console.error(err);
      toast.error(getErrorMessage(err, "Failed to save thesis"));
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
    try {
      setDecompositionSaving(true);
      const envelope = await api.post<ThesisDecompositionEnvelope>(`/api/theses/${activeThesis.id}/decomposition/confirm`, payload);
      setDecompositionEnvelope(envelope);
      await refreshCurrentThesis();
      await refreshConvictionLog();
    } catch (error) {
      console.error(error);
    } finally {
      setDecompositionSaving(false);
    }
  };

  const handleReviewEvent = async (
    event: MonitoringEvent,
    action: "reaffirmed" | "ignored" | "lowered_confidence" | "invalidated" | "not_relevant",
    notes?: string,
  ) => {
    try {
      setReviewingEventId(event.id);
      const result = await api.post<MonitoringEventReviewResponse>(`/api/monitoring/events/${event.id}/review`, {
        action,
        notes: notes?.trim() ? notes.trim() : undefined,
      });
      setTheses((current) => current.map((thesis) => (thesis.id === result.thesis.id ? result.thesis : thesis)));
      await Promise.all([refreshEvents(), refreshConvictionLog()]);
      const ageText = result.reason_age_days != null ? ` Reason age: ${result.reason_age_days} days.` : "";
      toast.success(`Logged. Reason is now ${result.thesis.status.replace("_", " ")}.${ageText}`);
    } catch (error) {
      console.error(error);
      toast.error("Failed to save review");
    } finally {
      setReviewingEventId(null);
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

  // ── Loading ──────────────────────────────────────────────────────────────

  if (loading) return (
    <div className="flex items-center justify-center min-h-[calc(100vh-53px)]">
      <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground animate-pulse">Loading…</p>
    </div>
  );

  if (!holding) return (
    <div className="max-w-4xl mx-auto px-8 py-8">
      <p className="text-sm text-muted-foreground">Holding not found for ticker {ticker}</p>
    </div>
  );

  // ── Derived state ────────────────────────────────────────────────────────

  const cost = holding.quantity * holding.average_cost_basis;
  const value = holding.current_value || 0;
  const pnl = value - cost;
  const pnlPct = cost > 0 ? ((pnl / cost) * 100).toFixed(1) : "0.0";
  const thesisInsights = getThesisInsights(activeThesis, events);
  const latestEvent = events[0];
  const recentEarningsEvent =
    events.find(
      (e) => ["earnings_surprise", "earnings_call_transcript"].includes(e.event_type) && !e.review_action && isRecentEvent(e.created_at, 3),
    ) ?? null;
  const hasSignals = Boolean(decompositionEnvelope?.decomposition);
  const hasActiveSignals =
    decompositionEnvelope?.decomposition?.claims.some((claim) =>
      claim.entities.some((entity) => entity.signals.some((signal) => signal.active)),
    ) ?? false;
  const watchHints = Array.isArray(activeThesis?.interpretation?.watch_hints)
    ? activeThesis.interpretation.watch_hints.filter((hint): hint is Record<string, unknown> => typeof hint === "object" && hint !== null)
    : [];
  const earningsWatchList = watchHints.map((h) => describeWatchHint(h)).filter((h): h is string => Boolean(h)).slice(0, 3);
  const unreviewedEvents = events.filter((e) => !e.review_action).length;
  const invalidatedTheses = theses.filter((t) => t.status === "invalidated");

  const tabs: { id: TabId; label: string; badge?: number | string }[] = [
    { id: "thesis", label: "Thesis" },
    { id: "monitoring", label: "Monitoring", badge: unreviewedEvents > 0 ? unreviewedEvents : undefined },
    { id: "history", label: "History", badge: convictionLog?.entries.length ?? undefined },
  ];

  const steps = [
    { done: !!activeThesis, label: "Thesis" },
    { done: hasActiveSignals, partial: hasSignals && !hasActiveSignals, label: "Signals" },
    { done: !!(latestEvent && latestEvent.review_action), partial: !!(latestEvent && !latestEvent.review_action), label: "Review" },
  ];

  const lastReviewedEvent = events.filter((e) => e.review_action).sort((a, b) =>
    new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  )[0];

  // ── Render ───────────────────────────────────────────────────────────────

  return (
    <div className="min-h-[calc(100vh-53px)]">

      {/* ── Sticky header ────────────────────────────────────────────────── */}
      <div className="sticky top-[52px] z-20 bg-background border-b border-border/60">
        <div className="max-w-5xl mx-auto px-6 lg:px-10">

          {/* Nav row */}
          <div className="flex items-center justify-between pt-4 pb-2">
            <Link
              href="/dashboard"
              className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground hover:text-primary transition-colors"
            >
              ← Portfolio
            </Link>
            <CheckNowButton
              holdingId={holding.id}
              ticker={holding.ticker}
              currency={holding.currency}
              onComplete={async () => { await refreshEvents(); await refreshCurrentThesis(); }}
            />
          </div>

          {/* Identity + value row */}
          <div className="flex items-end justify-between gap-6 pb-3">
            <div>
              <h1 className="font-display italic text-[3.5rem] leading-none text-primary tracking-tight">
                {cleanTicker(holding.ticker)}
              </h1>
              {holding.name && holding.name !== holding.ticker && (
                <p className="font-sans text-[13px] text-muted-foreground mt-1 leading-none">
                  {holding.name}
                </p>
              )}
            </div>
            <div className="text-right shrink-0 pb-0.5">
              <p className="font-mono text-[1.6rem] tabular-nums text-foreground leading-tight">
                {formatCurrency(value)}
              </p>
              <p className={`font-mono text-[13px] tabular-nums mt-0.5 ${pnl >= 0 ? "text-emerald-700" : "text-red-600"}`}>
                {pnl >= 0 ? "+" : ""}{formatCurrency(pnl)}
                <span className="opacity-60 ml-1.5">({pnl >= 0 ? "+" : ""}{pnlPct}%)</span>
              </p>
            </div>
          </div>

          {/* Status ribbon */}
          <div className="flex items-center gap-4 pb-3">
            {/* Pulse dot + label */}
            <div className="flex items-center gap-2">
              <span className={`h-1.5 w-1.5 rounded-full ${STATUS_DOT[activeThesis?.status ?? "no_thesis"] ?? "bg-border"}`} />
              <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                {thesisInsights.qualityLabel}
              </span>
            </div>
            {activeThesis && (
              <>
                <span className="text-border text-[10px]">·</span>
                <span className="font-mono text-[10px] text-muted-foreground/60">
                  thesis {ageInDays(activeThesis.updated_at)}d old
                </span>
              </>
            )}
            {/* Progress indicators */}
            <div className="flex items-center gap-3 ml-auto">
              {steps.map((step, i) => (
                <div key={step.label} className="flex items-center gap-2">
                  {i > 0 && <span className="text-border text-[10px]">·</span>}
                  <span className={`font-mono text-[9px] uppercase tracking-[0.15em] ${
                    step.done ? "text-emerald-600" : step.partial ? "text-amber-600" : "text-muted-foreground/40"
                  }`}>
                    {step.done ? "●" : step.partial ? "◐" : "○"} {step.label}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Tab strip */}
          <div className="flex gap-1 -mx-1">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className="relative pb-3 px-3 font-mono text-[10px] uppercase tracking-[0.2em] transition-colors flex items-center gap-2"
                style={{ color: activeTab === tab.id ? "var(--primary)" : "var(--muted-foreground)" }}
              >
                {tab.label}
                {tab.badge !== undefined && (
                  <span className={`inline-flex items-center justify-center h-4 min-w-4 px-1 rounded-sm font-mono text-[8px] tabular-nums ${
                    tab.id === "monitoring" && unreviewedEvents > 0
                      ? "bg-primary/10 text-primary"
                      : "text-muted-foreground/60"
                  }`}>
                    {tab.badge}
                  </span>
                )}
                {activeTab === tab.id && (
                  <motion.div
                    layoutId="tab-indicator"
                    className="absolute bottom-0 left-0 right-0 h-px bg-primary"
                    transition={{ type: "spring", stiffness: 400, damping: 35 }}
                  />
                )}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* ── Contextual banners ───────────────────────────────────────────── */}
      <div className="max-w-5xl mx-auto px-6 lg:px-10">

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
                Tighten the thesis so the app knows what evidence should matter the morning after.
              </p>
            )}
          </motion.div>
        )}

        {activeThesis && recentEarningsEvent && (
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
                {recentEarningsEvent.ai_analysis || recentEarningsEvent.evidence_summary || recentEarningsEvent.summary}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              {[
                { action: "reaffirmed" as const, label: "Thesis holds", cls: "border-emerald-500/30 text-emerald-700 hover:bg-emerald-500/8" },
                { action: "lowered_confidence" as const, label: "Lower confidence", cls: "border-amber-500/30 text-amber-700 hover:bg-amber-500/8" },
                { action: "invalidated" as const, label: "Thesis broken", cls: "border-red-500/30 text-red-600 hover:bg-red-500/8" },
              ].map(({ action, label, cls }) => (
                <button
                  key={action}
                  disabled={reviewingEventId === recentEarningsEvent.id}
                  onClick={() => void handleReviewEvent(recentEarningsEvent, action)}
                  className={`font-mono text-[10px] uppercase tracking-[0.15em] border px-4 py-2 transition-colors disabled:opacity-40 ${cls}`}
                >
                  {label}
                </button>
              ))}
              <button
                onClick={() => { setEditing(true); setActiveTab("thesis"); }}
                className="font-mono text-[10px] uppercase tracking-[0.15em] border border-border text-muted-foreground hover:text-foreground px-4 py-2 transition-colors"
              >
                Update thesis
              </button>
            </div>
          </motion.div>
        )}
      </div>

      {/* ── Tab content ─────────────────────────────────────────────────── */}
      <div className="max-w-5xl mx-auto px-6 lg:px-10">
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
                {(thesisInsights.canReaffirm || !activeThesis) && !editing && (
                  <div className="border-l-2 border-primary/30 pl-4 py-1 flex items-start justify-between gap-4">
                    <p className="font-sans text-sm text-foreground/80 leading-relaxed max-w-xl">
                      {thesisInsights.nextStep}
                    </p>
                    <div className="flex gap-2 shrink-0">
                      {!activeThesis && (
                        <button
                          onClick={() => setEditing(true)}
                          className="font-mono text-[10px] uppercase tracking-[0.15em] bg-primary text-primary-foreground px-4 py-2 hover:bg-primary/90 transition-colors"
                        >
                          Start thesis
                        </button>
                      )}
                      {activeThesis && thesisInsights.canReaffirm && (
                        <button
                          onClick={handleReaffirm}
                          disabled={reaffirming}
                          className="font-mono text-[10px] uppercase tracking-[0.15em] border border-primary/40 text-primary px-4 py-2 hover:border-primary transition-colors disabled:opacity-40"
                        >
                          {reaffirming ? "Reaffirming…" : "Reaffirm thesis"}
                        </button>
                      )}
                    </div>
                  </div>
                )}

                {/* Editor */}
                {editing && (
                  <ThesisEditor
                    thesis={activeThesis ?? null}
                    onSave={handleSave}
                    onAssist={handleAssist}
                    onCancel={() => setEditing(false)}
                  />
                )}

                {/* Thesis card */}
                {activeThesis && !editing && (
                  <ThesisCard
                    thesis={activeThesis}
                    decomposition={decompositionEnvelope?.decomposition ?? null}
                    onEdit={() => setEditing(true)}
                    onInvalidate={() => setInvalidateOpen(true)}
                  />
                )}

                {/* No thesis empty state */}
                {!activeThesis && !editing && (
                  <div className="py-16 text-center space-y-4">
                    <p className="font-display italic text-2xl text-foreground/50">
                      No thesis written yet.
                    </p>
                    <p className="font-sans text-sm text-muted-foreground max-w-sm mx-auto leading-relaxed">
                      Start with the reason this position exists, what has to stay true, and what would make you rethink it.
                    </p>
                    <button
                      onClick={() => setEditing(true)}
                      className="font-mono text-[10px] uppercase tracking-[0.2em] border border-primary/40 text-primary px-5 py-2.5 hover:border-primary transition-colors"
                    >
                      Write thesis
                    </button>
                  </div>
                )}

                {/* Analysis (health check + counter thesis) */}
                {activeThesis && (healthCheck || healthCheckLoading || showCounterThesis) && (
                  <div className="space-y-4 border-t border-border/40 pt-6">
                    <button
                      onClick={() => setShowAnalysis((s) => !s)}
                      className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground hover:text-foreground transition-colors"
                    >
                      {showAnalysis ? "▲" : "▼"} Analysis
                    </button>
                    {showAnalysis && (
                      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-4">
                        {(healthCheck || healthCheckLoading) && (
                          <ThesisHealthCheck result={healthCheck} loading={healthCheckLoading} />
                        )}
                        {showCounterThesis && <CounterThesisCard thesisId={activeThesis.id} />}
                      </motion.div>
                    )}
                  </div>
                )}

                {/* Position metrics */}
                <div className="border-t border-border/40 pt-5">
                  <button
                    onClick={() => setShowPositionDetails((s) => !s)}
                    className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground hover:text-foreground transition-colors"
                  >
                    {showPositionDetails ? "▲" : "▼"} Position details
                  </button>
                  {showPositionDetails && (
                    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-4">
                      {[
                        { label: "Shares", value: String(holding.quantity) },
                        { label: "Avg cost", value: formatCurrency(holding.average_cost_basis) },
                        { label: "Current value", value: formatCurrency(value) },
                        { label: "P&L", value: `${pnl >= 0 ? "+" : ""}${formatCurrency(pnl)}`, colored: true },
                      ].map(({ label, value: v, colored }) => (
                        <div key={label} className="border border-border/60 bg-card px-4 py-3">
                          <p className="font-mono text-[9px] uppercase tracking-[0.2em] text-muted-foreground">{label}</p>
                          <p className={`font-mono text-lg tabular-nums mt-1.5 ${colored ? (pnl >= 0 ? "text-emerald-700" : "text-red-600") : "text-foreground"}`}>
                            {v}
                          </p>
                        </div>
                      ))}
                    </motion.div>
                  )}
                </div>
              </>
            )}

            {/* ─── MONITORING TAB ──────────────────────────────────────── */}
            {activeTab === "monitoring" && (
              <div className="space-y-10">

                {/* No thesis guard */}
                {!activeThesis ? (
                  <div className="py-16 text-center space-y-4">
                    <p className="font-display italic text-2xl text-foreground/50">
                      Nothing to watch yet.
                    </p>
                    <p className="font-sans text-sm text-muted-foreground max-w-xs mx-auto leading-relaxed">
                      Write a thesis first — monitoring needs an explicit belief to test against.
                    </p>
                    <button
                      onClick={() => { setEditing(true); setActiveTab("thesis"); }}
                      className="font-mono text-[10px] uppercase tracking-[0.2em] border border-primary/40 text-primary px-5 py-2.5 hover:border-primary transition-colors"
                    >
                      Go to thesis →
                    </button>
                  </div>
                ) : (
                  <>
                    {/* ── DECISION SECTION ────────────────────────────── */}
                    <section>
                      {unreviewedEvents > 0 ? (
                        <div className="space-y-5">
                          {/* Decisions pending header */}
                          <div className="flex items-baseline justify-between gap-4">
                            <div>
                              <p className="font-mono text-[9px] uppercase tracking-[0.3em] text-muted-foreground mb-1">
                                Decisions pending
                              </p>
                              <p className="font-display italic text-[1.6rem] leading-tight text-foreground">
                                {unreviewedEvents === 1
                                  ? "One signal needs your verdict."
                                  : `${unreviewedEvents} signals need your verdict.`}
                              </p>
                            </div>
                            <span className="font-mono text-[10px] text-muted-foreground/50 shrink-0 self-end pb-0.5">
                              drag to decide
                            </span>
                          </div>

                          {/* Card stack */}
                          <EventReviewStack
                            events={events.filter((e) => !e.review_action)}
                            onReview={handleReviewEvent}
                            reviewingEventId={reviewingEventId}
                          />
                        </div>
                      ) : (
                        /* Position clear */
                        <div className="flex items-start gap-5 py-6 border-l-[3px] border-emerald-500/40 pl-6">
                          <div className="space-y-1">
                            <p className="font-display italic text-[1.6rem] leading-tight text-foreground">
                              Position clear.
                            </p>
                            <p className="font-sans text-sm text-muted-foreground leading-relaxed">
                              {events.length > 0
                                ? `All ${events.length} event${events.length !== 1 ? "s" : ""} reviewed.${lastReviewedEvent ? ` Last reviewed ${ageInDays(lastReviewedEvent.created_at)}d ago.` : ""} The thesis stands until something changes.`
                                : "No material changes flagged since monitoring started."}
                            </p>
                          </div>
                        </div>
                      )}
                    </section>

                    {/* ── SIGNALS SECTION ─────────────────────────────── */}
                    <section className="border-t border-border/40 pt-8 space-y-4">
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="font-mono text-[9px] uppercase tracking-[0.3em] text-muted-foreground mb-0.5">
                            Watching for
                          </p>
                          <p className="font-sans text-xs text-muted-foreground/70">
                            Signals derived from your thesis
                          </p>
                        </div>
                        {!hasSignals && !decompositionLoading && (
                          <button
                            onClick={handleGenerateDecomposition}
                            className="font-mono text-[10px] uppercase tracking-[0.15em] border border-primary/40 text-primary px-4 py-2 hover:border-primary transition-colors"
                          >
                            Generate signals
                          </button>
                        )}
                      </div>

                      <ThesisDecompositionReview
                        key={`${decompositionEnvelope?.decomposition?.id ?? "empty"}:${decompositionEnvelope?.status ?? "none"}`}
                        envelope={decompositionEnvelope}
                        loading={decompositionLoading}
                        saving={decompositionSaving}
                        onGenerate={handleGenerateDecomposition}
                        onConfirm={handleConfirmDecomposition}
                      />
                    </section>

                    {/* ── EVIDENCE SECTION ────────────────────────────── */}
                    {events.some((e) => e.review_action) && (
                      <section className="border-t border-border/40 pt-8 space-y-4">
                        <div>
                          <p className="font-mono text-[9px] uppercase tracking-[0.3em] text-muted-foreground mb-0.5">
                            Evidence on file
                          </p>
                          <p className="font-sans text-xs text-muted-foreground/70">
                            Reviewed events and your verdicts
                          </p>
                        </div>
                        <EventTimeline
                          events={events.filter((e) => e.review_action)}
                          reviewingEventId={reviewingEventId}
                        />
                      </section>
                    )}

                    {/* No events at all */}
                    {events.length === 0 && !decompositionLoading && (
                      <p className="font-sans text-sm text-muted-foreground/60 italic">
                        Monitoring is active. Events will appear here as they are detected.
                      </p>
                    )}
                  </>
                )}
              </div>
            )}

            {/* ─── HISTORY TAB ─────────────────────────────────────────── */}
            {activeTab === "history" && (
              <>
                <ConvictionLog
                  data={convictionLog}
                  loading={convictionLogLoading}
                  saving={noteSaving}
                  onAddNote={activeThesis ? handleAddManualNote : undefined}
                />

                {invalidatedTheses.length > 0 && (
                  <div className="border-t border-border/40 pt-6 space-y-3">
                    <p className="font-mono text-[9px] uppercase tracking-[0.3em] text-muted-foreground">
                      Previous theses
                    </p>
                    {invalidatedTheses.map((t) => (
                      <div key={t.id} className="border-l-2 border-border/60 pl-4 py-3 space-y-1.5">
                        <p className="font-sans text-sm text-foreground/70 leading-relaxed italic">
                          &ldquo;{t.why_own_it}&rdquo;
                        </p>
                        {t.invalidation_reason && (
                          <p className="font-sans text-xs text-muted-foreground">
                            Closed: {t.invalidation_reason}
                          </p>
                        )}
                        <p className="font-mono text-[9px] text-muted-foreground/50">
                          {formatDate(t.updated_at)}
                        </p>
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}

          </motion.div>
        </AnimatePresence>
      </div>

      {/* ── Invalidate dialog ────────────────────────────────────────────── */}
      <Dialog open={invalidateOpen} onOpenChange={setInvalidateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="font-display italic">Invalidate thesis</DialogTitle>
          </DialogHeader>
          <Textarea
            placeholder="Why is this thesis no longer valid?"
            value={invalidateReason}
            onChange={(e) => setInvalidateReason(e.target.value)}
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setInvalidateOpen(false)}>Cancel</Button>
            <Button variant="destructive" onClick={handleInvalidate}>Invalidate</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
