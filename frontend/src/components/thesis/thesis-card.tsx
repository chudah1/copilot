"use client";

import { useState } from "react";
import { formatDate } from "@/lib/utils";
import { classifyCaseQuality } from "@/lib/decision-state";
import { describeWatchHint } from "@/lib/watch-hints";
import { aiAssistWeakMessaging } from "@/lib/ai-assisted-thesis";
import { InfoTip } from "@/components/ui/info-tip";
import type { Thesis, ThesisDecomposition, MonitoringGap } from "@/types";

interface Props {
  thesis: Thesis;
  decomposition?: ThesisDecomposition | null;
  investorProfile?: "thesis_driven" | "hearsay_driven" | null;
  monitoringGaps?: MonitoringGap[];
  showMonitoringDetails?: boolean;
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

function formatSignalThresholdValue(unit: string | undefined, threshold: number): string {
  if (
    unit === "pct" ||
    unit === "revenue_growth_yoy" ||
    unit === "earnings_growth_yoy" ||
    unit === "gross_margin"
  ) {
    const pct = Math.abs(threshold) <= 1 ? threshold * 100 : threshold;
    return `${pct % 1 === 0 ? pct.toFixed(0) : pct.toFixed(1)}%`;
  }
  return String(threshold);
}

function describeSignalCheckLogic(signalType: string, config: Record<string, unknown> | null): string | null {
  const c = config ?? {};
  const proxyFor = typeof c.proxy_for === "string" && c.proxy_for.trim().length > 0 ? c.proxy_for.trim() : null;
  if (signalType === "price_move") {
    const t = typeof c.threshold_pct === "number" ? c.threshold_pct : null;
    return t != null ? `Flags if the stock moves ${t}% or more.` : "Flags on a sharp price move.";
  }
  if (signalType === "revenue_growth" || signalType === "earnings_growth") {
    const threshold = typeof c.threshold === "number" ? c.threshold : null;
    const thresholdPct = typeof c.threshold_pct === "number" ? c.threshold_pct / 100 : null;
    const effectiveThreshold = threshold ?? thresholdPct;
    const operator = typeof c.operator === "string" ? c.operator : ">=";
    const label = signalType === "revenue_growth" ? "revenue growth" : "earnings growth";
    if (effectiveThreshold == null || (effectiveThreshold === 0 && operator === ">=")) {
      return proxyFor
        ? `Tracks ${label} as a proxy for ${proxyFor}.`
        : `Flags when ${label} falls below the previous year.`;
    }
    const fmt = formatSignalThresholdValue(
      signalType === "revenue_growth" ? "revenue_growth_yoy" : "earnings_growth_yoy",
      effectiveThreshold,
    );
    if (operator === ">=" || operator === ">") {
      return proxyFor
        ? `Flags when ${label} falls below ${fmt} compared with a year earlier, using it as a proxy for ${proxyFor}.`
        : `Flags when ${label} falls below ${fmt} compared with a year earlier.`;
    }
    if (operator === "<=" || operator === "<") {
      return proxyFor
        ? `Flags when ${label} rises above ${fmt} compared with a year earlier, using it as a proxy for ${proxyFor}.`
        : `Flags when ${label} rises above ${fmt} compared with a year earlier.`;
    }
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

export function ThesisCard({ thesis, decomposition, investorProfile, monitoringGaps = [], showMonitoringDetails = true, onEdit, onInvalidate }: Props) {
  const [renderedAt] = useState(() => Date.now());
  const aiAssistCopy = aiAssistWeakMessaging(investorProfile);
  const { labels, watchHints, ambiguityNote } = getInterpretation(thesis);
  const watchDescriptions = watchHints
    .map((hint) => describeWatchHint(hint))
    .filter((d): d is string => Boolean(d));
  const activeSignals = getActiveSignals(decomposition);
  const quality = classifyCaseQuality(thesis);
  const qualityState =
    quality.kind === "sharp"
      ? "strong"
      : quality.kind === "workable" || quality.kind === "review_overdue"
        ? "workable"
        : "weak";
  const qualityHeadline =
    quality.kind === "sharp"
      ? "Ready to watch"
      : quality.kind === "workable"
        ? "Needs one sharper condition"
        : quality.kind === "review_overdue"
          ? "Refresh soon"
          : "Needs sharper conditions";
  const subject =
    investorProfile === "thesis_driven"
      ? "thesis"
      : investorProfile === "hearsay_driven"
        ? "reason"
        : "reason";
  const qualityReadLabel =
    investorProfile === "thesis_driven"
      ? "Thesis quality"
      : investorProfile === "hearsay_driven"
        ? "Reason quality"
        : "Reason quality";
  const qualityChecks = [
    {
      label: "What must stay true",
      detail: quality.missingMustRemainTrue ? "Not written yet" : "Clear",
      tone: quality.missingMustRemainTrue ? "text-red-600" : "text-emerald-700",
      help: "The business condition that must continue for your reason to keep working.",
    },
    {
      label: "What changes your mind",
      detail: quality.missingBreakCondition ? "Still too loose" : "Clear",
      tone: quality.missingBreakCondition ? "text-red-600" : "text-emerald-700",
      help: "The result or event that should make you reconsider the position. It does not place a trade.",
    },
    {
      label: "Last reviewed",
      detail:
        quality.kind === "review_overdue"
          ? `${quality.daysOld} days ago · cadence ${quality.cadenceDays} days`
          : `${quality.daysOld} day${quality.daysOld === 1 ? "" : "s"} ago`,
      tone: quality.kind === "review_overdue" ? "text-amber-700" : "text-foreground",
      help: `How long it has been since this ${subject} was updated or confirmed.`,
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
        qualityRead: qualityReadLabel,
        qualitySummary:
          quality.kind === "sharp"
            ? "This thesis is specific enough to check against new evidence."
            : quality.kind === "review_overdue"
              ? "Refresh it and confirm the original thesis still holds."
              : qualityState === "workable"
                ? "This thesis is monitorable, but one condition is still loose."
                : thesis.source === "ai_assisted"
                  ? aiAssistCopy.qualitySummary
                  : "Add the business condition or result that would make you reconsider.",
      }
    : investorProfile === "hearsay_driven"
      ? {
          edit: "Edit reason",
          invalidate: "Invalidate reason",
          stillTrue: "Still true if",
          breaks: "Breaks if",
          activeSignals: "Active signals",
          watching: "Watching for",
          qualityRead: qualityReadLabel,
          qualitySummary:
            quality.kind === "sharp"
              ? "This reason is specific enough to check against new evidence."
            : quality.kind === "review_overdue"
                ? "Refresh it and confirm the original reason still holds."
              : qualityState === "workable"
                  ? "This reason is monitorable, but one condition is still loose."
                  : thesis.source === "ai_assisted"
                    ? aiAssistCopy.qualitySummary
                    : "Add the business condition or result that would make you reconsider.",
        }
      : {
          edit: "Edit",
          invalidate: "Invalidate",
          stillTrue: "Still true if",
          breaks: "Breaks if",
          activeSignals: "Active signals",
          watching: "Watching for",
          qualityRead: qualityReadLabel,
          qualitySummary:
            quality.kind === "sharp"
              ? "This reason is specific enough to check against new evidence."
            : quality.kind === "review_overdue"
                ? "Refresh it and confirm your reason still holds."
              : qualityState === "workable"
                  ? "This reason is monitorable, but one condition is still loose."
                  : thesis.source === "ai_assisted"
                    ? aiAssistCopy.qualitySummary
                    : "Add the business condition or result that would make you reconsider.",
        };

  const recentGaps = monitoringGaps.filter((g) => {
    const age = renderedAt - new Date(g.failed_at).getTime();
    return age < 24 * 60 * 60 * 1000;
  });
  const uniqueSources = [...new Set(recentGaps.map((g) => g.source))];
  const hasGaps = uniqueSources.length > 0;

  return (
    <div className="border border-border bg-card divide-y divide-border/40">

      {/* ── Header: status strip + actions ── */}
      <div className="flex items-center justify-between px-5 py-3 gap-4 flex-wrap">
        <div className="flex items-center gap-3 flex-wrap min-w-0">
          {/* Status */}
          <div className="flex items-center gap-1.5 shrink-0">
            <span className={`h-1.5 w-1.5 rounded-full ${STATUS_DOT[thesis.status] ?? "bg-border"}`} />
            {hasGaps && (
              <span
                title={`Monitoring gaps in last 24h: ${uniqueSources.join(", ")}`}
                className="inline-flex items-center justify-center w-4 h-4 rounded-full bg-amber-100 text-amber-600 text-[10px] font-bold cursor-help"
              >
                !
              </span>
            )}
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
            className="border border-border/60 bg-background/72 px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.15em] text-foreground/72 transition-colors hover:border-border hover:text-foreground"
          >
            {copy.edit}
          </button>
          {thesis.status !== "invalidated" && (
            <button
              onClick={onInvalidate}
              className="border border-red-500/20 bg-red-500/5 px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.15em] text-red-700/75 transition-colors hover:border-red-500/35 hover:text-red-800"
            >
              {copy.invalidate}
            </button>
          )}
        </div>
      </div>

      {/* ── Bull case — hero ── */}
      <div className="px-5 py-6 space-y-4">
        <div className="product-panel border border-border/60 bg-background/72 px-4 py-4">
          <p className="font-display italic text-[1.15rem] leading-relaxed text-foreground/90">
            {thesis.why_own_it}
          </p>
        </div>

        {/* Thesis labels */}
        {labels.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
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
            <div className="flex items-center gap-1.5">
              <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                {copy.qualityRead}
              </p>
              <InfoTip label={copy.qualityRead}>
                {`A check of how specific, current, and testable this ${subject} is. It rates the quality of your reasoning, not the investment.`}
              </InfoTip>
            </div>
            <div className="space-y-1">
              <p className={`font-display italic text-[1.35rem] leading-tight ${QUALITY_TONE[qualityState]}`}>
                {qualityHeadline}
              </p>
              <p className="font-sans text-sm leading-relaxed text-foreground/80">
                {copy.qualitySummary}
              </p>
            </div>
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <div className="min-w-0 border border-border/60 bg-background/70 p-3">
              <div className="flex min-w-0 items-start gap-1.5">
                <p className="min-w-0 font-mono text-[10px] uppercase leading-snug tracking-[0.16em] text-muted-foreground">
                  Monitorability
                </p>
                <InfoTip label="Monitorability">
                  {`How easily this ${subject} can be checked against public evidence. Specific conditions are easier to monitor than broad opinions.`}
                </InfoTip>
              </div>
              <p className={`mt-2 font-display text-[1.2rem] italic ${MONITORABILITY_TEXT[quality.monitorability ?? "medium"] ?? "text-muted-foreground"}`}>
                {quality.monitorability ?? "medium"}
              </p>
            </div>
            <div className="min-w-0 border border-border/60 bg-background/70 p-3">
              <div className="flex min-w-0 items-start gap-1.5">
                <p className="min-w-0 font-mono text-[10px] uppercase leading-snug tracking-[0.16em] text-muted-foreground">
                  Review cadence
                </p>
                <InfoTip label="Review cadence">
                  {`How often PenKeep asks you to revisit this ${subject} even when no evidence triggers an alert.`}
                </InfoTip>
              </div>
              <p className="mt-2 font-display text-[1.2rem] italic text-foreground">
                {quality.cadenceDays} days
              </p>
            </div>
            <div className="min-w-0 border border-border/60 bg-background/70 p-3">
              <div className="flex min-w-0 items-start gap-1.5">
                <p className="min-w-0 font-mono text-[10px] uppercase leading-snug tracking-[0.16em] text-muted-foreground">
                  Monitoring checks
                </p>
                <InfoTip label="Monitoring checks">
                  {`The number of active evidence checks tied to this ${subject}. A check is not a buy or sell instruction.`}
                </InfoTip>
              </div>
              <p className="mt-2 font-display text-[1.2rem] italic text-foreground">
                {activeSignals.length}
              </p>
            </div>
          </div>
        </div>

        <aside className="border-t border-border/40 bg-background/82 px-5 py-5 lg:border-t-0">
          <div className="space-y-3">
            <div className="product-panel border border-border/60 bg-background/72 px-3 py-3">
              <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                {copy.qualityRead}
              </p>
              <p className="mt-2 font-sans text-sm leading-relaxed text-foreground/78">
                {`These checks show whether this ${subject} is specific enough to trust when evidence lands.`}
              </p>
            </div>
            {qualityChecks.map((item) => (
              <div key={item.label} className="product-panel border border-border/60 bg-background/72 px-3 py-3">
                <div className="flex items-center gap-1">
                  <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                    {item.label}
                  </p>
                  <InfoTip label={item.label}>{item.help}</InfoTip>
                </div>
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
        <div className={`relative px-5 py-5 ${thesis.must_remain_true ? "bg-emerald-500/[0.035]" : "bg-amber-500/[0.035]"}`}>
          <div className="mb-2 flex items-center gap-1">
            <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
              {copy.stillTrue}
            </p>
            <InfoTip label={copy.stillTrue}>
              The business condition that must continue for your reason to keep working.
            </InfoTip>
          </div>
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
        <div className={`relative px-5 py-5 ${thesis.what_would_change_my_mind ? "bg-red-500/[0.03]" : "bg-background/55"}`}>
          <div className="mb-2 flex items-center gap-1">
            <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
              {copy.breaks}
            </p>
            <InfoTip label={copy.breaks} align="end">
              The result or event that should force you to review the position. It does not trigger an automatic trade.
            </InfoTip>
          </div>
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
      {showMonitoringDetails && (activeSignals.length > 0 || watchDescriptions.length > 0) && (
        <div className="px-5 py-4 space-y-3">
          <div className="flex items-center gap-1.5">
            <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
              {activeSignals.length > 0 ? "Monitoring checks" : copy.watching}
            </p>
            <InfoTip label={activeSignals.length > 0 ? "Monitoring checks" : "Watching for"}>
              {`Each row is a measurable check connected to something in your ${subject}. The line underneath explains when it will be flagged.`}
            </InfoTip>
          </div>

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

      {/* ── AI summary — the model's read gets its own ink card, distinct
             from the user's own words and the data chrome around it ── */}
      {thesis.ai_summary && (
        <div className="px-5 py-4">
          <div className="relative overflow-hidden bg-[#17150F] border border-[#332F24] px-4 py-4">
            <div aria-hidden className="absolute top-0 left-4 right-4 h-[2px] bg-emerald-600/70" />
            <div className="flex items-center gap-1.5">
              <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-[#A8A293]">
                penKeep&apos;s read
              </p>
              <InfoTip label="penKeep's read" iconClassName="text-[#A8A293] hover:text-[#ECE7DB]">
                {`The model&apos;s short summary of your ${subject}. It restates your view and is not advice.`}
              </InfoTip>
            </div>
            <p className="mt-2 font-display italic text-[1.05rem] leading-relaxed text-[#ECE7DB]">
              {thesis.ai_summary}
            </p>
          </div>
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
