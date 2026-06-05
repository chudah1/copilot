"use client";

import { formatDate } from "@/lib/utils";
import { classifyThesisQuality } from "@/lib/thesis-quality";
import type { Thesis, ThesisDecomposition } from "@/types";

interface Props {
  thesis: Thesis;
  decomposition?: ThesisDecomposition | null;
  investorProfile?: "thesis_driven" | "hearsay_driven" | null;
  onEdit: () => void;
  onInvalidate: () => void;
}

// ── Colour maps ───────────────────────────────────────────────────────────────

const STATUS_DOT: Record<string, string> = {
  draft: "bg-muted-foreground/40",
  active: "bg-emerald-500",
  needs_review: "bg-orange-500",
  invalidated: "bg-red-500",
};

const STATUS_TEXT: Record<string, string> = {
  draft: "text-muted-foreground",
  active: "text-emerald-700",
  needs_review: "text-orange-600",
  invalidated: "text-red-600",
};

const CONFIDENCE_TEXT: Record<string, string> = {
  high: "text-emerald-700",
  medium: "text-amber-700",
  low: "text-red-600",
};

const MONITORABILITY_TEXT: Record<string, string> = {
  high: "text-emerald-700",
  medium: "text-amber-700",
  low: "text-red-600",
};

const QUALITY_TONE: Record<string, string> = {
  strong: "text-emerald-700",
  workable: "text-amber-700",
  weak: "text-red-600",
};

// ── Helpers ───────────────────────────────────────────────────────────────────

const METRIC_LABELS: Record<string, string> = {
  revenue_growth_yoy: "Revenue growth (YoY)",
  earnings_growth_yoy: "Earnings growth (YoY)",
  pe_ratio: "P/E ratio",
  dividend_yield: "Dividend yield",
  gross_margin: "Gross margin",
  operating_margin: "Operating margin",
};

function formatThresholdValue(unit: string | undefined, threshold: number): string {
  if (unit === "pct") {
    const pct = Math.abs(threshold) <= 1 ? threshold * 100 : threshold;
    return `${pct % 1 === 0 ? pct.toFixed(0) : pct.toFixed(1)}%`;
  }
  return String(threshold);
}

function describeWatchHint(hint: Record<string, unknown>): string | null {
  if (hint.kind === "price_move_pct" && typeof hint.threshold === "number") {
    return `Review if price moves ${hint.threshold}% or more.`;
  }
  if (
    hint.kind === "metric_threshold" &&
    typeof hint.metric === "string" &&
    typeof hint.operator === "string" &&
    typeof hint.threshold === "number"
  ) {
    if (hint.threshold === 0) return null;
    const label = typeof hint.label === "string" ? hint.label : (METRIC_LABELS[hint.metric] ?? hint.metric.replaceAll("_", " "));
    const unit = typeof hint.unit === "string" ? hint.unit : undefined;
    return `${label} stays ${hint.operator} ${formatThresholdValue(unit, hint.threshold)}.`;
  }
  return null;
}

function describeSignalCheckLogic(signalType: string, config: Record<string, unknown> | null): string | null {
  const c = config ?? {};
  if (signalType === "price_move") {
    const t = typeof c.threshold_pct === "number" ? c.threshold_pct : null;
    return t != null ? `Flags if the stock moves ${t}% or more.` : "Flags on a sharp price move.";
  }
  if (signalType === "revenue_growth" || signalType === "earnings_growth") {
    const threshold = typeof c.threshold === "number" ? c.threshold : null;
    const operator = typeof c.operator === "string" ? c.operator : ">=";
    const label = signalType === "revenue_growth" ? "revenue growth" : "earnings growth";
    if (threshold == null || (threshold === 0 && operator === ">=")) {
      return `Flags when ${label} turns negative YoY.`;
    }
    const fmt = formatThresholdValue(
      signalType === "revenue_growth" ? "revenue_growth_yoy" : "earnings_growth_yoy",
      threshold,
    );
    if (operator === ">=" || operator === ">") return `Flags when ${label} falls below ${fmt} YoY.`;
    if (operator === "<=" || operator === "<") return `Flags when ${label} rises above ${fmt} YoY.`;
  }
  if (signalType === "guidance_change") return "Watches guidance for meaningful deterioration.";
  if (signalType === "earnings_surprise") return "Watches for a big miss versus expectations.";
  if (signalType === "dividend_change") return "Watches for a dividend cut or payout policy change.";
  return null;
}

function getActiveSignals(decomposition: ThesisDecomposition | null | undefined) {
  if (!decomposition) return [];
  return decomposition.claims.flatMap((claim) =>
    claim.entities.flatMap((entity) =>
      entity.signals
        .filter((s) => s.active || s.user_confirmed === true)
        .map((s) => ({
          id: s.id,
          label: s.signal_label ?? s.signal_type.replaceAll("_", " "),
          rationale: s.rationale,
          entityName: entity.entity_name,
          entityTicker: entity.entity_ticker,
          checkLogic: describeSignalCheckLogic(s.signal_type, s.signal_config_json),
        })),
    ),
  );
}

function getInterpretation(thesis: Thesis) {
  const interp = thesis.interpretation ?? {};
  const labels = Array.isArray(interp.labels)
    ? interp.labels.filter((l): l is string => typeof l === "string" && l.length > 0)
    : [];
  const watchHints = Array.isArray(interp.watch_hints)
    ? interp.watch_hints.filter((h): h is Record<string, unknown> => typeof h === "object" && h !== null)
    : [];
  const monitorability = typeof interp.monitorability === "string" ? interp.monitorability : null;
  const ambiguityNote = typeof interp.ambiguity_note === "string" ? interp.ambiguity_note : "";
  return { labels, watchHints, monitorability, ambiguityNote };
}

// ── Component ─────────────────────────────────────────────────────────────────

export function ThesisCard({ thesis, decomposition, investorProfile, onEdit, onInvalidate }: Props) {
  const { labels, watchHints, ambiguityNote } = getInterpretation(thesis);
  const watchDescriptions = watchHints
    .map(describeWatchHint)
    .filter((d): d is string => Boolean(d));
  const activeSignals = getActiveSignals(decomposition);
  const quality = classifyThesisQuality(thesis);
  const qualityState =
    quality.kind === "sharp"
      ? "strong"
      : quality.kind === "workable" || quality.kind === "stale"
        ? "workable"
        : "weak";
  const qualityHeadline =
    quality.kind === "sharp"
      ? "Sharp"
      : quality.kind === "workable"
        ? "Workable"
        : quality.kind === "stale"
          ? "Stale"
          : quality.kind === "review"
            ? "Needs review"
            : "Weak";
  const qualityChecks = [
    {
      label: "Must remain true",
      detail: quality.missingMustRemainTrue ? "Missing" : "Defined",
      tone: quality.missingMustRemainTrue ? "text-red-600" : "text-emerald-700",
    },
    {
      label: "Break condition",
      detail: quality.missingBreakCondition ? "Too vague" : "Defined",
      tone: quality.missingBreakCondition ? "text-red-600" : "text-emerald-700",
    },
    {
      label: "Freshness",
      detail:
        quality.kind === "stale"
          ? `${quality.daysOld}d old vs ${quality.cadenceDays}d cadence`
          : `${quality.daysOld}d old`,
      tone: quality.kind === "stale" ? "text-amber-700" : "text-foreground",
    },
  ];
  const copy = investorProfile === "thesis_driven"
    ? {
        edit: "Edit thesis",
        invalidate: "Invalidate thesis",
        stillTrue: "Still true if",
        breaks: "Breaks if",
        activeSignals: "Active signals",
        watching: "Watching for",
        qualityRead: "Read",
        qualitySummary:
          quality.kind === "sharp"
            ? "Specific enough to rely on."
            : quality.kind === "stale"
              ? "Overdue for refresh."
              : qualityState === "workable"
                ? "Usable, but still worth sharpening."
                : "Too fuzzy to trust without tightening.",
      }
    : investorProfile === "hearsay_driven"
      ? {
          edit: "Edit reason",
          invalidate: "Invalidate reason",
          stillTrue: "Still true if",
          breaks: "Breaks if",
          activeSignals: "Active signals",
          watching: "Watching for",
          qualityRead: "Read",
          qualitySummary:
            quality.kind === "sharp"
              ? "Specific enough to rely on."
              : quality.kind === "stale"
                ? "Overdue for refresh."
              : qualityState === "workable"
                  ? "Usable, but the story still needs sharpening."
                  : "Still too story-like to rely on without tightening.",
        }
      : {
          edit: "Edit",
          invalidate: "Invalidate",
          stillTrue: "Still true if",
          breaks: "Breaks if",
          activeSignals: "Active signals",
          watching: "Watching for",
          qualityRead: "Read",
          qualitySummary:
            quality.kind === "sharp"
              ? "Specific enough to rely on."
              : quality.kind === "stale"
                ? "Overdue for refresh."
              : qualityState === "workable"
                  ? "Usable, but still worth sharpening."
                  : "Too fuzzy to trust without tightening.",
        };

  return (
    <div className="border border-border bg-card divide-y divide-border/40">

      {/* ── Header: status strip + actions ── */}
      <div className="flex items-center justify-between px-5 py-3 gap-4 flex-wrap">
        <div className="flex items-center gap-3 flex-wrap min-w-0">
          {/* Status */}
          <div className="flex items-center gap-1.5 shrink-0">
            <span className={`h-1.5 w-1.5 rounded-full ${STATUS_DOT[thesis.status] ?? "bg-border"}`} />
            <span className={`font-mono text-[10px] uppercase tracking-[0.2em] ${STATUS_TEXT[thesis.status] ?? "text-muted-foreground"}`}>
              {thesis.status.replace("_", " ")}
            </span>
          </div>

          <span className="text-border/60 text-xs">·</span>

          {/* Confidence */}
          <span className={`font-mono text-[10px] uppercase tracking-[0.12em] ${CONFIDENCE_TEXT[thesis.confidence] ?? "text-muted-foreground"}`}>
            {thesis.confidence} confidence
          </span>

          <span className="text-border/60 text-xs">·</span>

          {/* Source */}
          <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-muted-foreground/60">
            {thesis.source === "ai_assisted" ? "Assisted" : "Manual"}
          </span>

        </div>

        {/* Actions */}
        <div className="flex items-center gap-4 shrink-0">
          <button
            onClick={onEdit}
            className="font-mono text-[10px] uppercase tracking-[0.15em] text-primary/60 hover:text-primary transition-colors"
          >
            {copy.edit}
          </button>
          {thesis.status !== "invalidated" && (
            <button
              onClick={onInvalidate}
              className="font-mono text-[10px] uppercase tracking-[0.15em] text-red-500/40 hover:text-red-600 transition-colors"
            >
              {copy.invalidate}
            </button>
          )}
        </div>
      </div>

      {/* ── Bull case — hero ── */}
      <div className="px-5 py-6 space-y-4">
        <blockquote className="border-l-2 border-primary/25 pl-4">
          <p className="font-display italic text-[1.15rem] leading-relaxed text-foreground/90 max-w-prose">
            {thesis.why_own_it}
          </p>
        </blockquote>

        {/* Thesis labels */}
        {labels.length > 0 && (
          <div className="flex flex-wrap gap-1.5 pl-4">
            {labels.map((label) => (
              <span
                key={label}
                className="font-mono text-[10px] uppercase tracking-[0.1em] text-muted-foreground/70 border border-border/50 px-1.5 py-0.5"
              >
                {label}
              </span>
            ))}
          </div>
        )}
      </div>

      <div className="grid gap-0 border-t border-border/40 lg:grid-cols-[minmax(0,1.15fr)_minmax(16rem,20rem)]">
        <div className="px-5 py-5">
          <div className="space-y-2">
            <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
              {copy.qualityRead}
            </p>
            <div className="space-y-1">
              <p className={`font-display italic text-[1.35rem] leading-tight ${QUALITY_TONE[qualityState]}`}>
                {qualityHeadline}
              </p>
              <p className="font-sans text-sm leading-relaxed text-foreground/80">
                {copy.qualitySummary}
              </p>
            </div>
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-3">
            <div className="border border-border/60 bg-background/70 p-3">
              <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                Monitorability
              </p>
              <p className={`mt-2 font-display text-[1.2rem] italic ${MONITORABILITY_TEXT[quality.monitorability ?? "medium"] ?? "text-muted-foreground"}`}>
                {quality.monitorability ?? "medium"}
              </p>
            </div>
            <div className="border border-border/60 bg-background/70 p-3">
              <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                Review cadence
              </p>
              <p className="mt-2 font-display text-[1.2rem] italic text-foreground">
                {quality.cadenceDays}d
              </p>
            </div>
            <div className="border border-border/60 bg-background/70 p-3">
              <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                Signals armed
              </p>
              <p className="mt-2 font-display text-[1.2rem] italic text-foreground">
                {activeSignals.length}
              </p>
            </div>
          </div>
        </div>

        <aside className="border-t border-border/40 bg-muted/15 px-5 py-5 lg:border-l lg:border-t-0">
          <div className="grid gap-3">
            {qualityChecks.map((item) => (
              <div key={item.label} className="border border-border/60 bg-background/70 px-3 py-3">
                <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                  {item.label}
                </p>
                <p className={`mt-2 font-sans text-sm leading-relaxed ${item.tone}`}>
                  {item.detail}
                </p>
              </div>
            ))}
          </div>
        </aside>
      </div>

      {/* ── Must remain true + Exit trigger ── */}
      <div className="grid md:grid-cols-2 divide-y md:divide-y-0 md:divide-x divide-border/40">
        {/* Must remain true */}
        <div className={`relative px-5 py-5 border-l-2 ${thesis.must_remain_true ? "border-l-emerald-500/35" : "border-l-amber-400/35"}`}>
          <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground mb-2">
            {copy.stillTrue}
          </p>
          {thesis.must_remain_true ? (
            <p className="font-sans text-sm leading-relaxed text-foreground/80">
              {thesis.must_remain_true}
            </p>
          ) : (
            <p className="font-sans text-sm leading-relaxed text-muted-foreground italic">
              Not defined — write the condition that must remain true.
            </p>
          )}
        </div>

        {/* Exit trigger */}
        <div className={`relative px-5 py-5 border-l-2 md:border-l-0 ${thesis.what_would_change_my_mind ? "border-l-red-500/30" : "border-l-border/30"}`}>
          <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground mb-2">
            {copy.breaks}
          </p>
          {thesis.what_would_change_my_mind ? (
            <p className="font-sans text-sm leading-relaxed text-foreground/80">
              {thesis.what_would_change_my_mind}
            </p>
          ) : (
            <p className="font-sans text-sm leading-relaxed text-muted-foreground italic">
              Not defined — write the event that would make you rethink this.
            </p>
          )}
        </div>
      </div>

      {/* ── Active signals or watch hints ── */}
      {(activeSignals.length > 0 || watchDescriptions.length > 0) && (
        <div className="px-5 py-4 space-y-3">
          <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
            {activeSignals.length > 0 ? copy.activeSignals : copy.watching}
          </p>

          <div className="space-y-0">
            {activeSignals.length > 0
              ? activeSignals.map((signal) => (
                  <div
                    key={signal.id}
                    className="flex items-start gap-3 py-2.5 border-b border-border/20 last:border-b-0"
                  >
                    <span className="font-mono text-[10px] text-emerald-600 mt-0.5 shrink-0">●</span>
                    <div className="space-y-0.5 min-w-0">
                      <p className="font-sans text-[13px] text-foreground leading-tight">
                        {signal.label}
                        {signal.entityTicker && (
                          <span className="font-mono text-[10px] text-muted-foreground/60 ml-2">
                            ({signal.entityTicker})
                          </span>
                        )}
                      </p>
                      {signal.checkLogic && (
                        <p className="font-sans text-xs text-muted-foreground/60 leading-relaxed">
                          {signal.checkLogic}
                        </p>
                      )}
                    </div>
                  </div>
                ))
              : watchDescriptions.map((desc, i) => (
                  <div
                    key={i}
                    className="flex items-start gap-3 py-2.5 border-b border-border/20 last:border-b-0"
                  >
                    <span className="font-mono text-[10px] text-muted-foreground/35 mt-0.5 shrink-0">○</span>
                    <p className="font-sans text-[13px] text-muted-foreground leading-tight">{desc}</p>
                  </div>
                ))}
          </div>
        </div>
      )}

      {/* ── AI summary ── */}
      {thesis.ai_summary && (
        <div className="px-5 py-4">
          <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground mb-1.5">
            Snapshot
          </p>
          <p className="font-sans text-xs text-muted-foreground/80 leading-relaxed">
            {thesis.ai_summary}
          </p>
        </div>
      )}

      {/* ── Footer ── */}
      <div className="px-5 py-3 flex items-start justify-between gap-4 flex-wrap">
        {ambiguityNote ? (
          <p className="font-sans text-xs text-amber-700/70 leading-relaxed max-w-lg">
            {ambiguityNote}
          </p>
        ) : (
          <span />
        )}
        <p className="font-mono text-[10px] text-muted-foreground/50 whitespace-nowrap ml-auto">
          Created {formatDate(thesis.created_at)} · Updated {formatDate(thesis.updated_at)}
        </p>
      </div>
    </div>
  );
}
