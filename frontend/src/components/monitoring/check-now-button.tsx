"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";
import type { CheckNowResponse, MarketSnapshot } from "@/types";

interface CheckNowButtonProps {
  holdingId: string;
  ticker: string;
  currency?: string;
  onComplete: () => void;
}

function cleanTicker(ticker: string): string {
  return ticker.replace(/(?:_US)?_EQ$/i, "").replace(/([A-Z])([a-z]+)$/, "$1");
}

function formatLargeNumber(n: number): string {
  if (n >= 1e12) return `$${(n / 1e12).toFixed(1)}T`;
  if (n >= 1e9) return `$${(n / 1e9).toFixed(1)}B`;
  if (n >= 1e6) return `$${(n / 1e6).toFixed(0)}M`;
  return `$${n.toLocaleString()}`;
}

function SnapshotCard({ snapshot, ticker, currency, eventsCreated }: { snapshot: MarketSnapshot; ticker: string; currency: string; eventsCreated: number }) {
  const pnlPositive = (snapshot.pnl ?? 0) >= 0;
  const priceUp = (snapshot.price_change_pct ?? 0) >= 0;
  const hintsOk = snapshot.watch_hints_ok === snapshot.watch_hints_total && snapshot.watch_hints_total > 0;
  const checkedAt = snapshot.checked_at ? new Date(snapshot.checked_at).getTime() : null;

  const earningsDate = snapshot.upcoming_earnings_date
    ? new Date(snapshot.upcoming_earnings_date).toLocaleDateString("en-GB", { day: "numeric", month: "short" })
    : null;
  const earningsDays = snapshot.upcoming_earnings_date && checkedAt != null
    ? Math.ceil((new Date(snapshot.upcoming_earnings_date).getTime() - checkedAt) / (1000 * 60 * 60 * 24))
    : null;

  return (
    <div className="mt-4 border border-border bg-card animate-in fade-in slide-in-from-bottom-2 duration-300">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-border/40">
        <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 shrink-0" />
        <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
          {cleanTicker(ticker)} — checked just now
        </p>
      </div>

      <div className="grid grid-cols-2 gap-0 sm:grid-cols-4 divide-x divide-border/40">
        {snapshot.current_price != null && (
          <div className="px-4 py-3">
            <p className="font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground mb-1">Price</p>
            <p className="font-mono text-sm font-medium tabular-nums">{formatCurrency(snapshot.current_price, currency)}</p>
            {snapshot.price_change_pct != null && (
              <p className={`font-mono text-[10px] tabular-nums ${priceUp ? "text-emerald-600" : "text-red-600"}`}>
                {priceUp ? "+" : ""}{snapshot.price_change_pct.toFixed(2)}%
              </p>
            )}
          </div>
        )}

        {snapshot.pnl != null && (
          <div className="px-4 py-3">
            <p className="font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground mb-1">P&L</p>
            <p className={`font-mono text-sm font-medium tabular-nums ${pnlPositive ? "text-emerald-600" : "text-red-600"}`}>
              {formatCurrency(snapshot.pnl)}
            </p>
            {snapshot.pnl_pct != null && (
              <p className={`font-mono text-[10px] tabular-nums ${pnlPositive ? "text-emerald-600" : "text-red-600"}`}>
                {snapshot.pnl_pct >= 0 ? "+" : ""}{snapshot.pnl_pct.toFixed(1)}%
              </p>
            )}
          </div>
        )}

        {snapshot.pe_ratio != null && (
          <div className="px-4 py-3">
            <p className="font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground mb-1">P/E</p>
            <p className="font-mono text-sm font-medium tabular-nums">{snapshot.pe_ratio.toFixed(1)}</p>
            {snapshot.market_cap != null && (
              <p className="font-mono text-[10px] text-muted-foreground">{formatLargeNumber(snapshot.market_cap)}</p>
            )}
          </div>
        )}

        <div className="px-4 py-3">
          <p className="font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground mb-1">Signals</p>
          {snapshot.watch_hints_total > 0 ? (
            <p className={`font-mono text-sm font-medium tabular-nums ${hintsOk ? "text-emerald-600" : "text-amber-600"}`}>
              {snapshot.watch_hints_ok}/{snapshot.watch_hints_total}
            </p>
          ) : (
            <p className="font-mono text-sm text-muted-foreground">—</p>
          )}
          {snapshot.recent_news_count > 0 ? (
            <p className="font-mono text-[10px] text-muted-foreground">
              {eventsCreated > 0
                ? `${snapshot.recent_news_count} article${snapshot.recent_news_count !== 1 ? "s" : ""} · ${eventsCreated} flagged`
                : `${snapshot.recent_news_count} reviewed · none flagged`}
            </p>
          ) : (
            <p className="font-mono text-[10px] text-muted-foreground">No recent articles</p>
          )}
        </div>
      </div>

      {earningsDate && earningsDays != null && earningsDays > 0 && earningsDays <= 30 && (
        <div className="px-4 py-2.5 border-t border-border/40">
          <p className="font-mono text-[10px] text-muted-foreground/70">
            Earnings {earningsDate} · {earningsDays} day{earningsDays !== 1 ? "s" : ""} away
          </p>
        </div>
      )}
    </div>
  );
}

export function CheckNowButton({ holdingId, ticker, currency = "GBP", onComplete }: CheckNowButtonProps) {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<CheckNowResponse | null>(null);

  const handleCheckNow = async () => {
    try {
      setLoading(true);
      setResult(null);
      const res = await api.post<CheckNowResponse>(`/api/monitoring/holdings/${holdingId}/check-now`);
      setResult(res);
      if (res.status === "completed") {
        onComplete();
      }
    } catch (err) {
      console.error("Check now failed:", err);
    } finally {
      setLoading(false);
    }
  };

  const nextAvailable = result?.next_available_at ? new Date(result.next_available_at) : null;
  const isRateLimited = result?.status === "rate_limited";
  const hasEvents = result?.status === "completed" && (result?.events_created ?? 0) > 0;

  return (
    <div>
      <div className="flex items-center gap-4">
        <button
          onClick={handleCheckNow}
          disabled={loading || isRateLimited}
          className="font-mono text-[10px] uppercase tracking-[0.15em] border border-border text-foreground/70 hover:text-foreground px-4 py-2 transition-colors hover:border-border/80 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {loading ? "Checking…" : "Check now"}
        </button>

        {hasEvents && (
          <span className="font-mono text-[10px] uppercase tracking-[0.15em] text-amber-700">
            {result!.events_created} event{result!.events_created !== 1 ? "s" : ""} — review below
          </span>
        )}

        {isRateLimited && nextAvailable && (
          <span className="font-mono text-[10px] text-muted-foreground/60">
            Next check {nextAvailable.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
          </span>
        )}
      </div>

      {result?.status === "completed" && result.snapshot && (
        <SnapshotCard snapshot={result.snapshot} ticker={ticker} currency={currency} eventsCreated={result.events_created ?? 0} />
      )}
    </div>
  );
}
