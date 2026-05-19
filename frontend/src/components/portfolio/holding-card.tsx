"use client";

import Link from "next/link";
import { formatCurrency, formatPercent } from "@/lib/utils";
import type { Holding, Thesis, HoldingPulse, UpcomingEarnings } from "@/types";

interface Props {
  holding: Holding;
  thesis?: Thesis;
  pulse?: HoldingPulse;
  earnings?: UpcomingEarnings;
  onGenerateDraft?: () => void;
  index?: number;
}

function statusStyle(pulse: HoldingPulse | undefined, hasThesis: boolean) {
  if (!hasThesis) return { dot: "text-border", label: "No thesis", text: "text-muted-foreground/60" };
  const s = pulse?.pulse_status ?? "intact";
  if (s === "review") return { dot: "text-red-600", label: "Needs review", text: "text-red-600" };
  if (s === "watch") return { dot: "text-amber-700", label: "Watching", text: "text-amber-700" };
  return { dot: "text-emerald-700", label: "Intact", text: "text-emerald-700" };
}

export function HoldingCard({ holding, thesis, pulse, earnings, onGenerateDraft, index = 0 }: Props) {
  const cost = holding.quantity * holding.average_cost_basis;
  const value = holding.current_value ?? 0;
  const pnl = value - cost;
  const pnlPct = cost > 0 ? (pnl / cost) * 100 : 0;

  const hasThesis = !!thesis;
  const { label, text } = statusStyle(pulse, hasThesis);
  const displayName = holding.name !== holding.ticker ? holding.name : holding.ticker;
  const thesisText = pulse?.reason ?? thesis?.why_own_it;

  return (
    <Link
      href={`/dashboard/positions/${holding.ticker}`}
      className="group block border-b border-border/60 py-5 transition-colors hover:bg-muted"
      style={{ animationDelay: `${index * 40}ms` }}
    >
      <div className="flex items-start gap-4 justify-between">

        {/* Left: ticker + name + thesis quote */}
        <div className="flex-1 min-w-0 space-y-1.5">
          <div className="flex items-baseline gap-3 flex-wrap">
            <span className="font-mono text-[11px] font-bold uppercase tracking-[0.2em] text-primary">
              {holding.ticker}
            </span>
            <span className="font-sans text-[15px] text-foreground leading-tight">
              {displayName}
            </span>
            {earnings && earnings.days_until <= 7 && (
              <span className="font-mono text-[10px] tracking-wide text-violet-700">
                earnings {earnings.days_until === 0 ? "today" : earnings.days_until === 1 ? "tomorrow" : `in ${earnings.days_until}d`}
              </span>
            )}
          </div>

          {hasThesis && thesisText ? (
            <p className="font-sans italic text-sm text-muted-foreground leading-relaxed line-clamp-2 max-w-xl">
              &ldquo;{thesisText}&rdquo;
            </p>
          ) : !hasThesis ? (
            <button
              onClick={(e) => { e.preventDefault(); e.stopPropagation(); onGenerateDraft?.(); }}
              className="font-mono text-[10px] uppercase tracking-[0.15em] text-primary/50 hover:text-primary transition-colors"
            >
              + Draft thesis with AI
            </button>
          ) : null}
        </div>

        {/* Right: value, P&L, status */}
        <div className="text-right shrink-0 space-y-1 pl-4">
          <p className="font-mono text-base tabular-nums text-foreground">
            {formatCurrency(value, holding.currency)}
          </p>
          <p className={`font-mono text-sm tabular-nums ${pnl >= 0 ? "text-emerald-700" : "text-red-600"}`}>
            {pnl >= 0 ? "+" : ""}{formatCurrency(pnl, holding.currency)}{" "}
            <span className="text-xs opacity-70">({formatPercent(pnlPct)})</span>
          </p>
          <p className={`font-mono text-[11px] ${text}`}>
            ● {label}
          </p>
        </div>
      </div>
    </Link>
  );
}
