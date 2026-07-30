"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { formatAssumptionLabel } from "@/lib/assumption-label";
import { tightenInvestorCopy } from "@/lib/investor-language";
import { formatCurrency, formatPercent } from "@/lib/utils";
import { classifyCaseQuality, getDecisionState } from "@/lib/decision-state";
import { aiAssistWeakMessaging } from "@/lib/ai-assisted-thesis";
import type { Holding, Thesis, HoldingPulse, LivePrice, UpcomingEarnings } from "@/types";
import { WatchReceipt } from "./watch-receipt";

const DECISION_DOT: Record<string, string> = {
  calm: "bg-emerald-500",
  changed: "bg-amber-400",
  needs_decision: "bg-red-500",
  needs_written_case: "bg-border",
};

const DECISION_RING: Record<string, string> = {
  needs_decision: "ring-1 ring-red-500/20",
  changed: "ring-1 ring-amber-500/20",
};

export function cardStatusCopy(args: {
  hasThesis: boolean;
  pulse?: HoldingPulse;
  thesis?: Thesis;
  investorProfile?: "thesis_driven" | "hearsay_driven" | null;
}) {
  const { hasThesis, pulse, thesis, investorProfile } = args;
  const aiAssistCopy = aiAssistWeakMessaging(investorProfile);
  const assumptionLabel = formatAssumptionLabel(pulse?.assumption_label, investorProfile, {
    maxLength: 54,
    sentenceCaseFallback: true,
  });
  const pulseReason = pulse?.reason
    ? tightenInvestorCopy(pulse.reason, investorProfile)
    : null;
  const quality = classifyCaseQuality(thesis);
  const decisionState = getDecisionState({ thesis, pulse });
  if (decisionState.kind === "needs_written_case" || !hasThesis) {
    return {
      eyebrow: "Missing",
      headline:
        investorProfile === "hearsay_driven"
          ? "No reason yet."
          : "No thesis yet.",
      detail:
        investorProfile === "hearsay_driven"
          ? "Write it so it can be tracked."
          : "Write it so it can be tracked.",
      tone: "text-muted-foreground/70",
    };
  }

  if (decisionState.kind === "needs_decision") {
    return {
      eyebrow: "Needs decision",
      headline: `${assumptionLabel} needs a call.`,
      detail: pulseReason || "Something meaningful changed.",
      tone: "text-red-600",
    };
  }

  if (decisionState.kind === "changed") {
    return {
      eyebrow: "Changed",
      headline: `${assumptionLabel} is under pressure.`,
      detail: pulseReason || "Not broken, but no longer quiet.",
      tone: "text-amber-700",
    };
  }

  if (quality.kind === "weak") {
    const assisted = thesis?.source === "ai_assisted";
    return {
      eyebrow: "Calm",
      headline:
        assisted
          ? aiAssistCopy.cardHeadline
          : investorProfile === "hearsay_driven"
            ? "This reason is too soft."
            : "This thesis is too soft.",
      detail: assisted ? aiAssistCopy.cardDetail : "Too vague to trust.",
      tone: "text-emerald-700",
    };
  }

  if (quality.kind === "review_overdue") {
    return {
      eyebrow: "Calm",
      headline:
        investorProfile === "hearsay_driven"
          ? "Reason intact."
          : "Thesis intact.",
      detail: `${quality.daysOld}d old. Cadence ${quality.cadenceDays}d.`,
      tone: "text-emerald-700",
    };
  }

  if (quality.kind === "workable") {
    return {
      eyebrow: "Calm",
      headline:
        investorProfile === "hearsay_driven"
          ? "The reason needs one clearer condition."
          : "The written case needs one clearer condition.",
      detail: "Monitoring is active, but one part is still broad.",
      tone: "text-emerald-700",
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
  };
}

export function cleanTicker(ticker: string) {
  return ticker.replace(/_US_EQ$/, "").replace(/_EQ$/, "");
}

interface PositionCardProps {
  holding: Holding;
  thesis?: Thesis;
  pulse?: HoldingPulse;
  earnings?: UpcomingEarnings;
  livePrice?: LivePrice;
  totalValue: number;
  onGenerateDraft?: () => void;
  /** When set, a plain left-click peeks instead of navigating. Modifier
      clicks and middle-clicks keep native link behavior (new tab, etc.). */
  onPeek?: () => void;
  investorProfile?: "thesis_driven" | "hearsay_driven" | null;
  index: number;
  featured?: boolean;
}

export function PositionCard({
  holding,
  thesis,
  pulse,
  earnings,
  livePrice,
  totalValue,
  onGenerateDraft,
  onPeek,
  investorProfile,
  index,
  featured = false,
}: PositionCardProps) {
  const value = livePrice?.current_value ?? holding.current_value ?? 0;
  const cost = holding.quantity * holding.average_cost_basis;
  const pnl = value - cost;
  const pnlPct = cost > 0 ? (pnl / cost) * 100 : 0;
  const allocationPct = totalValue > 0
    ? Math.min(100, Math.max(0, (value / totalValue) * 100))
    : 0;

  const hasThesis = Boolean(thesis?.why_own_it);
  const noThesisCta =
    investorProfile === "hearsay_driven"
      ? "Write reason"
      : "Write thesis";
  const quality = classifyCaseQuality(thesis);
  const decisionState = getDecisionState({ thesis, pulse });
  const dotColor = DECISION_DOT[decisionState.kind];
  const ringClass = DECISION_RING[decisionState.kind] ?? "";
  const qualityChipLabel =
    quality.kind === "sharp"
      ? "Ready to monitor"
      : quality.kind === "review_overdue"
        ? "Review overdue"
        : quality.kind === "workable"
          ? "Needs detail"
          : quality.kind === "weak"
            ? "Needs clearer reason"
            : "Missing";
  const statusCopy = cardStatusCopy({
    hasThesis,
    pulse,
    thesis,
    investorProfile,
  });
  const hasLivePulse = pulse?.pulse_status === "review" || pulse?.pulse_status === "watch";
  const showQualityChip =
    hasThesis &&
    !hasLivePulse &&
    qualityChipLabel.toLowerCase() !== statusCopy.eyebrow.toLowerCase();

  return (
    <motion.div
      className="h-full"
      initial={false}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay: Math.min(index, 11) * 0.04, ease: "easeOut" }}
    >
      <Link
        href={`/dashboard/positions/${holding.ticker}`}
        className="block h-full"
        onClick={(e) => {
          if (!onPeek) return;
          if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) return;
          e.preventDefault();
          onPeek();
        }}
      >
        <div
          className={`h-full group relative gap-3 border border-border bg-card p-4 transition-all duration-200 ease-out hover:border-foreground/20 hover:-translate-y-0.5 hover:shadow-[0_10px_30px_-12px_rgba(52,40,24,0.28)] cursor-pointer ${
            featured
              ? "grid grid-cols-1 sm:grid-cols-[minmax(12rem,0.75fr)_minmax(0,1.25fr)] sm:grid-rows-[auto_auto_1fr] sm:gap-x-6"
              : "flex flex-col"
          } ${ringClass}`}
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
          <div className={`flex items-start justify-between pt-1 ${featured ? "sm:col-start-1 sm:row-start-1" : ""}`}>
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
          <div className={featured ? "sm:col-start-1 sm:row-start-2" : ""}>
            <p className="font-mono text-[1.05rem] tabular-nums text-foreground font-medium leading-tight">
              {formatCurrency(value, holding.portfolio_currency ?? "GBP")}
            </p>
            <p className={`font-mono text-[11px] tabular-nums mt-0.5 ${pnl >= 0 ? "text-emerald-700" : "text-red-600"}`}>
              {pnl >= 0 ? "+" : ""}{formatCurrency(pnl, holding.portfolio_currency ?? "GBP")}{" "}
              <span className="opacity-70">({formatPercent(pnlPct)})</span>
            </p>
          </div>

          {/* Allocation % with bar */}
          <div className={`space-y-1 ${featured ? "sm:col-start-1 sm:row-start-3" : ""}`}>
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
          {!featured && <div className="flex-1" />}

          <div className={`space-y-1 border-t border-border/60 pt-2.5 ${
            featured ? "sm:col-start-2 sm:row-start-1 sm:row-span-2 sm:border-l sm:border-t-0 sm:pl-6 sm:pt-0" : ""
          }`}>
            <div className="flex items-center justify-between gap-2">
              <span className={`font-mono text-[10px] uppercase tracking-[0.14em] ${statusCopy.tone}`}>
                {statusCopy.eyebrow}
              </span>
              <div className="flex items-center gap-2">
                {showQualityChip && (
                  <span className={`font-mono text-[9px] uppercase tracking-[0.12em] px-1.5 py-0.5 ${
                    quality.kind === "sharp"
                      ? "text-emerald-700 bg-emerald-500/10"
                      : quality.kind === "review_overdue" || quality.kind === "workable" || quality.kind === "weak"
                        ? "text-amber-700 bg-amber-500/10"
                        : "text-red-600 bg-red-500/10"
                  }`}>
                    {qualityChipLabel}
                  </span>
                )}
                {hasThesis && (
                  <span className={`h-1.5 w-1.5 rounded-full ${dotColor}`} />
                )}
              </div>
            </div>
            <p className="font-sans text-[11px] text-foreground/85 leading-relaxed line-clamp-1">
              {statusCopy.headline}
            </p>
            <p className="font-sans text-[11px] text-muted-foreground leading-relaxed line-clamp-2">
              {statusCopy.detail}
            </p>
            <WatchReceipt pulse={pulse} hasThesis={hasThesis} />

          </div>

          {/* Thesis snippet or CTA */}
          {thesis?.why_own_it ? (
            <p className={`font-sans text-[11px] italic text-foreground/85 leading-relaxed line-clamp-2 ${
              featured ? "sm:col-start-2 sm:row-start-3 sm:border-l sm:border-border/60 sm:pl-6" : ""
            }`}>
              {thesis.why_own_it}
            </p>
          ) : (
            <button
              onClick={(e) => { e.preventDefault(); e.stopPropagation(); onGenerateDraft?.(); }}
              className={`font-mono text-[10px] tracking-[0.04em] text-muted-foreground/70 hover:text-primary transition-colors text-left ${
                featured ? "sm:col-start-2 sm:row-start-3 sm:border-l sm:border-border/60 sm:pl-6" : ""
              }`}
            >
              {noThesisCta}
            </button>
          )}
        </div>
      </Link>
    </motion.div>
  );
}
