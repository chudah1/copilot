"use client";

import { formatDate } from "@/lib/utils";
import type {
  MonitoringEvent,
  ThesisDecomposition,
  ThesisDecompositionClaim,
  ThesisDecompositionSignal,
  ThesisHealthSnapshot,
} from "@/types";

// ── Types ─────────────────────────────────────────────────────────────────────

type EffectiveVerdict = "supports" | "threatens" | "neutral" | "ignored";

interface SignalWithEvents {
  signal: ThesisDecompositionSignal;
  entityName: string;
  events: MonitoringEvent[];
}

type ClaimHealth = "Supporting" | "Mixed" | "Threatened" | "Watching";

// ── Verdict helpers ───────────────────────────────────────────────────────────

function effectiveVerdict(event: MonitoringEvent): EffectiveVerdict {
  if (event.review_action === "not_relevant" || event.review_action === "ignored") return "ignored";
  if (event.review_action === "reaffirmed") return "supports";
  if (event.review_action === "invalidated" || event.review_action === "lowered_confidence") return "threatens";
  return (event.verdict as EffectiveVerdict) ?? "neutral";
}

function claimHealth(signals: SignalWithEvents[]): ClaimHealth {
  const verdicts = signals
    .flatMap((s) => s.events)
    .map(effectiveVerdict)
    .filter((v) => v !== "ignored");

  if (verdicts.length === 0) return "Watching";
  const threats = verdicts.filter((v) => v === "threatens").length;
  const supports = verdicts.filter((v) => v === "supports").length;
  if (threats > 0 && threats >= supports) return "Threatened";
  if (supports > 0 && threats === 0) return "Supporting";
  return "Mixed";
}

// ── Verdict dot ───────────────────────────────────────────────────────────────

function VerdictDot({ verdict }: { verdict: EffectiveVerdict }) {
  const map: Record<EffectiveVerdict, { color: string; label: string }> = {
    supports:  { color: "#16a34a", label: "supports" },
    threatens: { color: "#dc2626", label: "threatens" },
    neutral:   { color: "#9ca3af", label: "neutral" },
    ignored:   { color: "#d1d5db", label: "ignored" },
  };
  const { color, label } = map[verdict];
  return (
    <span
      title={label}
      style={{
        display: "inline-block",
        width: 8,
        height: 8,
        borderRadius: "50%",
        background: color,
        flexShrink: 0,
        marginTop: 5,
      }}
    />
  );
}

// ── Health badge ──────────────────────────────────────────────────────────────

function ClaimHealthBadge({ health }: { health: ClaimHealth }) {
  const styles: Record<ClaimHealth, { bg: string; text: string }> = {
    Supporting: { bg: "#dcfce7", text: "#15803d" },
    Mixed:      { bg: "#fef9c3", text: "#854d0e" },
    Threatened: { bg: "#fee2e2", text: "#b91c1c" },
    Watching:   { bg: "#f3f4f6", text: "#6b7280" },
  };
  const { bg, text } = styles[health];
  return (
    <span
      style={{
        padding: "2px 8px",
        borderRadius: 999,
        background: bg,
        color: text,
        fontSize: 10,
        fontWeight: 600,
        letterSpacing: "0.08em",
        textTransform: "uppercase",
        fontFamily: "var(--font-geist-mono), monospace",
        flexShrink: 0,
      }}
    >
      {health}
    </span>
  );
}

// ── Signal row ────────────────────────────────────────────────────────────────

function SignalRow({ sw }: { sw: SignalWithEvents }) {
  const { signal, events } = sw;
  const latest = events[0] ?? null;
  const label = signal.signal_label ?? signal.signal_type.replaceAll("_", " ");
  const verdict = latest ? effectiveVerdict(latest) : "neutral";

  return (
    <div
      style={{
        display: "flex",
        alignItems: "flex-start",
        gap: 10,
        padding: "10px 0",
        borderBottom: "1px solid #f0ede6",
      }}
    >
      <VerdictDot verdict={latest ? verdict : "neutral"} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 8, flexWrap: "wrap" }}>
          <span style={{ fontSize: 13, fontWeight: 500, color: "#15140f" }}>{label}</span>
          {sw.entityName && (
            <span style={{ fontSize: 11, color: "#9ca3af", fontFamily: "var(--font-geist-mono), monospace" }}>
              {sw.entityName}
            </span>
          )}
        </div>

        {latest ? (
          <div style={{ marginTop: 4 }}>
            <p style={{ fontSize: 12, color: "#3a3833", lineHeight: 1.5, margin: 0 }}>
              {latest.title}
            </p>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 3, flexWrap: "wrap" }}>
              <span style={{ fontSize: 11, color: "#9ca3af", fontFamily: "var(--font-geist-mono), monospace" }}>
                {formatDate(latest.created_at)}
              </span>
              {latest.review_action && (
                <span
                  style={{
                    fontSize: 10,
                    fontWeight: 600,
                    letterSpacing: "0.06em",
                    textTransform: "uppercase",
                    color: latest.review_action === "reaffirmed" ? "#15803d"
                      : latest.review_action === "not_relevant" || latest.review_action === "ignored" ? "#9ca3af"
                      : "#b91c1c",
                    fontFamily: "var(--font-geist-mono), monospace",
                  }}
                >
                  you said: {latest.review_action.replace("_", " ")}
                </span>
              )}
            </div>
          </div>
        ) : (
          <p style={{ fontSize: 12, color: "#9ca3af", margin: "4px 0 0", fontStyle: "italic" }}>
            No events yet
          </p>
        )}
      </div>

      {events.length > 1 && (
        <span
          style={{
            fontSize: 11,
            color: "#9ca3af",
            fontFamily: "var(--font-geist-mono), monospace",
            flexShrink: 0,
            paddingTop: 2,
          }}
        >
          +{events.length - 1}
        </span>
      )}
    </div>
  );
}

// ── Claim card ────────────────────────────────────────────────────────────────

function ClaimCard({
  claim,
  signals,
}: {
  claim: ThesisDecompositionClaim;
  signals: SignalWithEvents[];
}) {
  const health = claimHealth(signals);
  const activeSignals = signals.filter(
    (s) => s.signal.active || s.signal.user_confirmed === true
  );

  return (
    <div
      style={{
        background: "#fff",
        border: "1px solid #dcd6c8",
        borderRadius: 14,
        overflow: "hidden",
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: "14px 18px",
          borderBottom: "1px solid #f0ede6",
          display: "flex",
          alignItems: "flex-start",
          gap: 12,
        }}
      >
        <ClaimHealthBadge health={health} />
        <p
          style={{
            fontSize: 14,
            fontWeight: 500,
            lineHeight: 1.45,
            color: "#15140f",
            margin: 0,
            flex: 1,
          }}
        >
          {claim.claim_text}
        </p>
      </div>

      {/* Signals */}
      <div style={{ padding: "0 18px" }}>
        {activeSignals.length === 0 ? (
          <p style={{ fontSize: 12, color: "#9ca3af", padding: "12px 0", margin: 0, fontStyle: "italic" }}>
            No active signals for this claim.
          </p>
        ) : (
          activeSignals.map((sw) => (
            <SignalRow key={sw.signal.id} sw={sw} />
          ))
        )}
      </div>
    </div>
  );
}

// ── Health sparkline ──────────────────────────────────────────────────────────

function HealthSparkline({ snapshots }: { snapshots: ThesisHealthSnapshot[] }) {
  if (snapshots.length < 2) return null;

  const W = 200;
  const H = 40;
  const scores = snapshots.map((s) => s.score);
  const minS = Math.min(...scores);
  const maxS = Math.max(...scores);
  const range = maxS - minS || 1;

  const pts = scores.map((s, i) => {
    const x = (i / (scores.length - 1)) * W;
    const y = H - ((s - minS) / range) * (H - 6) - 3;
    return `${x},${y}`;
  });

  const latest = snapshots[snapshots.length - 1];
  const labelColor = latest.label === "Healthy" ? "#16a34a" : latest.label === "At Risk" ? "#d97706" : "#dc2626";

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 16,
        padding: "12px 18px",
        background: "#faf8f3",
        border: "1px solid #dcd6c8",
        borderRadius: 12,
        marginBottom: 20,
      }}
    >
      <div>
        <div
          style={{
            fontFamily: "var(--font-geist-mono), monospace",
            fontSize: 10,
            letterSpacing: "0.12em",
            textTransform: "uppercase",
            color: "#7a7268",
            marginBottom: 2,
          }}
        >
          Thesis health
        </div>
        <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
          <span style={{ fontSize: 28, fontWeight: 600, letterSpacing: "-0.02em", color: labelColor }}>
            {latest.score}
          </span>
          <span
            style={{
              fontFamily: "var(--font-geist-mono), monospace",
              fontSize: 11,
              fontWeight: 600,
              color: labelColor,
              textTransform: "uppercase",
              letterSpacing: "0.06em",
            }}
          >
            {latest.label}
          </span>
        </div>
      </div>

      <svg width={W} height={H} style={{ flex: 1, maxWidth: W }}>
        <polyline
          points={pts.join(" ")}
          fill="none"
          stroke={labelColor}
          strokeWidth={1.5}
          strokeLinecap="round"
          strokeLinejoin="round"
          opacity={0.7}
        />
        {/* Latest dot */}
        <circle
          cx={(scores.length - 1) / (scores.length - 1) * W}
          cy={H - ((scores[scores.length - 1] - minS) / range) * (H - 6) - 3}
          r={3}
          fill={labelColor}
        />
      </svg>

      <div
        style={{
          fontFamily: "var(--font-geist-mono), monospace",
          fontSize: 10,
          color: "#9ca3af",
          whiteSpace: "nowrap",
        }}
      >
        {snapshots.length} checks
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

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
      <p style={{ fontSize: 13, color: "#9ca3af", fontStyle: "italic", padding: "20px 0" }}>
        No decomposition yet. Generate signals first.
      </p>
    );
  }

  const eventsBySignal = new Map<string, MonitoringEvent[]>();
  const eventsByClaim = new Map<string, MonitoringEvent[]>();
  for (const ev of monitoringEvents) {
    if (ev.signal_id) {
      const arr = eventsBySignal.get(ev.signal_id) ?? [];
      arr.push(ev);
      eventsBySignal.set(ev.signal_id, arr);
    }
    if (ev.claim_id) {
      const arr = eventsByClaim.get(ev.claim_id) ?? [];
      arr.push(ev);
      eventsByClaim.set(ev.claim_id, arr);
    }
  }

  // Sort events newest-first per signal
  for (const [, arr] of eventsBySignal) {
    arr.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
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
            }))
          );
          return (
            <ClaimCard key={claim.id} claim={claim} signals={signals} />
          );
        })}
    </div>
  );
}
