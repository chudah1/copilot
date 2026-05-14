"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { getErrorMessage } from "@/lib/errors";
import { formatCurrency, formatDate } from "@/lib/utils";
import { ThesisCard } from "@/components/thesis/thesis-card";
import { ThesisDecompositionReview } from "@/components/thesis/thesis-decomposition-review";
import { ThesisEditor } from "@/components/thesis/thesis-editor";
import { EventTimeline } from "@/components/monitoring/event-timeline";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { ThesisHealthCheck } from "@/components/thesis/thesis-health-check";
import { CounterThesisCard } from "@/components/thesis/counter-thesis-card";
import { CheckNowButton } from "@/components/monitoring/check-now-button";
import type {
  ConfirmDecompositionRequest,
  HealthCheckResult,
  Holding,
  MonitoringEvent,
  MonitoringEventReviewResponse,
  Thesis,
  ThesisAssistResponse,
  ThesisDecompositionEnvelope,
} from "@/types";

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
      qualityTone: "bg-red-100 text-red-800",
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
      qualityTone: "bg-orange-100 text-orange-800",
      watchStatus: "Monitoring found something worth revisiting in this thesis.",
      canReaffirm: true,
    };
  }

  if (stale) {
    return {
      nextStep: "This thesis is old. Re-read it and either reaffirm it or tighten the language.",
      qualityLabel: "Stale thesis",
      qualityTone: "bg-amber-100 text-amber-800",
      watchStatus: "Nothing necessarily broke, but this reasoning has not been reviewed in a while.",
      canReaffirm: true,
    };
  }

  if (monitorability === "low") {
    return {
      nextStep: ambiguity || "Tighten the thesis so the app can monitor something more precise than a vague reason.",
      qualityLabel: "Weak monitorability",
      qualityTone: "bg-stone-200 text-stone-800",
      watchStatus: "The current reason is too vague for high-confidence monitoring.",
      canReaffirm: false,
    };
  }

  return {
    nextStep: latestEvent ? latestEvent.ai_analysis || "Monitoring is active. Review the latest event if it still matters." : "The thesis looks healthy. You do not need to do anything unless your view changes.",
    qualityLabel: `${monitorability} monitorability`,
    qualityTone: monitorability === "high" ? "bg-emerald-100 text-emerald-800" : "bg-sky-100 text-sky-800",
    watchStatus: latestEvent ? "Monitoring has context to evaluate new changes against this thesis." : "Monitoring is active and no material thesis change has been flagged yet.",
    canReaffirm: false,
  };
}

export default function PositionDetailPage() {
  const { ticker } = useParams<{ ticker: string }>();
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
  const [loading, setLoading] = useState(true);
  const [healthCheck, setHealthCheck] = useState<HealthCheckResult | null>(null);
  const [healthCheckLoading, setHealthCheckLoading] = useState(false);
  const [showCounterThesis, setShowCounterThesis] = useState(false);
  const [showAdvancedContext, setShowAdvancedContext] = useState(false);

  const holding = holdings.find((h) => h.ticker === ticker);
  const activeThesis = theses.find((t) => t.status === "active" || t.status === "draft" || t.status === "needs_review");

  useEffect(() => {
    async function load() {
      try {
        const h = await api.get<Holding[]>("/api/portfolio/holdings");
        setHoldings(h);
        const match = h.find((x) => x.ticker === ticker);
        if (match) {
          const [t, e] = await Promise.all([
            api.get<Thesis[]>(`/api/theses/holding/${match.id}`),
            api.get<MonitoringEvent[]>(`/api/monitoring/holdings/${match.id}/events`),
          ]);
          setTheses(t);
          setEvents(e);
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
                setDecompositionEnvelope({
                  status: "failed",
                  message,
                  decomposition: null,
                });
              }
            } finally {
              setDecompositionLoading(false);
            }
          } else {
            setDecompositionEnvelope(null);
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

  const handleAssist = async (draftText: string): Promise<ThesisAssistResponse> => {
    if (!holding) {
      throw new Error("Holding not found");
    }
    return api.post<ThesisAssistResponse>("/api/theses/assist", {
      holding_id: holding.id,
      draft_text: draftText,
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
        setTheses(theses.map((t) => (t.id === updated.id ? updated : t)));
        savedThesisId = updated.id;
      } else if (holding) {
        const created = await api.post<Thesis>("/api/theses", { holding_id: holding.id, ...data });
        setTheses([created, ...theses]);
        savedThesisId = created.id;
      }
      setDecompositionEnvelope(null);
      setEditing(false);
      if (savedThesisId) {
        runHealthCheck(savedThesisId);
        setShowCounterThesis(true);
      }
    } catch (err) {
      console.error(err);
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
      setDecompositionEnvelope({
        status: "failed",
        message,
        decomposition: null,
      });
    } finally {
      setDecompositionLoading(false);
    }
  };

  const handleConfirmDecomposition = async (payload: ConfirmDecompositionRequest) => {
    if (!activeThesis) return;
    try {
      setDecompositionSaving(true);
      const envelope = await api.post<ThesisDecompositionEnvelope>(
        `/api/theses/${activeThesis.id}/decomposition/confirm`,
        payload,
      );
      setDecompositionEnvelope(envelope);
      await refreshCurrentThesis();
    } catch (error) {
      console.error(error);
    } finally {
      setDecompositionSaving(false);
    }
  };

  const handleReviewEvent = async (
    event: MonitoringEvent,
    action: "reaffirmed" | "ignored" | "lowered_confidence" | "invalidated",
  ) => {
    try {
      setReviewingEventId(event.id);
      const result = await api.post<MonitoringEventReviewResponse>(`/api/monitoring/events/${event.id}/review`, {
        action,
      });
      setTheses((current) => current.map((thesis) => (thesis.id === result.thesis.id ? result.thesis : thesis)));
      await refreshEvents();
    } catch (error) {
      console.error(error);
    } finally {
      setReviewingEventId(null);
    }
  };

  if (loading) return <p>Loading...</p>;
  if (!holding) return <p>Holding not found for ticker {ticker}</p>;

  const cost = holding.quantity * holding.average_cost_basis;
  const value = holding.current_value || 0;
  const pnl = value - cost;
  const thesisInsights = getThesisInsights(activeThesis, events);
  const latestEvent = events[0];
  const hasSignals = Boolean(decompositionEnvelope?.decomposition);
  const hasActiveSignals =
    decompositionEnvelope?.decomposition?.claims.some((claim) =>
      claim.entities.some((entity) => entity.signals.some((signal) => signal.active)),
    ) ?? false;
  const reviewStateLabel = latestEvent
    ? latestEvent.review_action
      ? `Latest event reviewed: ${latestEvent.review_action.replaceAll("_", " ")}`
      : "Latest event needs a decision"
    : "No recent thesis-breaking events";

  return (
    <div className="space-y-6">
      <Card className="border-0 bg-[linear-gradient(135deg,rgba(19,26,32,0.98),rgba(27,47,60,0.94)_55%,rgba(207,224,231,0.92))] text-white ring-0">
        <CardHeader className="gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <Badge className="bg-white/12 text-white">{holding.ticker}</Badge>
            <Badge className={thesisInsights.qualityTone}>{thesisInsights.qualityLabel}</Badge>
            {latestEvent && <Badge className="bg-white/12 text-white">{latestEvent.severity.replace("_", " ")}</Badge>}
          </div>
          <CardTitle className="text-3xl font-semibold tracking-tight text-white">{holding.name}</CardTitle>
          <CardDescription className="max-w-2xl text-white/80">
            {thesisInsights.watchStatus}
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-[1.2fr_0.8fr]">
          <div className="rounded-2xl border border-white/12 bg-white/8 p-4 backdrop-blur">
            <p className="text-sm text-white/70">Next best action</p>
            <p className="mt-2 text-lg font-medium">{thesisInsights.nextStep}</p>
            <div className="mt-4 flex flex-wrap gap-2">
              {!activeThesis && <Button onClick={() => setEditing(true)}>Start thesis</Button>}
              {activeThesis && (
                <Button onClick={() => setEditing(true)} variant="outline" className="border-white/20 bg-white/10 text-white hover:bg-white/20">
                  Tighten thesis
                </Button>
              )}
              {activeThesis && !hasSignals && !editing && (
                <Button onClick={handleGenerateDecomposition}>
                  {decompositionLoading ? "Generating..." : "Generate signals"}
                </Button>
              )}
              {activeThesis && thesisInsights.canReaffirm && (
                <Button onClick={handleReaffirm} disabled={reaffirming}>
                  {reaffirming ? "Reaffirming..." : "Reaffirm thesis"}
                </Button>
              )}
            </div>
          </div>
          <div className="rounded-2xl border border-white/12 bg-white/8 p-4 backdrop-blur">
            <p className="text-sm text-white/70">Position snapshot</p>
            <div className="mt-3 grid grid-cols-2 gap-3 text-sm">
              <div>
                <p className="text-white/65">Current value</p>
                <p className="mt-1 text-lg font-semibold">{formatCurrency(value, holding.currency)}</p>
              </div>
              <div>
                <p className="text-white/65">P&L</p>
                <p className={`mt-1 text-lg font-semibold ${pnl >= 0 ? "text-emerald-200" : "text-rose-200"}`}>{formatCurrency(pnl, holding.currency)}</p>
              </div>
              <div>
                <p className="text-white/65">Last thesis review</p>
                <p className="mt-1">{activeThesis ? formatDate(activeThesis.updated_at) : "Never"}</p>
              </div>
              <div>
                <p className="text-white/65">Recent events</p>
                <p className="mt-1">{events.length}</p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Core loop</CardTitle>
          <CardDescription>
            Keep the position honest in three steps: state the thesis, confirm what should be monitored, then react when evidence shows up.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-3">
          <div className="rounded-xl border p-4">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Step 1</p>
            <p className="mt-2 font-medium">Write the thesis</p>
            <p className="mt-1 text-sm text-muted-foreground">
              {activeThesis ? "A current thesis exists for this position." : "No thesis yet. Monitoring has nothing to anchor to."}
            </p>
            <Badge className={`mt-3 ${activeThesis ? "bg-emerald-100 text-emerald-800" : "bg-stone-200 text-stone-800"}`}>
              {activeThesis ? "Done" : "Needed"}
            </Badge>
          </div>
          <div className="rounded-xl border p-4">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Step 2</p>
            <p className="mt-2 font-medium">Confirm the signals</p>
            <p className="mt-1 text-sm text-muted-foreground">
              {hasSignals
                ? hasActiveSignals
                  ? "Signals are confirmed and monitoring is anchored to them."
                  : "A decomposition exists, but nothing is actively confirmed yet."
                : "Generate a decomposition so the app can suggest what to watch."}
            </p>
            <Badge className={`mt-3 ${hasActiveSignals ? "bg-emerald-100 text-emerald-800" : hasSignals ? "bg-amber-100 text-amber-800" : "bg-stone-200 text-stone-800"}`}>
              {hasActiveSignals ? "Monitoring ready" : hasSignals ? "Needs confirmation" : "Not started"}
            </Badge>
          </div>
          <div className="rounded-xl border p-4">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Step 3</p>
            <p className="mt-2 font-medium">Review live evidence</p>
            <p className="mt-1 text-sm text-muted-foreground">{reviewStateLabel}</p>
            <Badge className={`mt-3 ${latestEvent && !latestEvent.review_action ? "bg-amber-100 text-amber-800" : "bg-sky-100 text-sky-800"}`}>
              {latestEvent && !latestEvent.review_action ? "Decision needed" : "Up to date"}
            </Badge>
          </div>
        </CardContent>
      </Card>

      {activeThesis && !editing && (
        <ThesisCard thesis={activeThesis} onEdit={() => setEditing(true)} onInvalidate={() => setInvalidateOpen(true)} />
      )}

      {activeThesis && !editing && (
        <ThesisDecompositionReview
          key={`${decompositionEnvelope?.decomposition?.id ?? "empty"}:${decompositionEnvelope?.status ?? "none"}`}
          envelope={decompositionEnvelope}
          loading={decompositionLoading}
          saving={decompositionSaving}
          onGenerate={handleGenerateDecomposition}
          onConfirm={handleConfirmDecomposition}
        />
      )}

      {activeThesis && editing && (
        <ThesisEditor thesis={activeThesis} onSave={handleSave} onAssist={handleAssist} onCancel={() => setEditing(false)} />
      )}

      {!activeThesis && (
        <Card>
          <CardContent className="flex flex-col items-center gap-4 py-8">
            <p className="text-muted-foreground">No current thesis for this position.</p>
            <p className="max-w-md text-center text-sm text-muted-foreground">
              Start with the reason this position exists, what has to stay true, and what would make you rethink it. That is what the monitoring system watches.
            </p>
            <Button onClick={() => setEditing(true)}>
              Start Thesis
            </Button>
          </CardContent>
        </Card>
      )}

      {!activeThesis && editing && (
        <ThesisEditor thesis={null} onSave={handleSave} onAssist={handleAssist} onCancel={() => setEditing(false)} />
      )}

      {activeThesis && holding && (
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-medium text-muted-foreground">Monitoring events</h3>
            <p className="text-xs text-muted-foreground">This is the review layer: when something changes, decide whether the thesis still holds.</p>
          </div>
          <CheckNowButton holdingId={holding.id} onComplete={async () => { await refreshEvents(); await refreshCurrentThesis(); }} />
        </div>
      )}

      <EventTimeline events={events} onReview={handleReviewEvent} reviewingEventId={reviewingEventId} />

      <div className="space-y-3">
        <button
          onClick={() => setShowAdvancedContext((current) => !current)}
          className="text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          {showAdvancedContext ? "Hide" : "Show"} advanced context
        </button>

        {showAdvancedContext && (
          <div className="space-y-4 animate-in fade-in duration-200">
            <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
              <Card>
                <CardHeader className="pb-2"><CardTitle className="text-sm text-muted-foreground">Quantity</CardTitle></CardHeader>
                <CardContent><p className="text-xl font-bold">{holding.quantity}</p></CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2"><CardTitle className="text-sm text-muted-foreground">Avg Cost</CardTitle></CardHeader>
                <CardContent><p className="text-xl font-bold">{formatCurrency(holding.average_cost_basis, holding.currency)}</p></CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2"><CardTitle className="text-sm text-muted-foreground">Current Value</CardTitle></CardHeader>
                <CardContent><p className="text-xl font-bold">{formatCurrency(value, holding.currency)}</p></CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2"><CardTitle className="text-sm text-muted-foreground">P&L</CardTitle></CardHeader>
                <CardContent><p className={`text-xl font-bold ${pnl >= 0 ? "text-green-600" : "text-red-600"}`}>{formatCurrency(pnl, holding.currency)}</p></CardContent>
              </Card>
            </div>

            {activeThesis && (healthCheck || healthCheckLoading) && (
              <ThesisHealthCheck result={healthCheck} loading={healthCheckLoading} />
            )}

            {activeThesis && showCounterThesis && (
              <CounterThesisCard thesisId={activeThesis.id} />
            )}

            {theses.filter((t) => t.status === "invalidated").length > 0 && (
              <Card>
                <CardHeader><CardTitle className="text-base">Thesis history</CardTitle></CardHeader>
                <CardContent className="space-y-2">
                  {theses.filter((t) => t.status === "invalidated").map((t) => (
                    <div key={t.id} className="border-l-2 border-muted pl-4 py-2">
                      <p className="text-sm">{t.why_own_it}</p>
                      <p className="text-xs text-muted-foreground">Invalidated: {t.invalidation_reason}</p>
                    </div>
                  ))}
                </CardContent>
              </Card>
            )}
          </div>
        )}
      </div>

      <Dialog open={invalidateOpen} onOpenChange={setInvalidateOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>Invalidate Thesis</DialogTitle></DialogHeader>
          <Textarea placeholder="Why is this thesis no longer valid?" value={invalidateReason} onChange={(e) => setInvalidateReason(e.target.value)} />
          <DialogFooter>
            <Button variant="outline" onClick={() => setInvalidateOpen(false)}>Cancel</Button>
            <Button variant="destructive" onClick={handleInvalidate}>Invalidate</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
