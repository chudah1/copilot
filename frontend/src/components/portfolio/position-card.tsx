"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { formatCurrency, formatPercent } from "@/lib/utils";
import type { Holding, Thesis, HoldingPulse, LivePrice, UpcomingEarnings } from "@/types";

const PULSE_DOT: Record<string, string> = {
  intact: "bg-emerald-500",
  watch: "bg-amber-400",
  review: "bg-red-500",
};

const PULSE_RING: Record<string, string> = {
  review: "ring-1 ring-red-200",
  watch: "ring-1 ring-amber-200",
};

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

  const pulseStatus = pulse?.pulse_status ?? (thesis ? "intact" : null);
  const dotColor = pulseStatus ? (PULSE_DOT[pulseStatus] ?? "bg-border") : "bg-border";
  const ringClass = pulseStatus ? (PULSE_RING[pulseStatus] ?? "") : "";
  const noThesisCta =
    investorProfile === "hearsay_driven"
      ? "+ Turn the story into a reason"
      : "+ Write down your thesis";

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

          {/* Thesis snippet or CTA */}
          {thesis?.why_own_it ? (
            <p className="font-sans text-[11px] italic text-foreground/75 leading-relaxed line-clamp-2 border-t border-border/60 pt-2.5">
              {thesis.why_own_it}
            </p>
          ) : (
            <button
              onClick={(e) => { e.preventDefault(); e.stopPropagation(); onGenerateDraft?.(); }}
              className="font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground/60 hover:text-primary transition-colors border-t border-border/60 pt-2.5 text-left"
            >
              {noThesisCta}
            </button>
          )}
        </div>
      </Link>
    </motion.div>
  );
}
