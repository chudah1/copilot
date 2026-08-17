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
  holding, activeThesis, pulse, investorProfile, hasPrice, value, pnl, pnlPct,
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
    <>
      <div className="relative z-20 border-b border-border/60 bg-background">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-10">

          {/* Nav row */}
          <div className="flex flex-col gap-3 pt-4 pb-3 sm:flex-row sm:items-center sm:justify-between">
            <Link
              href="/dashboard"
              className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground hover:text-primary transition-colors"
            >
              ← Portfolio
            </Link>
            <div className="flex flex-wrap items-center gap-2 sm:justify-end">
              {deleteConfirming ? (
                <div className="flex flex-wrap items-center gap-2 border border-red-500/20 bg-red-500/5 px-3 py-2 sm:justify-end">
                  <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-red-700/80">
                    Remove all data?
                  </span>
                  <button
                    onClick={onDelete}
                    disabled={deleteLoading}
                    className="border border-red-500/25 bg-background/80 px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.15em] text-red-700/80 transition-colors hover:border-red-500/40 hover:text-red-800 disabled:opacity-40"
                  >
                    {deleteLoading ? "Removing…" : "Confirm"}
                  </button>
                  <button
                    onClick={() => onSetDeleteConfirming(false)}
                    className="border border-border/60 bg-background/72 px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground transition-colors hover:border-border hover:text-foreground"
                  >
                    Cancel
                  </button>
                </div>
              ) : (
                <button
                  onClick={() => onSetDeleteConfirming(true)}
                  className="border border-border/60 bg-background/72 px-3 py-2 font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground transition-colors hover:border-border hover:text-foreground"
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
          <div className="flex flex-col gap-4 pb-3 sm:flex-row sm:items-end sm:justify-between sm:gap-6">
            <div>
              <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                Position
              </p>
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
              <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                Live value
              </p>
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

          <div className="mb-3 grid grid-cols-3 gap-px overflow-hidden border border-border/60 bg-border/60">
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

          <div>
            <PriceSparkline
              holdingId={holding.id}
              className="mb-3"
              investorProfile={investorProfile}
            />
          </div>

          {/* Status ribbon */}
          <div className="flex flex-col items-start gap-3 pb-3 sm:flex-row sm:items-center sm:gap-4">
            <div className="flex flex-wrap items-center gap-2">
              <span className={`h-1.5 w-1.5 rounded-full ${decisionStatusDot}`} />
              <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                {decisionState.label}
              </span>
            </div>
            {activeThesis && (
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-mono text-[10px] text-muted-foreground/60">
                  Updated {ageInDays(activeThesis.updated_at)}d ago
                </span>
                {stalePressure && (
                  <>
                    <span className="text-border text-[10px]">·</span>
                    <span className="font-mono text-[10px] text-amber-700/80">
                      Review cadence {stalePressure.cadenceDays}d
                    </span>
                  </>
                )}
              </div>
              )}
          </div>

        </div>
      </div>

      {/* Keep only the lightweight tab rail sticky; the hero above keeps its
          natural height so scrolling never causes a layout jump. */}
      <div className="sticky top-[84px] z-30 border-b border-border/60 bg-background/95 backdrop-blur-sm">
        <div className="mx-auto flex max-w-5xl items-center gap-4 px-4 sm:px-6 lg:px-10">
          <span className="hidden shrink-0 border-r border-border/60 py-3 pr-4 font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground sm:inline">
            {cleanTicker(holding.ticker)}
          </span>
          <div className="flex min-w-0 flex-1 gap-1 overflow-x-auto">
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
    </>
  );
}
