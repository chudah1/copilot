"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { formatCurrency } from "@/lib/utils";
import { CheckNowButton } from "@/components/monitoring/check-now-button";
import type { CheckNowResponse, Holding, HoldingPulse, Thesis } from "@/types";
import { WatchReceipt } from "@/components/portfolio/watch-receipt";
import { PriceSparkline } from "@/components/portfolio/price-sparkline";
import { ageInDays, getDecisionState } from "@/lib/decision-state";
import type { CaseReviewPressure } from "@/lib/decision-state";
import { cleanTicker } from "./position-helpers";
import type { TabId } from "./position-helpers";

interface PositionHeaderProps {
  holding: Holding;
  activeThesis: Thesis | undefined;
  pulse: HoldingPulse | null;
  investorProfile: "thesis_driven" | "hearsay_driven" | null;
  headerCollapsed: boolean;
  hasPrice: boolean;
  value: number;
  pnl: number;
  pnlPct: string;
  stalePressure: CaseReviewPressure | null;
  tabs: { id: TabId; label: string; badge?: number | string }[];
  activeTab: TabId;
  unreviewedEvents: number;
  deleteConfirming: boolean;
  deleteLoading: boolean;
  onDelete: () => void;
  onSetDeleteConfirming: (v: boolean) => void;
  onCheckNowComplete: (result: CheckNowResponse) => Promise<void> | void;
  onSelectTab: (id: TabId) => void;
  onOpenNote: () => void;
}

export function PositionHeader({
  holding, activeThesis, pulse, investorProfile, headerCollapsed, hasPrice, value, pnl, pnlPct,
  stalePressure, tabs, activeTab, unreviewedEvents, deleteConfirming,
  deleteLoading, onDelete, onSetDeleteConfirming, onCheckNowComplete, onSelectTab,
  onOpenNote,
}: PositionHeaderProps) {
  const decisionState = getDecisionState({ thesis: activeThesis, pulse });
  // Native price vs native average cost — same currency, so FX noise drops out.
  const priceVsAvgCostPct =
    holding.current_price != null &&
    holding.average_cost_native != null &&
    holding.average_cost_native > 0
      ? ((holding.current_price - holding.average_cost_native) / holding.average_cost_native) * 100
      : null;
  const decisionStatusDot = {
    needs_written_case: "bg-border",
    needs_decision: "bg-red-500",
    changed: "bg-amber-500",
    calm: "bg-emerald-500",
  }[decisionState.kind];

  return (
      <div className="sticky top-[52px] z-20 bg-background border-b border-border/60">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-10">

          {/* Nav row */}
          <div className="flex flex-col gap-3 pt-4 pb-2 sm:flex-row sm:items-center sm:justify-between">
            <Link
              href="/dashboard"
              className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground hover:text-primary transition-colors"
            >
              ← Portfolio
            </Link>
            <div className="flex flex-wrap items-center gap-2 sm:justify-end">
              {deleteConfirming ? (
                <div className="flex flex-wrap items-center gap-2 sm:justify-end">
                  <span className="font-mono text-[10px] text-muted-foreground">Remove all data?</span>
                  <button
                    onClick={onDelete}
                    disabled={deleteLoading}
                    className="font-mono text-[10px] uppercase tracking-[0.15em] text-red-600 hover:text-red-700 transition-colors disabled:opacity-40"
                  >
                    {deleteLoading ? "Removing…" : "Confirm"}
                  </button>
                  <button
                    onClick={() => onSetDeleteConfirming(false)}
                    className="font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground hover:text-foreground transition-colors"
                  >
                    Cancel
                  </button>
                </div>
              ) : (
                <button
                  onClick={() => onSetDeleteConfirming(true)}
                  className="font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground/70 hover:text-muted-foreground transition-colors"
                >
                  Remove position
                </button>
              )}
              <button
                onClick={onOpenNote}
                className="border border-border px-3 py-2 font-mono text-[10px] uppercase tracking-[0.15em] text-primary transition-colors hover:border-primary/40"
              >
                + Note
              </button>
              <CheckNowButton
                holdingId={holding.id}
                ticker={holding.ticker}
                currency={holding.currency}
                portfolioCurrency={holding.portfolio_currency ?? "GBP"}
                investorProfile={investorProfile ?? null}
                onComplete={onCheckNowComplete}
              />
            </div>
          </div>

          {/* Identity + value row */}
          <div className={`flex flex-col gap-4 pb-3 overflow-hidden transition-all duration-200 sm:flex-row sm:items-end sm:justify-between sm:gap-6 ${headerCollapsed ? "max-h-0 pb-0 opacity-0 sm:max-h-40 sm:pb-3 sm:opacity-100" : "max-h-60 sm:max-h-40"}`}>
            <div>
              <h1 className="font-display italic text-[2.9rem] leading-none text-primary tracking-tight sm:text-[3.5rem]">
                {cleanTicker(holding.ticker)}
              </h1>
              {holding.name && holding.name !== holding.ticker && (
                <p className="font-sans text-[13px] text-muted-foreground mt-1 leading-none">
                  {holding.name}
                </p>
              )}
            </div>
            <div className="shrink-0 pb-0.5 sm:text-right">
              {hasPrice ? (
                <>
                  <p className="font-mono text-[1.6rem] tabular-nums text-foreground leading-tight">
                    {formatCurrency(value, holding.portfolio_currency ?? "GBP")}
                  </p>
                  <p className={`font-mono text-[13px] tabular-nums mt-0.5 ${pnl >= 0 ? "text-emerald-700" : "text-red-600"}`}>
                    {pnl >= 0 ? "+" : ""}{formatCurrency(pnl, holding.portfolio_currency ?? "GBP")}
                    <span className="opacity-60 ml-1.5">({pnl >= 0 ? "+" : ""}{pnlPct}%)</span>
                  </p>
                </>
              ) : (
                <>
                  <p className="font-mono text-[1.6rem] tabular-nums text-muted-foreground/70 leading-tight">—</p>
                  <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground/60 mt-1">
                    Price unavailable
                  </p>
                </>
              )}
              <WatchReceipt
                pulse={pulse ?? undefined}
                hasThesis={Boolean(activeThesis)}
                className="mt-1"
              />
            </div>
          </div>

          <div className={`grid grid-cols-3 gap-px overflow-hidden border border-border/60 bg-border/60 transition-all duration-200 ${headerCollapsed ? "max-h-0 border-0 opacity-0 sm:max-h-24 sm:border sm:opacity-100" : "max-h-24"} mb-3`}>
            <div className="bg-background/90 px-3 py-2">
              <p className="font-mono text-[9px] uppercase tracking-[0.15em] text-muted-foreground">
                Shares
              </p>
              <p className="mt-1 font-mono text-sm tabular-nums text-foreground">
                {holding.quantity.toLocaleString()}
              </p>
            </div>
            <div className="bg-background/90 px-3 py-2">
              <p className="font-mono text-[9px] uppercase tracking-[0.15em] text-muted-foreground">
                Current price
              </p>
              <p className="mt-1 font-mono text-sm tabular-nums text-foreground">
                {holding.current_price != null
                  ? formatCurrency(holding.current_price, holding.currency || "GBP")
                  : "—"}
              </p>
            </div>
            <div className="bg-background/90 px-3 py-2">
              <p className="font-mono text-[9px] uppercase tracking-[0.15em] text-muted-foreground">
                Average cost
              </p>
              <p className="mt-1 font-mono text-sm tabular-nums text-foreground">
                {holding.average_cost_native != null
                  ? formatCurrency(holding.average_cost_native, holding.currency || "GBP")
                  : formatCurrency(
                      holding.average_cost_basis,
                      holding.portfolio_currency ?? "GBP",
                    )}
              </p>
              {priceVsAvgCostPct != null && (
                <p className={`mt-0.5 font-sans text-[10px] leading-tight ${priceVsAvgCostPct >= 0 ? "text-emerald-700" : "text-red-600"}`}>
                  Price is {Math.abs(priceVsAvgCostPct).toFixed(1)}% {priceVsAvgCostPct >= 0 ? "above" : "below"} this
                </p>
              )}
            </div>
          </div>

          {/* The decision's price line — collapses with the rest of the header */}
          <div className={`overflow-hidden transition-all duration-200 ${headerCollapsed ? "max-h-0 opacity-0 sm:max-h-24 sm:opacity-100" : "max-h-24"}`}>
            <PriceSparkline holdingId={holding.id} className="mb-3" />
          </div>

          {/* Status ribbon */}
          <div className={`flex flex-col items-start gap-3 pb-3 overflow-hidden transition-all duration-200 sm:flex-row sm:items-center sm:gap-4 ${headerCollapsed ? "max-h-0 pb-0 opacity-0 sm:max-h-20 sm:pb-3 sm:opacity-100" : "max-h-48 sm:max-h-20"}`}>
            <div className="flex flex-wrap items-center gap-2">
              <span className={`h-1.5 w-1.5 rounded-full ${decisionStatusDot}`} />
              <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                {decisionState.label}
              </span>
            </div>
            {activeThesis && (
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-mono text-[10px] text-muted-foreground/60">
                  updated {ageInDays(activeThesis.updated_at)}d ago
                </span>
                {stalePressure && (
                  <>
                    <span className="text-border text-[10px]">·</span>
                    <span className="font-mono text-[10px] text-amber-700/80">
                      {stalePressure.cadenceDays}d cadence
                    </span>
                  </>
                )}
              </div>
              )}
          </div>

          {/* Tab strip */}
          <div className="flex gap-1 -mx-1 overflow-x-auto pb-0.5">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => onSelectTab(tab.id)}
                className="relative pb-3 px-3 font-mono text-[10px] uppercase tracking-[0.2em] transition-colors flex items-center gap-2 whitespace-nowrap"
                style={{ color: activeTab === tab.id ? "var(--primary)" : "var(--muted-foreground)" }}
              >
                {tab.label}
                {tab.badge !== undefined && (
                  <span className={`inline-flex items-center justify-center h-4 min-w-4 px-1 rounded-sm font-mono text-[10px] tabular-nums ${
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
  );
}
