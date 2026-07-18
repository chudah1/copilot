"use client";

import { formatDate } from "@/lib/utils";
import type {
  MonitoringEvent,
  ThesisDecomposition,
  ThesisDecompositionClaim,
  ThesisDecompositionSignal,
  ThesisHealthSnapshot,
} from "@/types";

type EffectiveVerdict = "supports" | "threatens" | "neutral" | "ignored";

interface SignalWithEvents {
  signal: ThesisDecompositionSignal;
  entityName: string;
  events: MonitoringEvent[];
}

type ClaimHealth = "Supporting" | "Mixed" | "Threatened" | "Watching";

const CLAIM_TYPE_LABELS: Record<string, string> = {
  must_remain_true: "Must hold",
  what_would_change_my_mind: "Exit trigger",
  why_own_it: "Bull case",
  thesis: "Core belief",
};

const VERDICT_DOT_CLASS: Record<EffectiveVerdict, string> = {
  supports: "bg-emerald-600",
  threatens: "bg-red-600",
  neutral: "bg-muted-foreground/50",
  ignored: "bg-border",
};

const REVIEW_TEXT_CLASS: Record<string, string> = {
  reaffirmed: "text-emerald-700",
  ignored: "text-muted-foreground",
  not_relevant: "text-muted-foreground",
  lowered_confidence: "text-amber-700",
  invalidated: "text-red-600",
};

const CLAIM_HEALTH_CLASS: Record<ClaimHealth, string> = {
  Supporting: "border-emerald-500/20 bg-emerald-500/10 text-emerald-700",
  Mixed: "border-amber-500/20 bg-amber-500/10 text-amber-700",
  Threatened: "border-red-500/20 bg-red-500/10 text-red-600",
  Watching: "border-border bg-muted/40 text-muted-foreground",
};

function effectiveVerdict(event: MonitoringEvent): EffectiveVerdict {
  if (event.review_action === "not_relevant" || event.review_action === "ignored") return "ignored";
  if (event.review_action === "reaffirmed") return "supports";
  if (event.review_action === "invalidated" || event.review_action === "lowered_confidence") return "threatens";
  return (event.verdict as EffectiveVerdict) ?? "neutral";
}

function claimHealth(signals: SignalWithEvents[]): ClaimHealth {
  const verdicts = signals
    .flatMap((signal) => signal.events)
    .map(effectiveVerdict)
    .filter((verdict) => verdict !== "ignored");

  if (verdicts.length === 0) return "Watching";
  const threats = verdicts.filter((verdict) => verdict === "threatens").length;
  const supports = verdicts.filter((verdict) => verdict === "supports").length;
  if (threats > 0 && threats >= supports) return "Threatened";
  if (supports > 0 && threats === 0) return "Supporting";
  return "Mixed";
}

function HealthSparkline({ snapshots }: { snapshots: ThesisHealthSnapshot[] }) {
  if (snapshots.length < 2) return null;

  const width = 220;
  const height = 44;
  const scores = snapshots.map((snapshot) => snapshot.score);
  const minScore = Math.min(...scores);
  const maxScore = Math.max(...scores);
  const range = maxScore - minScore || 1;
  const latest = snapshots[snapshots.length - 1];
  const toneClass =
    latest.label === "Healthy"
      ? "text-emerald-700"
      : latest.label === "At Risk"
        ? "text-amber-700"
        : "text-red-600";
  const stroke =
    latest.label === "Healthy"
      ? "#15803d"
      : latest.label === "At Risk"
        ? "#b45309"
        : "#dc2626";

  const points = scores.map((score, index) => {
    const x = (index / (scores.length - 1)) * width;
    const y = height - ((score - minScore) / range) * (height - 8) - 4;
    return `${x},${y}`;
  });

  const latestX = width;
  const latestY = height - ((scores[scores.length - 1] - minScore) / range) * (height - 8) - 4;

  return (
    <div className="product-panel p-5 sm:p-6">
      <div className="grid gap-4 lg:grid-cols-[minmax(0,12rem)_minmax(0,1fr)_auto] lg:items-center">
        <div>
          <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
            Thesis health
          </p>
          <div className="mt-2 flex items-baseline gap-2">
            <span className={`font-display text-[2rem] italic leading-none ${toneClass}`}>
              {latest.score}
            </span>
            <span className={`font-mono text-[10px] uppercase tracking-[0.14em] ${toneClass}`}>
              {latest.label}
            </span>
          </div>
        </div>

        <svg width={width} height={height} className="w-full max-w-[220px] lg:max-w-none">
          <polyline
            points={points.join(" ")}
            fill="none"
            stroke={stroke}
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            opacity="0.75"
          />
          <circle cx={latestX} cy={latestY} r="3" fill={stroke} />
        </svg>

        <div className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
          {snapshots.length} checks
        </div>
      </div>
    </div>
  );
}

function SignalRow({ signalWithEvents }: { signalWithEvents: SignalWithEvents }) {
  const { signal, entityName, events } = signalWithEvents;
  const countedEvents = events.filter((event) => effectiveVerdict(event) !== "ignored");
  const latestEvent = countedEvents[0] ?? events[0] ?? null;
  const additionalCheckCount = Math.max(0, countedEvents.length - 1);
  const verdict = latestEvent ? effectiveVerdict(latestEvent) : "neutral";
  const label = signal.signal_label ?? signal.signal_type.replaceAll("_", " ");

  return (
    <div className="flex items-start gap-3 border-b border-border/30 py-3 last:border-b-0">
      <span
        title={verdict}
        className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${VERDICT_DOT_CLASS[latestEvent ? verdict : "neutral"]}`}
      />

      <div className="min-w-0 flex-1 space-y-1">
        <div className="flex items-center gap-2 flex-wrap">
          <p className="font-sans text-sm leading-tight text-foreground">
            {label}
          </p>
          {entityName && (
            <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground/70">
              {entityName}
            </span>
          )}
        </div>

        {latestEvent ? (
          <>
            <p className="font-sans text-xs leading-relaxed text-foreground/80">
              {latestEvent.title}
            </p>
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-mono text-[10px] text-muted-foreground/70">
                {formatDate(latestEvent.created_at)}
              </span>
              {latestEvent.review_action && (
                <span
                  className={`font-mono text-[10px] uppercase tracking-[0.12em] ${
                    REVIEW_TEXT_CLASS[latestEvent.review_action] ?? "text-muted-foreground"
                  }`}
                >
                  {latestEvent.review_action.replaceAll("_", " ")}
                </span>
              )}
            </div>
          </>
        ) : (
          <p className="font-sans text-xs italic leading-relaxed text-muted-foreground">
            No evidence yet.
          </p>
        )}
      </div>

      {additionalCheckCount > 0 && (
        <span className="shrink-0 pt-1 font-mono text-[10px] text-muted-foreground/70">
          {additionalCheckCount} more {additionalCheckCount === 1 ? "check" : "checks"}
        </span>
      )}
    </div>
  );
}

function ClaimCard({
  claim,
  signals,
}: {
  claim: ThesisDecompositionClaim;
  signals: SignalWithEvents[];
}) {
  const health = claimHealth(signals);
  const activeSignals = signals.filter(
    (signal) => signal.signal.active || signal.signal.user_confirmed === true,
  );

  return (
    <div className="product-panel overflow-hidden">
      <div className="border-b border-border/40 px-5 py-4 sm:px-6">
        <div className="flex items-start gap-3">
          <span
            className={`inline-flex shrink-0 items-center border px-2 py-0.5 font-mono text-[10px] uppercase tracking-[0.12em] ${CLAIM_HEALTH_CLASS[health]}`}
          >
            {health}
          </span>
          <div className="min-w-0 flex-1 space-y-2">
            {claim.claim_type && (
              <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                {CLAIM_TYPE_LABELS[claim.claim_type] ?? claim.claim_type.replaceAll("_", " ")}
              </p>
            )}
            <p className="font-display text-[1.15rem] italic leading-relaxed text-foreground">
              {claim.claim_text}
            </p>
          </div>
        </div>
      </div>

      <div className="px-5 py-4 sm:px-6">
        {activeSignals.length === 0 ? (
          <p className="font-sans text-sm italic leading-relaxed text-muted-foreground">
            No active signals for this claim.
          </p>
        ) : (
          activeSignals.map((signalWithEvents) => (
            <SignalRow key={signalWithEvents.signal.id} signalWithEvents={signalWithEvents} />
          ))
        )}
      </div>
    </div>
  );
}

interface ThesisDiffViewProps {
  decomposition: ThesisDecomposition | null;
  monitoringEvents: MonitoringEvent[];
  healthSnapshots: ThesisHealthSnapshot[];
}

export function ThesisDiffView({
  decomposition,
  monitoringEvents,
  healthSnapshots,
}: ThesisDiffViewProps) {
  if (!decomposition || decomposition.claims.length === 0) {
    return (
      <div className="product-panel p-5 sm:p-6">
        <p className="font-sans text-sm italic leading-relaxed text-muted-foreground">
          No signal map yet. Generate signals first.
        </p>
      </div>
    );
  }

  const eventsBySignal = new Map<string, MonitoringEvent[]>();
  for (const event of monitoringEvents) {
    if (!event.signal_id) continue;
    const entries = eventsBySignal.get(event.signal_id) ?? [];
    entries.push(event);
    eventsBySignal.set(event.signal_id, entries);
  }

  for (const [, entries] of eventsBySignal) {
    entries.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
  }

  return (
    <div className="space-y-4">
      <HealthSparkline snapshots={healthSnapshots} />

      {decomposition.claims
        .slice()
        .sort((a, b) => (a.position ?? 0) - (b.position ?? 0))
        .map((claim) => {
          const signals: SignalWithEvents[] = claim.entities.flatMap((entity) =>
            entity.signals.map((signal) => ({
              signal,
              entityName: entity.entity_name,
              events: eventsBySignal.get(signal.id) ?? [],
            })),
          );

          return <ClaimCard key={claim.id} claim={claim} signals={signals} />;
        })}
    </div>
  );
}
