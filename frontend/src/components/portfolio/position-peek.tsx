"use client";

import { useEffect, useRef, useSyncExternalStore } from "react";
import { createPortal } from "react-dom";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import { formatCurrency, formatPercent, formatDate } from "@/lib/utils";
import { getDecisionState } from "@/lib/decision-state";
import { AnimatedCurrency } from "@/components/ui/animated-currency";
import { PriceSparkline } from "./price-sparkline";
import { cardStatusCopy, cleanTicker } from "./position-card";
import type { Holding, Thesis, HoldingPulse, LivePrice, UpcomingEarnings } from "@/types";

const DECISION_DOT: Record<string, string> = {
  calm: "bg-emerald-500",
  changed: "bg-amber-400",
  needs_decision: "bg-red-500",
  needs_written_case: "bg-border",
};

const subscribeToNothing = () => () => undefined;
const getClientSnapshot = () => true;
const getServerSnapshot = () => false;

const PEEK_SECTION = {
  hidden: { opacity: 0, y: 6 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.28, ease: "easeOut" as const } },
};

interface PositionPeekProps {
  holding: Holding | null;
  thesis?: Thesis;
  pulse?: HoldingPulse;
  earnings?: UpcomingEarnings;
  livePrice?: LivePrice;
  totalValue: number;
  investorProfile?: "thesis_driven" | "hearsay_driven" | null;
  onClose: () => void;
}

/**
 * Slide-over peek at a position from the dashboard — everything already
 * loaded on the page, no navigation, no extra fetches. The full position
 * page stays one click away.
 */
export function PositionPeek({
  holding,
  thesis,
  pulse,
  earnings,
  livePrice,
  totalValue,
  investorProfile,
  onClose,
}: PositionPeekProps) {
  const closeRef = useRef<HTMLButtonElement>(null);
  const open = Boolean(holding);
  // The dashboard's AppShell wraps content in a positioned, z-indexed layer
  // (.product-main), which traps any fixed-position descendant inside its own
  // stacking context — the peek's z-50 would then lose to the navbar's z-40
  // even though 50 > 40, because they're no longer compared in the same
  // context. Portal to <body> to escape it, the same way Radix's Dialog does.
  const mounted = useSyncExternalStore(subscribeToNothing, getClientSnapshot, getServerSnapshot);

  useEffect(() => {
    if (!open) return;
    closeRef.current?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = previousOverflow;
    };
  }, [open, onClose]);

  if (!mounted) return null;

  return createPortal(
    <AnimatePresence>
      {holding && (
        <>
          <motion.div
            key="peek-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            onClick={onClose}
            className="fixed inset-0 z-40 bg-foreground/25 backdrop-blur-[2px]"
          />
          <motion.aside
            key="peek-panel"
            role="dialog"
            aria-modal="true"
            aria-label={`${cleanTicker(holding.ticker)} position peek`}
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", stiffness: 380, damping: 40 }}
            className="fixed inset-y-0 right-0 z-50 flex w-full max-w-[26rem] flex-col border-l border-border bg-background shadow-2xl"
          >
            <PeekContent
              holding={holding}
              thesis={thesis}
              pulse={pulse}
              earnings={earnings}
              livePrice={livePrice}
              totalValue={totalValue}
              investorProfile={investorProfile}
              onClose={onClose}
              closeRef={closeRef}
            />
          </motion.aside>
        </>
      )}
    </AnimatePresence>,
    document.body,
  );
}

function PeekContent({
  holding,
  thesis,
  pulse,
  earnings,
  livePrice,
  totalValue,
  investorProfile,
  onClose,
  closeRef,
}: Omit<PositionPeekProps, "holding"> & {
  holding: Holding;
  closeRef: React.RefObject<HTMLButtonElement | null>;
}) {
  const value = livePrice?.current_value ?? holding.current_value ?? 0;
  const cost = holding.quantity * holding.average_cost_basis;
  const pnl = value - cost;
  const pnlPct = cost > 0 ? (pnl / cost) * 100 : 0;
  const allocationPct = totalValue > 0 ? (value / totalValue) * 100 : 0;
  const currency = holding.portfolio_currency ?? "GBP";
  const hasThesis = Boolean(thesis?.why_own_it);
  const decisionState = getDecisionState({ thesis, pulse });
  const statusCopy = cardStatusCopy({ hasThesis, pulse, thesis, investorProfile });
  const hasLivePulse = pulse?.pulse_status === "review" || pulse?.pulse_status === "watch";
  const positionHref = `/dashboard/positions/${holding.ticker}`;

  return (
    <>
      {/* Header */}
      <div className="flex items-start justify-between gap-4 border-b border-border/60 px-5 py-4">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className={`h-2 w-2 shrink-0 rounded-full ${DECISION_DOT[decisionState.kind]}`} />
            <p className="font-display italic text-[1.7rem] leading-none text-primary tracking-tight">
              {cleanTicker(holding.ticker)}
            </p>
          </div>
          {holding.name && holding.name !== holding.ticker && (
            <p className="mt-1.5 truncate font-sans text-xs text-muted-foreground">{holding.name}</p>
          )}
        </div>
        <button
          ref={closeRef}
          onClick={onClose}
          aria-label="Close peek"
          className="-m-2 shrink-0 p-3 font-mono text-sm leading-none text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/35"
        >
          ✕
        </button>
      </div>

      {/* Body — sections settle in sequence once the panel has slid in */}
      <motion.div
        className="min-h-0 flex-1 space-y-5 overflow-y-auto px-5 py-5"
        initial="hidden"
        animate="visible"
        variants={{
          visible: { transition: { staggerChildren: 0.06, delayChildren: 0.12 } },
        }}
      >
        <motion.div variants={PEEK_SECTION}>
          <p className="font-mono text-[1.5rem] tabular-nums leading-tight text-foreground">
            <AnimatedCurrency value={value} currency={currency} />
          </p>
          <p className={`mt-0.5 font-mono text-[12px] tabular-nums ${pnl >= 0 ? "text-emerald-700" : "text-red-600"}`}>
            {pnl >= 0 ? "+" : ""}
            {formatCurrency(pnl, currency)}
            <span className="ml-1.5 opacity-60">({formatPercent(pnlPct)})</span>
          </p>
          <div className="mt-3 grid grid-cols-3 gap-px border border-border/60 bg-border/60">
            <div className="bg-background/90 px-2.5 py-2">
              <p className="font-mono text-[9px] uppercase tracking-[0.14em] text-muted-foreground">Shares</p>
              <p className="mt-1 font-mono text-[13px] tabular-nums text-foreground">
                {holding.quantity.toLocaleString()}
              </p>
            </div>
            <div className="bg-background/90 px-2.5 py-2">
              <p className="font-mono text-[9px] uppercase tracking-[0.14em] text-muted-foreground">Avg cost</p>
              <p className="mt-1 font-mono text-[13px] tabular-nums text-foreground">
                {holding.average_cost_native != null
                  ? formatCurrency(holding.average_cost_native, holding.currency || "GBP")
                  : formatCurrency(holding.average_cost_basis, currency)}
              </p>
            </div>
            <div className="bg-background/90 px-2.5 py-2">
              <p className="font-mono text-[9px] uppercase tracking-[0.14em] text-muted-foreground">Weight</p>
              <p className="mt-1 font-mono text-[13px] tabular-nums text-foreground">
                {allocationPct.toFixed(1)}%
              </p>
            </div>
          </div>
          <PriceSparkline holdingId={holding.id} className="mt-4" />
        </motion.div>

        {/* Status */}
        <motion.div variants={PEEK_SECTION} className="border-l-2 border-border/70 pl-3">
          <p className={`font-mono text-[10px] uppercase tracking-[0.16em] ${statusCopy.tone}`}>
            {statusCopy.eyebrow}
          </p>
          <p className="mt-1 font-sans text-sm leading-relaxed text-foreground/90">{statusCopy.headline}</p>
          <p className="mt-0.5 font-sans text-xs leading-relaxed text-muted-foreground">{statusCopy.detail}</p>
        </motion.div>

        {/* Earnings */}
        {earnings && (
          <motion.div variants={PEEK_SECTION} className="flex items-center gap-3 border border-sky-500/25 bg-sky-500/8 px-3 py-2.5">
            <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-sky-700">
              Earnings{" "}
              {earnings.days_until === 0
                ? "today"
                : earnings.days_until === 1
                  ? "tomorrow"
                  : `in ${earnings.days_until} days`}
            </span>
            <span className="font-mono text-[10px] text-muted-foreground">{formatDate(earnings.report_date)}</span>
          </motion.div>
        )}

        {/* Written case */}
        {thesis?.why_own_it ? (
          <motion.div variants={PEEK_SECTION} className="space-y-4">
            <div>
              <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                {investorProfile === "thesis_driven" ? "Your thesis" : "Your reason"}
              </p>
              <blockquote className="mt-2 border-l-2 border-primary/25 pl-3">
                <p className="font-display italic text-[1.02rem] leading-relaxed text-foreground/90">
                  {thesis.why_own_it}
                </p>
              </blockquote>
            </div>
            {thesis.must_remain_true && (
              <div>
                <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                  Still true if
                </p>
                <p className="mt-1.5 font-sans text-[13px] leading-relaxed text-foreground/80">
                  {thesis.must_remain_true}
                </p>
              </div>
            )}
            {thesis.what_would_change_my_mind && (
              <div>
                <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                  Breaks if
                </p>
                <p className="mt-1.5 font-sans text-[13px] leading-relaxed text-foreground/80">
                  {thesis.what_would_change_my_mind}
                </p>
              </div>
            )}
            <p className="font-mono text-[10px] text-muted-foreground/60">
              Updated {formatDate(thesis.updated_at)}
            </p>
          </motion.div>
        ) : (
          <motion.div variants={PEEK_SECTION} className="border border-border/60 bg-card/60 px-4 py-3.5">
            <p className="font-sans text-sm leading-relaxed text-foreground/85">
              {investorProfile === "hearsay_driven" ? "No reason written yet." : "No thesis written yet."}
            </p>
            <p className="mt-1 font-sans text-xs leading-relaxed text-muted-foreground">
              Write it and monitoring can start judging evidence against it.
            </p>
          </motion.div>
        )}
      </motion.div>

      {/* Footer */}
      <div className="flex items-center gap-2 border-t border-border/60 px-5 pt-4 pb-[max(1rem,env(safe-area-inset-bottom))]">
        <Link
          href={hasThesis ? positionHref : `${positionHref}?source=dashboard_blind_spot`}
          className="flex-1 bg-primary px-4 py-2.5 text-center font-mono text-[10px] uppercase tracking-[0.16em] text-primary-foreground transition-colors hover:bg-primary/90"
        >
          {hasThesis
            ? "Open position"
            : investorProfile === "hearsay_driven"
              ? "Write the reason"
              : "Write the thesis"}
        </Link>
        {hasLivePulse && (
          <Link
            href={`${positionHref}?tab=monitoring`}
            className="flex-1 border border-primary/30 px-4 py-2.5 text-center font-mono text-[10px] uppercase tracking-[0.16em] text-primary transition-colors hover:border-primary/60"
          >
            What changed
          </Link>
        )}
      </div>
    </>
  );
}
