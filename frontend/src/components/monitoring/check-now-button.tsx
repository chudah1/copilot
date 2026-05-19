"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import type { CheckNowResponse, MarketSnapshot } from "@/types";

interface CheckNowButtonProps {
  holdingId: string;
  ticker: string;
  currency?: string;
  onComplete: () => void;
}

function formatLargeNumber(n: number): string {
  if (n >= 1e12) return `$${(n / 1e12).toFixed(1)}T`;
  if (n >= 1e9) return `$${(n / 1e9).toFixed(1)}B`;
  if (n >= 1e6) return `$${(n / 1e6).toFixed(0)}M`;
  return `$${n.toLocaleString()}`;
}

function SnapshotCard({ snapshot, ticker, currency }: { snapshot: MarketSnapshot; ticker: string; currency: string }) {
  const pnlColor = (snapshot.pnl ?? 0) >= 0 ? "text-emerald-600" : "text-red-600";
  const priceChangeColor = (snapshot.price_change_pct ?? 0) >= 0 ? "text-emerald-600" : "text-red-600";
  const hintsOk = snapshot.watch_hints_ok === snapshot.watch_hints_total && snapshot.watch_hints_total > 0;
  const checkedAt = snapshot.checked_at ? new Date(snapshot.checked_at).getTime() : null;

  const earningsDate = snapshot.upcoming_earnings_date
    ? new Date(snapshot.upcoming_earnings_date).toLocaleDateString("en-GB", { day: "numeric", month: "short" })
    : null;
  const earningsDays = snapshot.upcoming_earnings_date && checkedAt != null
    ? Math.ceil((new Date(snapshot.upcoming_earnings_date).getTime() - checkedAt) / (1000 * 60 * 60 * 24))
    : null;

  return (
    <div className="mt-4 rounded-xl border bg-card p-4 animate-in fade-in slide-in-from-bottom-2 duration-300">
      <div className="flex items-center gap-2 mb-3">
        <span className="inline-block h-2 w-2 rounded-full bg-emerald-500" />
        <p className="text-sm font-medium">Thesis holding — {ticker} checked just now</p>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {snapshot.current_price != null && (
          <div>
            <p className="text-[11px] text-muted-foreground">Price</p>
            <p className="text-base font-semibold">{formatCurrency(snapshot.current_price, currency)}</p>
            {snapshot.price_change_pct != null && (
              <p className={`text-xs ${priceChangeColor}`}>
                {snapshot.price_change_pct >= 0 ? "+" : ""}{snapshot.price_change_pct.toFixed(2)}% since last check
              </p>
            )}
          </div>
        )}

        {snapshot.pnl != null && (
          <div>
            <p className="text-[11px] text-muted-foreground">Your P&L</p>
            <p className={`text-base font-semibold ${pnlColor}`}>
              {formatCurrency(snapshot.pnl, currency)}
            </p>
            {snapshot.pnl_pct != null && (
              <p className={`text-xs ${pnlColor}`}>
                {snapshot.pnl_pct >= 0 ? "+" : ""}{snapshot.pnl_pct.toFixed(1)}% vs cost
              </p>
            )}
          </div>
        )}

        {snapshot.pe_ratio != null && (
          <div>
            <p className="text-[11px] text-muted-foreground">P/E Ratio</p>
            <p className="text-base font-semibold">{snapshot.pe_ratio.toFixed(1)}</p>
            {snapshot.market_cap != null && (
              <p className="text-xs text-muted-foreground">{formatLargeNumber(snapshot.market_cap)} cap</p>
            )}
          </div>
        )}

        <div>
          <p className="text-[11px] text-muted-foreground">Signals</p>
          {snapshot.watch_hints_total > 0 ? (
            <p className={`text-base font-semibold ${hintsOk ? "text-emerald-600" : "text-amber-600"}`}>
              {snapshot.watch_hints_ok}/{snapshot.watch_hints_total} passing
            </p>
          ) : (
            <p className="text-base font-semibold text-muted-foreground">None set</p>
          )}
          <p className="text-xs text-muted-foreground">
            {snapshot.recent_news_count} recent article{snapshot.recent_news_count !== 1 ? "s" : ""}
          </p>
        </div>
      </div>

      {earningsDate && earningsDays != null && earningsDays > 0 && earningsDays <= 30 && (
        <p className="mt-3 text-xs text-muted-foreground">
          Earnings {earningsDate} ({earningsDays} day{earningsDays !== 1 ? "s" : ""} away)
        </p>
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
      <div className="flex items-center gap-3">
        <Button
          variant="outline"
          size="sm"
          onClick={handleCheckNow}
          disabled={loading || isRateLimited}
        >
          {loading ? "Checking..." : "Check now"}
        </Button>
        {hasEvents && (
          <span className="text-xs text-amber-600 font-medium">
            {result!.events_created} event{result!.events_created !== 1 ? "s" : ""} found — review below
          </span>
        )}
        {isRateLimited && nextAvailable && (
          <span className="text-xs text-muted-foreground">
            Next available {nextAvailable.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
          </span>
        )}
      </div>

      {result?.status === "completed" && result.snapshot && !hasEvents && (
        <SnapshotCard snapshot={result.snapshot} ticker={ticker} currency={currency} />
      )}
    </div>
  );
}
