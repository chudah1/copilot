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

function pulseConfig(pulse: HoldingPulse | undefined, hasThesis: boolean) {
  if (!hasThesis) return { color: "bg-border", label: "No thesis", labelColor: "text-muted-foreground/50" };
  const s = pulse?.pulse_status ?? "intact";
  if (s === "review") return { color: "bg-red-500", label: "Review", labelColor: "text-red-600" };
  if (s === "watch") return { color: "bg-amber-500", label: "Watch", labelColor: "text-amber-700" };
  return { color: "bg-emerald-500", label: "Intact", labelColor: "text-emerald-700" };
}

export function HoldingCard({ holding, thesis, pulse, earnings, onGenerateDraft, index = 0 }: Props) {
  const cost = holding.quantity * holding.average_cost_basis;
  const value = holding.current_value ?? 0;
  const pnl = value - cost;
  const pnlPct = cost > 0 ? (pnl / cost) * 100 : 0;

  const hasThesis = !!thesis;
  const { color: dotColor, label: statusLabel, labelColor } = pulseConfig(pulse, hasThesis);
  const displayName = holding.name !== holding.ticker ? holding.name : holding.ticker;
  const thesisText = pulse?.reason ?? thesis?.why_own_it;

  return (
    <Link
      href={`/dashboard/positions/${holding.ticker}`}
      className="group block border-b border-border/50 py-4 transition-colors hover:bg-secondary/60"
      style={{ animationDelay: `${index * 35}ms` }}
    >
      <div className="flex items-start gap-5 justify-between">

        {/* Status dot + content */}
        <div className="flex items-start gap-3 flex-1 min-w-0">
          {/* Pulse dot */}
          <div className="mt-[5px] flex-shrink-0">
            <span className={`block h-2 w-2 rounded-full ${dotColor}`} />
          </div>

          {/* Text block */}
          <div className="flex-1 min-w-0 space-y-1">
            <div className="flex items-baseline gap-2.5 flex-wrap">
              <span className="font-mono text-[11px] font-semibold tracking-[0.18em] text-primary">
                {holding.ticker.replace("_US_EQ", "").replace("_EQ", "")}
              </span>
              <span className="font-sans text-sm text-foreground/80 leading-tight">
                {displayName}
              </span>
              {earnings && earnings.days_until <= 7 && (
                <span className="font-mono text-[9px] tracking-[0.12em] uppercase text-violet-600 border border-violet-200 px-1.5 py-px rounded-sm">
                  earnings {earnings.days_until === 0 ? "today" : earnings.days_until === 1 ? "tomorrow" : `${earnings.days_until}d`}
                </span>
              )}
            </div>

            {hasThesis && thesisText ? (
              <p className="font-sans text-xs text-muted-foreground leading-relaxed line-clamp-1 max-w-lg italic">
                {thesisText}
              </p>
            ) : !hasThesis ? (
              <button
                onClick={(e) => { e.preventDefault(); e.stopPropagation(); onGenerateDraft?.(); }}
                className="font-mono text-[9px] uppercase tracking-[0.15em] text-muted-foreground/50 hover:text-primary transition-colors border-b border-dashed border-muted-foreground/30 pb-px"
              >
                Draft thesis with AI
              </button>
            ) : null}
          </div>
        </div>

        {/* Right: numbers + status */}
        <div className="text-right shrink-0 space-y-1 pl-4">
          <p className="font-mono text-[0.9375rem] tabular-nums text-foreground font-medium">
            {formatCurrency(value)}
          </p>
          <p className={`font-mono text-xs tabular-nums ${pnl >= 0 ? "text-emerald-700" : "text-red-600"}`}>
            {pnl >= 0 ? "+" : ""}{formatCurrency(pnl)}{" "}
            <span className="opacity-60">({formatPercent(pnlPct)})</span>
          </p>
          <p className={`font-mono text-[10px] uppercase tracking-[0.1em] ${labelColor}`}>
            {statusLabel}
          </p>
        </div>
      </div>
    </Link>
  );
}
