"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import type { Holding, PortfolioSummary, SimulateTradeResponse } from "@/types";

function pct(v: number) {
  return `${v.toFixed(1)}%`;
}

// --- Trade verdict -----------------------------------------------------------

function gradeTheTrade(result: SimulateTradeResponse): {
  grade: string;
  color: string;
  bg: string;
  border: string;
  headline: string;
  detail: string;
} {
  const w = result.warnings;
  const concAfter = result.after.top_3_concentration_pct;
  const concDelta = concAfter - result.before.top_3_concentration_pct;

  if (w.length === 0 && concDelta <= 2) {
    return { grade: "A", color: "text-emerald-700", bg: "bg-emerald-500/8", border: "border-emerald-500/25", headline: "Clean entry", detail: "No concentration warnings. This fits your portfolio well." };
  }
  if (w.length <= 1 && concDelta <= 5) {
    return { grade: "B", color: "text-blue-700", bg: "bg-blue-500/8", border: "border-blue-500/25", headline: "Looks reasonable", detail: "Minor considerations but nothing alarming." };
  }
  if (w.some((x) => x.warning_type === "concentration_risk")) {
    return { grade: "C", color: "text-amber-700", bg: "bg-amber-500/8", border: "border-amber-500/25", headline: "Concentration risk", detail: `This would make your top positions drive ${pct(concAfter)} of your portfolio.` };
  }
  return { grade: "D", color: "text-red-600", bg: "bg-red-500/8", border: "border-red-500/25", headline: "Proceed with caution", detail: `${w.length} warning${w.length !== 1 ? "s" : ""} flagged. Think this through.` };
}

// --- Donut chart -------------------------------------------------------------

const PALETTE = ["#8b5cf6", "#6366f1", "#3b82f6", "#06b6d4", "#14b8a6", "#10b981", "#f59e0b", "#a8a29e"];

function DonutChart({ breakdown, label, size = 112 }: { breakdown: Record<string, number>; label: string; size?: number }) {
  const sorted = Object.entries(breakdown).sort(([, a], [, b]) => b - a);
  if (sorted.length === 0) return null;

  const stops = sorted.reduce<string[]>((segments, [, val], i) => {
    const start = sorted.slice(0, i).reduce((total, [, current]) => total + current, 0);
    const end = start + val;
    segments.push(`${PALETTE[i % PALETTE.length]} ${start}% ${end}%`);
    return segments;
  }, []);

  return (
    <div className="flex flex-col items-center gap-2">
      <div
        className="rounded-full"
        style={{
          width: size, height: size,
          background: `conic-gradient(${stops.join(", ")})`,
          mask: "radial-gradient(circle, transparent 55%, black 56%)",
          WebkitMask: "radial-gradient(circle, transparent 55%, black 56%)",
        }}
      />
      <p className="text-xs font-medium text-muted-foreground">{label}</p>
      <div className="flex flex-wrap justify-center gap-x-3 gap-y-1">
        {sorted.map(([name, val], i) => (
          <span key={name} className="flex items-center gap-1 text-[11px] text-muted-foreground">
            <span className="inline-block h-2 w-2 rounded-full" style={{ backgroundColor: PALETTE[i % PALETTE.length] }} />
            {name} {pct(val)}
          </span>
        ))}
      </div>
    </div>
  );
}

// --- Narrative ---------------------------------------------------------------

function buildNarrative(result: SimulateTradeResponse): string[] {
  const lines: string[] = [];
  const concDelta = result.after.top_3_concentration_pct - result.before.top_3_concentration_pct;
  const isNew = result.after.holdings_count > result.before.holdings_count;

  lines.push(`${formatCurrency(result.simulated_value)} into ${result.name}, bringing your portfolio to ${formatCurrency(result.after.total_value)}.`);
  if (isNew) lines.push(`This adds a new position — you'd go from ${result.before.holdings_count} to ${result.after.holdings_count} holdings.`);
  if (Math.abs(concDelta) >= 0.5) {
    lines.push(concDelta > 0
      ? `Concentration tightens: top 3 go from ${pct(result.before.top_3_concentration_pct)} to ${pct(result.after.top_3_concentration_pct)}.`
      : `Diversification improves: top 3 drop from ${pct(result.before.top_3_concentration_pct)} to ${pct(result.after.top_3_concentration_pct)}.`);
  }
  return lines;
}

// --- Page --------------------------------------------------------------------

export default function SimulatePage() {
  const router = useRouter();
  const [ticker, setTicker] = useState("");
  const [quantity, setQuantity] = useState("");
  const [price, setPrice] = useState("");
  const [loading, setLoading] = useState(false);
  const [adding, setAdding] = useState(false);
  const [result, setResult] = useState<SimulateTradeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Current portfolio context
  const [summary, setSummary] = useState<PortfolioSummary | null>(null);
  const [holdings, setHoldings] = useState<Holding[]>([]);

  useEffect(() => {
    Promise.all([
      api.get<PortfolioSummary>("/api/portfolio/summary"),
      api.get<Holding[]>("/api/portfolio/holdings"),
    ]).then(([s, h]) => { setSummary(s); setHoldings(h); }).catch(() => {});
  }, []);

  const handleSimulate = async () => {
    if (!ticker || !quantity || !price) return;
    try {
      setLoading(true);
      setError(null);
      setResult(null);
      const res = await api.post<SimulateTradeResponse>("/api/portfolio/simulate", {
        ticker: ticker.toUpperCase(),
        quantity: parseFloat(quantity),
        price_per_share: parseFloat(price),
      });
      setResult(res);
    } catch (err) {
      setError("Simulation failed. Check the ticker and try again.");
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const addHolding = async (navigateTo: "dashboard" | "thesis") => {
    if (!result) return;
    try {
      setAdding(true);
      await api.post<Holding>("/api/portfolio/holdings", {
        ticker: result.ticker,
        name: result.name,
        quantity: result.simulated_quantity,
        average_cost_basis: result.simulated_price,
      });
      router.push(navigateTo === "thesis" ? `/dashboard/positions/${result.ticker}` : "/dashboard");
    } catch {
      setError("Failed to add holding.");
      setAdding(false);
    }
  };

  const verdict = result ? gradeTheTrade(result) : null;
  const narrative = result ? buildNarrative(result) : [];

  // Top holdings sorted by value
  const topHoldings = [...holdings]
    .filter((h) => h.current_value != null)
    .sort((a, b) => (b.current_value ?? 0) - (a.current_value ?? 0))
    .slice(0, 5);

  // Sectors the user doesn't have yet
  return (
    <div className="max-w-2xl mx-auto px-6 py-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight">What if&hellip;</h1>
      </div>

      {/* Input */}
      <div className="mb-8 rounded-xl border bg-card p-5">
        <div className="flex items-center gap-2 text-lg text-muted-foreground flex-wrap">
          <span>I buy</span>
          <input
            type="number"
            placeholder="10"
            value={quantity}
            onChange={(e) => setQuantity(e.target.value)}
            className="w-16 border-b-2 border-muted-foreground/30 bg-transparent text-center text-foreground font-medium outline-none focus:border-primary"
          />
          <span>shares of</span>
          <input
            placeholder="NVDA"
            value={ticker}
            onChange={(e) => setTicker(e.target.value)}
            className="w-20 border-b-2 border-muted-foreground/30 bg-transparent text-center text-foreground font-medium uppercase outline-none focus:border-primary"
          />
          <span>at $</span>
          <input
            type="number"
            step="0.01"
            placeholder="135"
            value={price}
            onChange={(e) => setPrice(e.target.value)}
            className="w-20 border-b-2 border-muted-foreground/30 bg-transparent text-center text-foreground font-medium outline-none focus:border-primary"
          />
          <span>each.</span>
        </div>

        <Button className="mt-5" size="lg" onClick={handleSimulate} disabled={loading || !ticker || !quantity || !price}>
          {loading ? "Thinking..." : "Show me the impact"}
        </Button>

        {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
      </div>

      {/* === Pre-simulation: current portfolio context === */}
      {!result && summary && (
        <div className="space-y-5 animate-in fade-in duration-300">
          {/* Current stats */}
          <div className="rounded-xl border bg-muted/20 p-5">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-4">Your portfolio right now</p>
            <div className="grid grid-cols-3 gap-4 text-center">
              <div>
                <p className="text-xl font-bold">{formatCurrency(summary.total_value)}</p>
                <p className="text-[11px] text-muted-foreground mt-0.5">Total value</p>
              </div>
              <div>
                <p className="text-xl font-bold">{summary.holdings_count}</p>
                <p className="text-[11px] text-muted-foreground mt-0.5">Holdings</p>
              </div>
              <div>
                <p className={`text-xl font-bold ${summary.top_3_concentration_pct >= 50 ? "text-amber-600" : ""}`}>
                  {pct(summary.top_3_concentration_pct)}
                </p>
                <p className="text-[11px] text-muted-foreground mt-0.5">Top 3 concentration</p>
              </div>
            </div>
          </div>

          {/* Sector donut + top holdings side by side */}
          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
            {Object.keys(summary.sector_breakdown).length > 0 && (
              <div className="rounded-xl border bg-card p-5">
                <DonutChart breakdown={summary.sector_breakdown} label="Sector allocation" size={100} />
              </div>
            )}

            {topHoldings.length > 0 && (
              <div className="rounded-xl border bg-card p-5">
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-3">Largest positions</p>
                <div className="space-y-2">
                  {topHoldings.map((h) => {
                    const weight = summary.total_value > 0 ? ((h.current_value ?? 0) / summary.total_value) * 100 : 0;
                    return (
                      <div key={h.id} className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium w-12">{h.ticker}</span>
                          <div className="h-1.5 rounded-full bg-muted w-20 overflow-hidden">
                            <div className="h-full rounded-full bg-violet-500" style={{ width: `${Math.min(weight, 100)}%` }} />
                          </div>
                        </div>
                        <span className="text-xs text-muted-foreground">{pct(weight)}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>

          {/* Nudge */}
          <p className="text-xs text-center text-muted-foreground">
            Try simulating a new position to see how it shifts your allocation and concentration.
          </p>
        </div>
      )}

      {/* === Post-simulation results === */}
      {result && verdict && (
        <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
          {/* Verdict */}
          <div className={`rounded-xl border-2 ${verdict.border} ${verdict.bg} p-5`}>
            <div className="flex items-start gap-4">
              <div className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-full ${verdict.bg} border ${verdict.border}`}>
                <span className={`text-xl font-black ${verdict.color}`}>{verdict.grade}</span>
              </div>
              <div>
                <p className={`text-lg font-semibold ${verdict.color}`}>{verdict.headline}</p>
                <p className={`text-sm mt-0.5 ${verdict.color} opacity-80`}>{verdict.detail}</p>
              </div>
            </div>
          </div>

          {/* Narrative */}
          <div className="space-y-1.5 px-1">
            {narrative.map((line, i) => (
              <p key={i} className="text-sm text-muted-foreground leading-relaxed">{line}</p>
            ))}
          </div>

          {/* Warnings */}
          {result.warnings.length > 0 && (
            <div className="space-y-2">
              {result.warnings.map((w, i) => (
                <div key={i} className={`rounded-lg border px-4 py-2.5 text-sm ${w.warning_type === "missing_thesis" ? "border-blue-500/25 bg-blue-500/8 text-blue-700" : "border-amber-500/25 bg-amber-500/8 text-amber-700"}`}>
                  {w.message}
                </div>
              ))}
            </div>
          )}

          {/* Donut comparison */}
          {(Object.keys(result.before.sector_breakdown).length > 0 || Object.keys(result.after.sector_breakdown).length > 0) && (
            <div className="rounded-xl border bg-muted/20 p-6">
              <p className="text-sm font-medium mb-5 text-center">Sector allocation shift</p>
              <div className="grid grid-cols-2 gap-6">
                <DonutChart breakdown={result.before.sector_breakdown} label="Before" />
                <DonutChart breakdown={result.after.sector_breakdown} label={`After +${result.ticker}`} />
              </div>
            </div>
          )}

          {/* Key numbers */}
          <div className="grid grid-cols-3 gap-3">
            <NumberCard label="Portfolio" before={formatCurrency(result.before.total_value)} after={formatCurrency(result.after.total_value)} />
            <NumberCard label="Holdings" before={String(result.before.holdings_count)} after={String(result.after.holdings_count)} />
            <NumberCard label="Top 3" before={pct(result.before.top_3_concentration_pct)} after={pct(result.after.top_3_concentration_pct)} />
          </div>

          {/* CTAs */}
          <div className="rounded-xl border bg-card p-5 space-y-3">
            <p className="text-sm font-medium text-center">Ready to commit?</p>
            <div className="flex flex-col gap-2 sm:flex-row">
              <Button className="flex-1" size="lg" onClick={() => addHolding("thesis")} disabled={adding}>
                {adding ? "Adding..." : `Add ${result.ticker} & write thesis`}
              </Button>
              <Button variant="outline" className="flex-1" size="lg" onClick={() => addHolding("dashboard")} disabled={adding}>
                Just add it
              </Button>
            </div>
          </div>

          <p className="text-center text-xs text-muted-foreground pb-4">
            <Link href="/dashboard" className="hover:underline underline-offset-4">&larr; Back to dashboard</Link>
          </p>
        </div>
      )}
    </div>
  );
}

function NumberCard({ label, before, after }: { label: string; before: string; after: string }) {
  return (
    <div className="rounded-lg border bg-card p-3 text-center">
      <p className="text-[11px] font-medium text-muted-foreground uppercase tracking-wide">{label}</p>
      <p className="text-xs text-muted-foreground/60 mt-1.5 line-through decoration-muted-foreground/30">{before}</p>
      <p className="text-base font-semibold mt-0.5">{after}</p>
    </div>
  );
}
