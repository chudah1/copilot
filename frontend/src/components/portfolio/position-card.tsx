"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { formatAssumptionLabel } from "@/lib/assumption-label";
import { normalizeInvestorTerminology } from "@/lib/investor-language";
import { formatCurrency, formatPercent } from "@/lib/utils";
import { classifyThesisQuality } from "@/lib/thesis-quality";
import type { Holding, Thesis, HoldingPulse, LivePrice, UpcomingEarnings } from "@/types";

const PULSE_DOT: Record<string, string> = {
  intact: "bg-emerald-500",
  watch: "bg-amber-400",
  review: "bg-red-500",
};

const PULSE_RING: Record<string, string> = {
  review: "ring-1 ring-red-500/20",
  watch: "ring-1 ring-amber-500/20",
};

function cardStatusCopy(args: {
  hasThesis: boolean;
  pulse?: HoldingPulse;
  thesis?: Thesis;
  investorProfile?: "thesis_driven" | "hearsay_driven" | null;
}) {
  const { hasThesis, pulse, thesis, investorProfile } = args;
  const cadencePressure = Boolean(pulse?.reason?.includes("review cadence"));
  const assumptionLabel = formatAssumptionLabel(pulse?.assumption_label, investorProfile, {
    maxLength: 54,
    sentenceCaseFallback: true,
  });
  const pulseReason = pulse?.reason
    ? normalizeInvestorTerminology(pulse.reason, investorProfile)
    : null;
  const quality = classifyThesisQuality(thesis);
  if (!hasThesis) {
    return {
      eyebrow: "Missing",
      headline:
        investorProfile === "hearsay_driven"
          ? "No written reason yet."
          : "No written thesis yet.",
      detail:
        investorProfile === "hearsay_driven"
          ? "Add one so the story can actually be tracked."
          : "Add one so the thesis can actually be tracked.",
      tone: "text-muted-foreground/70",
    };
  }

  if (pulse?.pulse_status === "review") {
    return {
      eyebrow: "Review",
      headline: `${assumptionLabel} needs a call.`,
      detail: pulseReason || "Something meaningful changed.",
      tone: "text-red-600",
      subLabel: cadencePressure ? "Review cadence missed" : null,
    };
  }

  if (pulse?.pulse_status === "watch") {
    return {
      eyebrow: "Watch",
      headline: `${assumptionLabel} is under pressure.`,
      detail: pulseReason || "Nothing looks broken yet, but this position is no longer quiet.",
      tone: "text-amber-700",
      subLabel: cadencePressure ? "Review cadence drifting" : null,
    };
  }

  if (quality.kind === "weak") {
    return {
      eyebrow: "Weak",
      headline:
        investorProfile === "hearsay_driven"
          ? "The written reason is still too soft."
          : "The written thesis is still too soft.",
      detail: "It is still too fuzzy to trust under pressure.",
      tone: "text-amber-700",
      subLabel: null,
    };
  }

  if (quality.kind === "stale") {
    return {
      eyebrow: "Stale",
      headline:
        investorProfile === "hearsay_driven"
          ? "This reason is out of date."
          : "This thesis is out of date.",
      detail: `Last refreshed ${quality.daysOld}d ago, outside its ${quality.cadenceDays}d cadence.`,
      tone: "text-amber-700",
      subLabel: "Review cadence drifting",
    };
  }

  if (quality.kind === "workable") {
    return {
      eyebrow: "Workable",
      headline:
        investorProfile === "hearsay_driven"
          ? "The written reason works, but still has soft edges."
          : "The written thesis works, but still has soft edges.",
      detail: "Usable now, but not yet crisp.",
      tone: "text-amber-700",
      subLabel: null,
    };
  }

  return {
    eyebrow: "Calm",
    headline:
      investorProfile === "hearsay_driven"
        ? "Reason intact."
        : "Thesis intact.",
    detail: "Nothing needs a call right now.",
    tone: "text-emerald-700",
    subLabel: null,
  };
}

export function cleanTicker(ticker: string) {
  return ticker.replace(/_US_EQ$/, "").replace(/_EQ$/, "");
}

function timeAgo(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return null;
  const mins = Math.floor((Date.now() - then) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

interface PositionCardProps {
  holding: Holding;
  thesis?: Thesis;
  pulse?: HoldingPulse;
  earnings?: UpcomingEarnings;
  livePrice?: LivePrice;
  totalValue: number;
  onGenerateDraft?: () => void;
  investorProfile?: "thesis_driven" | "hearsay_driven" | null;
  index: number;
}

export function PositionCard({
  holding,
  thesis,
  pulse,
  earnings,
  livePrice,
  totalValue,
  onGenerateDraft,
  investorProfile,
  index,
}: PositionCardProps) {
  const value = livePrice?.current_value ?? holding.current_value ?? 0;
  const cost = holding.quantity * holding.average_cost_basis;
  const pnl = value - cost;
  const pnlPct = cost > 0 ? (pnl / cost) * 100 : 0;
  const allocationPct = totalValue > 0 ? (value / totalValue) * 100 : 0;

  const hasThesis = Boolean(thesis?.why_own_it);
  const noThesisCta =
    investorProfile === "hearsay_driven"
      ? "Draft a starting reason"
      : "Draft a starting thesis";
  const quality = classifyThesisQuality(thesis);
  const pulseStatus = pulse?.pulse_status ?? (thesis ? "intact" : null);
  const qualityAdjustedStatus =
    pulseStatus === "intact" && (quality.kind === "weak" || quality.kind === "stale" || quality.kind === "workable")
      ? "watch"
      : pulseStatus;
  const dotColor = qualityAdjustedStatus ? (PULSE_DOT[qualityAdjustedStatus] ?? "bg-border") : "bg-border";
  const ringClass = qualityAdjustedStatus ? (PULSE_RING[qualityAdjustedStatus] ?? "") : "";
  const qualityChipLabel =
    quality.kind === "sharp"
      ? "Sharp"
      : quality.kind === "stale"
        ? "Stale"
        : quality.kind === "workable"
          ? "Workable"
          : quality.kind === "weak"
            ? "Weak"
            : quality.kind === "review"
              ? "Review"
              : "Missing";
  const statusCopy = cardStatusCopy({
    hasThesis,
    pulse,
    thesis,
    investorProfile,
  });
  const showQualityChip = hasThesis && qualityChipLabel.toLowerCase() !== statusCopy.eyebrow.toLowerCase();

  return (
    <motion.div
      className="h-full"
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: index * 0.04, ease: "easeOut" }}
    >
      <Link href={`/dashboard/positions/${holding.ticker}`} className="block h-full">
        <div
          className={`h-full group relative flex flex-col gap-3 border border-border bg-card p-4 transition-all duration-150 hover:border-foreground/20 hover:shadow-md cursor-pointer ${ringClass}`}
        >
          {/* Allocation bar — top edge */}
          <div className="absolute top-0 left-0 right-0 h-[3px] bg-border overflow-hidden">
            <motion.div
              className="h-full bg-primary"
              initial={{ width: 0 }}
              animate={{ width: `${Math.min(allocationPct * 4, 100)}%` }}
              transition={{ duration: 0.6, delay: index * 0.05 + 0.2, ease: "easeOut" }}
            />
          </div>

          {/* Header row */}
          <div className="flex items-start justify-between pt-1">
            <div className="min-w-0">
              <p className="font-mono text-[11px] font-semibold tracking-[0.2em] text-primary">
                {cleanTicker(holding.ticker)}
              </p>
              <p className="font-sans text-[11px] text-muted-foreground mt-0.5 truncate max-w-[140px]">
                {holding.name}
              </p>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              {earnings && earnings.days_until <= 5 && (
                <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-violet-600 border border-violet-200 px-1 py-px">
                  {earnings.days_until === 0 ? "today" : earnings.days_until === 1 ? "tmrw" : `${earnings.days_until}d`}
                </span>
              )}
              <span className={`h-2 w-2 rounded-full flex-shrink-0 ${dotColor}`} />
            </div>
          </div>

          {/* Value + P&L */}
          <div>
            <p className="font-mono text-[1.05rem] tabular-nums text-foreground font-medium leading-tight">
              {formatCurrency(value)}
            </p>
            <p className={`font-mono text-[11px] tabular-nums mt-0.5 ${pnl >= 0 ? "text-emerald-700" : "text-red-600"}`}>
              {pnl >= 0 ? "+" : ""}{formatCurrency(pnl)}{" "}
              <span className="opacity-70">({formatPercent(pnlPct)})</span>
            </p>
          </div>

          {/* Allocation % with bar */}
          <div className="space-y-1">
            <div className="flex items-center justify-between">
              <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-muted-foreground/70">
                Portfolio weight
              </span>
              <span className="font-mono text-[10px] text-muted-foreground">
                {allocationPct.toFixed(1)}%
              </span>
            </div>
            <div className="h-px bg-border overflow-hidden">
              <motion.div
                className="h-full bg-foreground/20"
                initial={{ width: 0 }}
                animate={{ width: `${Math.min(allocationPct * 4, 100)}%` }}
                transition={{ duration: 0.5, delay: index * 0.05 + 0.25, ease: "easeOut" }}
              />
            </div>
          </div>

          {/* Spacer — pushes thesis/CTA flush to bottom */}
          <div className="flex-1" />

          <div className="space-y-1 border-t border-border/60 pt-2.5">
            <div className="flex items-center justify-between gap-2">
              <span className={`font-mono text-[10px] uppercase tracking-[0.14em] ${statusCopy.tone}`}>
                {statusCopy.eyebrow}
              </span>
              <div className="flex items-center gap-2">
                {showQualityChip && (
                  <span className={`font-mono text-[9px] uppercase tracking-[0.12em] px-1.5 py-0.5 ${
                    quality.kind === "sharp"
                      ? "text-emerald-700 bg-emerald-500/10"
                      : quality.kind === "stale" || quality.kind === "workable" || quality.kind === "weak"
                        ? "text-amber-700 bg-amber-500/10"
                        : "text-red-600 bg-red-500/10"
                  }`}>
                    {qualityChipLabel}
                  </span>
                )}
                {qualityAdjustedStatus && hasThesis && (
                  <span className={`h-1.5 w-1.5 rounded-full ${dotColor}`} />
                )}
              </div>
            </div>
            {statusCopy.subLabel && (
              <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-foreground/45">
                {statusCopy.subLabel}
              </p>
            )}
            <p className="font-sans text-[11px] text-foreground/85 leading-relaxed line-clamp-1">
              {statusCopy.headline}
            </p>
            <p className="font-sans text-[11px] text-muted-foreground leading-relaxed line-clamp-2">
              {statusCopy.detail}
            </p>
            {qualityAdjustedStatus === "intact" && hasThesis && timeAgo(pulse?.last_checked_at) && (
              <p className="font-mono text-[9px] uppercase tracking-[0.12em] text-muted-foreground/50">
                Checked {timeAgo(pulse?.last_checked_at)}
              </p>
            )}
          </div>

          {/* Thesis snippet or CTA */}
          {thesis?.why_own_it ? (
            <p className="font-sans text-[11px] italic text-foreground/85 leading-relaxed line-clamp-2">
              {thesis.why_own_it}
            </p>
          ) : (
            <button
              onClick={(e) => { e.preventDefault(); e.stopPropagation(); onGenerateDraft?.(); }}
              className="font-mono text-[10px] tracking-[0.04em] text-muted-foreground/70 hover:text-primary transition-colors text-left"
            >
              {noThesisCta}
            </button>
          )}
        </div>
      </Link>
    </motion.div>
  );
}
