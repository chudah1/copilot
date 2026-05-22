"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import { api } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";
import type { Holding, OnboardingState, PortfolioSummary, SimulateTradeResponse, Thesis } from "@/types";

function pct(v: number) {
  return `${v.toFixed(1)}%`;
}

function cleanTicker(ticker: string) {
  return ticker.replace(/_US_EQ$/, "").replace(/_EQ$/, "");
}

function getMonitorability(thesis: Thesis | null | undefined) {
  const value = thesis?.interpretation && typeof thesis.interpretation.monitorability === "string"
    ? thesis.interpretation.monitorability
    : null;
  return value === "high" || value === "medium" || value === "low" ? value : null;
}

function getTradeIntervention(
  result: SimulateTradeResponse,
  holdings: Holding[],
  theses: Thesis[],
  investorProfile: "thesis_driven" | "hearsay_driven" | null,
) {
  const matchingHolding = holdings.find((holding) => cleanTicker(holding.ticker) === cleanTicker(result.ticker));
  const currentThesis = matchingHolding
    ? theses.find(
        (thesis) =>
          thesis.holding_id === matchingHolding.id &&
          (thesis.status === "draft" || thesis.status === "active" || thesis.status === "needs_review"),
      ) ?? null
    : null;
  const monitorability = getMonitorability(currentThesis);
  const ambiguityNote =
    currentThesis?.interpretation && typeof currentThesis.interpretation.ambiguity_note === "string"
      ? currentThesis.interpretation.ambiguity_note
      : "";

  if (matchingHolding && currentThesis?.status === "needs_review") {
    return {
      tone: "border-red-500/25 bg-red-500/6 text-red-700",
      eyebrow: "Before you add more",
      title:
        investorProfile === "hearsay_driven"
          ? "This story already has unresolved evidence against it."
          : "This thesis already needs review.",
      body:
        investorProfile === "hearsay_driven"
          ? "Adding here means increasing a position before you decide whether the original story is still real."
          : "Adding here means increasing a position before you resolve evidence that may weaken or break a thesis pillar.",
      ctaLabel: "Review this position first →",
      ctaHref: `/dashboard/positions/${result.ticker}`,
      softenSecondary: true,
    };
  }

  if (matchingHolding && !currentThesis) {
    return {
      tone: "border-amber-500/25 bg-amber-500/6 text-amber-800",
      eyebrow: "Before you add more",
      title:
        investorProfile === "hearsay_driven"
          ? "You are increasing a position with no written reason."
          : "You're adding size to a position with no written thesis.",
      body:
        investorProfile === "hearsay_driven"
          ? "That makes it much easier to average into a story without noticing what would prove you wrong."
          : "Hard to know if you're adding to a real case or just reacting to price and headlines.",
      ctaLabel: "Add it and write the reason →",
      ctaHref: null,
      softenSecondary: true,
    };
  }

  if (matchingHolding && currentThesis && (monitorability === "low" || ambiguityNote)) {
    return {
      tone: "border-sky-500/25 bg-sky-500/6 text-sky-800",
      eyebrow: "Before you size up",
      title:
        investorProfile === "hearsay_driven"
          ? "The current reason is still too story-like."
          : "The current thesis is still too vague.",
      body:
        ambiguityNote ||
        (investorProfile === "hearsay_driven"
          ? "Tighten what has to show up in the business results before you commit more capital."
          : "Tighten the assumption set before you commit more capital to this name."),
      ctaLabel: "Tighten it on the position page →",
      ctaHref: `/dashboard/positions/${result.ticker}`,
      softenSecondary: false,
    };
  }

  return {
    tone: "border-border bg-card text-foreground/80",
    eyebrow: "Decision check",
    title:
      investorProfile === "hearsay_driven"
        ? "Can you name what would prove the story is real?"
        : "Can you state what must remain true before this becomes a position?",
    body:
      investorProfile === "hearsay_driven"
        ? "If you cannot tie this idea to business results you expect to see, the safer move is to add it with a written reason immediately."
        : "If you can't state why you own it, what has to stay true, and what would make you sell, treat this as a draft idea — not a full-size add.",
    ctaLabel:
      investorProfile === "hearsay_driven"
        ? `Add ${cleanTicker(result.ticker)} & write the reason`
        : `Add ${cleanTicker(result.ticker)} & write the thesis`,
    ctaHref: null,
    softenSecondary: false,
  };
}

// ── Trade verdict ─────────────────────────────────────────────────────────────

function gradeTheTrade(result: SimulateTradeResponse): {
  grade: string;
  dot: string;
  headline: string;
  detail: string;
  borderClass: string;
  labelClass: string;
} {
  const w = result.warnings;
  const concAfter = result.after.top_3_concentration_pct;
  const concDelta = concAfter - result.before.top_3_concentration_pct;

  if (w.length === 0 && concDelta <= 2) {
    return { grade: "A", dot: "bg-emerald-500", headline: "Clean entry.", detail: "No concentration warnings. This fits your portfolio well.", borderClass: "border-emerald-500/30", labelClass: "text-emerald-700" };
  }
  if (w.length <= 1 && concDelta <= 5) {
    return { grade: "B", dot: "bg-sky-500", headline: "Looks reasonable.", detail: "Minor considerations but nothing alarming.", borderClass: "border-sky-500/30", labelClass: "text-sky-700" };
  }
  if (w.some((x) => x.warning_type === "concentration_risk")) {
    return { grade: "C", dot: "bg-amber-400", headline: "Concentration risk.", detail: `This would make your top positions drive ${pct(concAfter)} of your portfolio.`, borderClass: "border-amber-400/30", labelClass: "text-amber-700" };
  }
  return { grade: "D", dot: "bg-red-500", headline: "Proceed with caution.", detail: `${w.length} warning${w.length !== 1 ? "s" : ""} flagged. Think this through.`, borderClass: "border-red-500/30", labelClass: "text-red-600" };
}

// ── Donut chart ───────────────────────────────────────────────────────────────

// Earthy palette matching the mahogany design system
const PALETTE = ["#73321f", "#9b5035", "#b8704e", "#c98e6e", "#5a2515", "#8c5a3a", "#a87855", "#d4aa80"];

function DonutChart({ breakdown, label, size = 96 }: { breakdown: Record<string, number>; label: string; size?: number }) {
  const sorted = Object.entries(breakdown).sort(([, a], [, b]) => b - a);
  if (sorted.length === 0) return null;

  const stops = sorted.reduce<string[]>((segments, [, val], i) => {
    const start = sorted.slice(0, i).reduce((total, [, current]) => total + current, 0);
    segments.push(`${PALETTE[i % PALETTE.length]} ${start.toFixed(1)}% ${(start + val).toFixed(1)}%`);
    return segments;
  }, []);

  return (
    <div className="flex flex-col items-center gap-3">
      <div
        style={{
          width: size, height: size,
          background: `conic-gradient(${stops.join(", ")})`,
          mask: "radial-gradient(circle, transparent 52%, black 53%)",
          WebkitMask: "radial-gradient(circle, transparent 52%, black 53%)",
        }}
      />
      <p className="font-mono text-[9px] uppercase tracking-[0.2em] text-muted-foreground">{label}</p>
      <div className="flex flex-wrap justify-center gap-x-3 gap-y-1">
        {sorted.map(([name, val], i) => (
          <span key={name} className="flex items-center gap-1.5 font-mono text-[10px] text-muted-foreground">
            <span className="h-1.5 w-1.5 rounded-full shrink-0" style={{ backgroundColor: PALETTE[i % PALETTE.length] }} />
            {name} {pct(val)}
          </span>
        ))}
      </div>
    </div>
  );
}

// ── Narrative sentences ───────────────────────────────────────────────────────

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

// ── Page ──────────────────────────────────────────────────────────────────────

export default function SimulatePage() {
  const router = useRouter();
  const [ticker, setTicker] = useState("");
  const [quantity, setQuantity] = useState("");
  const [price, setPrice] = useState("");
  const [loading, setLoading] = useState(false);
  const [adding, setAdding] = useState(false);
  const [result, setResult] = useState<SimulateTradeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [summary, setSummary] = useState<PortfolioSummary | null>(null);
  const [holdings, setHoldings] = useState<Holding[]>([]);
  const [theses, setTheses] = useState<Thesis[]>([]);
  const [onboardingState, setOnboardingState] = useState<OnboardingState | null>(null);

  useEffect(() => {
    Promise.all([
      api.get<PortfolioSummary>("/api/portfolio/summary"),
      api.get<Holding[]>("/api/portfolio/holdings"),
      api.get<Thesis[]>("/api/theses/current").catch(() => []),
      api.get<OnboardingState>("/api/onboarding/state").catch(() => null),
    ]).then(([s, h, t, onboarding]) => {
      setSummary(s);
      setHoldings(h);
      setTheses(t);
      setOnboardingState(onboarding);
    }).catch(() => {});
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
  const intervention = result
    ? getTradeIntervention(result, holdings, theses, onboardingState?.investor_profile ?? null)
    : null;
  const topHoldings = [...holdings]
    .filter((h) => h.current_value != null)
    .sort((a, b) => (b.current_value ?? 0) - (a.current_value ?? 0))
    .slice(0, 5);

  return (
    <div className="max-w-xl mx-auto px-6 py-10">

      {/* ── Header ── */}
      <div className="mb-8">
        <Link href="/dashboard" className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground hover:text-primary transition-colors">
          ← Portfolio
        </Link>
        <h1 className="font-display italic text-[2.8rem] leading-none text-foreground mt-3">
          What if&hellip;
        </h1>
      </div>

      {/* ── Input sentence ── */}
      <div className="border border-border bg-card px-5 py-6 space-y-5 mb-8">
        <div className="flex items-baseline gap-2 text-base text-foreground/80 flex-wrap font-sans">
          <span>I buy</span>
          <input
            type="number"
            placeholder="10"
            value={quantity}
            onChange={(e) => setQuantity(e.target.value)}
            className="w-14 border-b border-foreground/25 bg-transparent text-center text-foreground font-mono text-base outline-none focus:border-primary pb-0.5 transition-colors"
          />
          <span>shares of</span>
          <input
            placeholder="NVDA"
            value={ticker}
            onChange={(e) => setTicker(e.target.value)}
            className="w-20 border-b border-foreground/25 bg-transparent text-center text-foreground font-mono text-base uppercase outline-none focus:border-primary pb-0.5 transition-colors"
          />
          <span>at</span>
          <input
            type="number"
            step="0.01"
            placeholder="135"
            value={price}
            onChange={(e) => setPrice(e.target.value)}
            className="w-20 border-b border-foreground/25 bg-transparent text-center text-foreground font-mono text-base outline-none focus:border-primary pb-0.5 transition-colors"
          />
          <span>each.</span>
        </div>

        <button
          onClick={handleSimulate}
          disabled={loading || !ticker || !quantity || !price}
          className="font-mono text-[10px] uppercase tracking-[0.2em] bg-primary text-primary-foreground px-5 py-2.5 hover:bg-primary/90 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {loading ? "Thinking…" : "Show me the impact"}
        </button>

        {error && (
          <p className="font-sans text-sm text-red-600">{error}</p>
        )}
      </div>

      {/* ── Pre-simulation: current portfolio ── */}
      <AnimatePresence mode="wait">
        {!result && summary && (
          <motion.div
            key="pre"
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.25 }}
            className="space-y-5"
          >
            {/* Current stats */}
            <div className="border border-border bg-card divide-y divide-border/40">
              <div className="px-5 py-3">
                <p className="font-mono text-[9px] uppercase tracking-[0.3em] text-muted-foreground">
                  Your portfolio right now
                </p>
              </div>
              <div className="grid grid-cols-3 divide-x divide-border/40">
                {[
                  { label: "Total value", value: formatCurrency(summary.total_value), accent: false },
                  { label: "Holdings", value: String(summary.holdings_count), accent: false },
                  { label: "Top 3 conc.", value: pct(summary.top_3_concentration_pct), accent: summary.top_3_concentration_pct >= 50 },
                ].map(({ label, value, accent }) => (
                  <div key={label} className="px-5 py-4 text-center">
                    <p className={`font-mono text-xl tabular-nums font-medium ${accent ? "text-amber-700" : "text-foreground"}`}>
                      {value}
                    </p>
                    <p className="font-mono text-[9px] uppercase tracking-[0.15em] text-muted-foreground mt-1">{label}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* Sector + top holdings */}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              {Object.keys(summary.sector_breakdown).length > 0 && (
                <div className="border border-border bg-card px-5 py-5 flex items-center justify-center min-h-[180px]">
                  <DonutChart breakdown={summary.sector_breakdown} label="Sector allocation" size={96} />
                </div>
              )}

              {topHoldings.length > 0 && (
                <div className="border border-border bg-card px-5 py-5 space-y-3">
                  <p className="font-mono text-[9px] uppercase tracking-[0.25em] text-muted-foreground">
                    Largest positions
                  </p>
                  <div className="space-y-2.5">
                    {topHoldings.map((h) => {
                      const weight = summary.total_value > 0 ? ((h.current_value ?? 0) / summary.total_value) * 100 : 0;
                      return (
                        <div key={h.id} className="flex items-center gap-3">
                          <span className="font-mono text-[11px] font-medium text-foreground w-14 shrink-0">
                            {cleanTicker(h.ticker)}
                          </span>
                          <div className="flex-1 h-px bg-border overflow-hidden">
                            <div
                              className="h-full bg-primary/40 transition-all"
                              style={{ width: `${Math.min(weight * 1.2, 100)}%` }}
                            />
                          </div>
                          <span className="font-mono text-[10px] text-muted-foreground tabular-nums w-10 text-right shrink-0">
                            {pct(weight)}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>

            <p className="font-mono text-[9px] text-center text-muted-foreground/50 uppercase tracking-[0.15em]">
              Simulate a trade above to see how it shifts your portfolio
            </p>
          </motion.div>
        )}

        {/* ── Post-simulation results ── */}
        {result && verdict && (
          <motion.div
            key="post"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.3 }}
            className="space-y-6"
          >
            {/* Verdict */}
            <div className={`border-l-4 ${verdict.borderClass} pl-5 py-2 flex items-start gap-4`}>
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className={`h-2 w-2 rounded-full shrink-0 ${verdict.dot}`} />
                  <p className={`font-mono text-[10px] uppercase tracking-[0.2em] ${verdict.labelClass}`}>
                    Grade {verdict.grade}
                  </p>
                </div>
                <p className="font-display italic text-xl text-foreground">{verdict.headline}</p>
                <p className="font-sans text-sm text-muted-foreground leading-relaxed">{verdict.detail}</p>
              </div>
            </div>

            {/* Narrative */}
            <div className="space-y-1.5">
              {narrative.map((line, i) => (
                <p key={i} className="font-sans text-sm text-muted-foreground leading-relaxed">{line}</p>
              ))}
            </div>

            {/* Warnings */}
            {result.warnings.length > 0 && (
              <div className="space-y-2">
                {result.warnings.map((w, i) => (
                  <div key={i} className={`border-l-2 pl-4 py-2 ${
                    w.warning_type === "missing_thesis"
                      ? "border-l-sky-400 bg-sky-500/5"
                      : "border-l-amber-400 bg-amber-500/5"
                  }`}>
                    <p className={`font-sans text-sm leading-relaxed ${
                      w.warning_type === "missing_thesis" ? "text-sky-700" : "text-amber-700"
                    }`}>
                      {w.message}
                    </p>
                  </div>
                ))}
              </div>
            )}

            {intervention && (
              <div className={`border px-5 py-4 space-y-3 ${intervention.tone}`}>
                <p className="font-mono text-[9px] uppercase tracking-[0.25em] opacity-80">
                  {intervention.eyebrow}
                </p>
                <div className="space-y-1.5">
                  <p className="font-display italic text-xl text-foreground">{intervention.title}</p>
                  <p className="font-sans text-sm leading-relaxed text-current/90">{intervention.body}</p>
                </div>
                {intervention.ctaHref && (
                  <Link
                    href={intervention.ctaHref}
                    className="inline-flex font-mono text-[10px] uppercase tracking-[0.15em] text-primary hover:text-primary/80 transition-colors"
                  >
                    {intervention.ctaLabel}
                  </Link>
                )}
              </div>
            )}

            {/* Before / after numbers */}
            <div className="border border-border bg-card divide-y divide-border/40">
              <div className="grid grid-cols-4 divide-x divide-border/40">
                <div className="px-3 py-2" />
                {["Before", "After", "Δ"].map((h) => (
                  <div key={h} className="px-3 py-2 text-right">
                    <p className="font-mono text-[9px] uppercase tracking-[0.2em] text-muted-foreground">{h}</p>
                  </div>
                ))}
              </div>
              {[
                {
                  label: "Portfolio",
                  before: formatCurrency(result.before.total_value),
                  after: formatCurrency(result.after.total_value),
                  delta: `+${formatCurrency(result.after.total_value - result.before.total_value)}`,
                  positive: true,
                },
                {
                  label: "Holdings",
                  before: String(result.before.holdings_count),
                  after: String(result.after.holdings_count),
                  delta: result.after.holdings_count > result.before.holdings_count ? "+1 new" : "—",
                  positive: result.after.holdings_count > result.before.holdings_count,
                },
                {
                  label: "Top 3 conc.",
                  before: pct(result.before.top_3_concentration_pct),
                  after: pct(result.after.top_3_concentration_pct),
                  delta: `${result.after.top_3_concentration_pct > result.before.top_3_concentration_pct ? "+" : ""}${(result.after.top_3_concentration_pct - result.before.top_3_concentration_pct).toFixed(1)}%`,
                  positive: result.after.top_3_concentration_pct <= result.before.top_3_concentration_pct,
                },
              ].map(({ label, before, after, delta, positive }) => (
                <div key={label} className="grid grid-cols-4 divide-x divide-border/40">
                  <div className="px-3 py-3">
                    <p className="font-mono text-[10px] text-muted-foreground">{label}</p>
                  </div>
                  <div className="px-3 py-3 text-right">
                    <p className="font-mono text-[11px] text-muted-foreground/50 line-through decoration-muted-foreground/30 tabular-nums">{before}</p>
                  </div>
                  <div className="px-3 py-3 text-right">
                    <p className="font-mono text-[11px] text-foreground tabular-nums font-medium">{after}</p>
                  </div>
                  <div className="px-3 py-3 text-right">
                    <p className={`font-mono text-[10px] tabular-nums ${positive ? "text-emerald-700" : "text-amber-700"}`}>{delta}</p>
                  </div>
                </div>
              ))}
            </div>

            {/* Sector comparison */}
            {(Object.keys(result.before.sector_breakdown).length > 0 || Object.keys(result.after.sector_breakdown).length > 0) && (
              <div className="border border-border bg-card px-5 py-5 space-y-4">
                <p className="font-mono text-[9px] uppercase tracking-[0.3em] text-muted-foreground">
                  Sector allocation shift
                </p>
                <div className="grid grid-cols-2 gap-6">
                  <DonutChart breakdown={result.before.sector_breakdown} label="Before" size={88} />
                  <DonutChart breakdown={result.after.sector_breakdown} label={`After +${cleanTicker(result.ticker)}`} size={88} />
                </div>
              </div>
            )}

            {/* CTAs */}
            <div className="border border-border bg-card px-5 py-5 space-y-3">
              <p className="font-mono text-[9px] uppercase tracking-[0.25em] text-muted-foreground">
                Ready to commit?
              </p>
              <div className="flex flex-col gap-2 sm:flex-row">
                <button
                  onClick={() => addHolding("thesis")}
                  disabled={adding}
                  className="flex-1 font-mono text-[10px] uppercase tracking-[0.15em] bg-primary text-primary-foreground px-4 py-3 hover:bg-primary/90 transition-colors disabled:opacity-40"
                >
                  {adding
                    ? "Adding…"
                    : intervention?.ctaHref === null
                      ? intervention.ctaLabel
                      : `Add ${cleanTicker(result.ticker)} & write thesis`}
                </button>
                <button
                  onClick={() => addHolding("dashboard")}
                  disabled={adding}
                  className={`flex-1 font-mono text-[10px] uppercase tracking-[0.15em] border px-4 py-3 transition-colors disabled:opacity-40 ${
                    intervention?.softenSecondary
                      ? "border-border text-foreground/45 hover:text-foreground/60 hover:border-foreground/25"
                      : "border-border text-foreground/70 hover:text-foreground hover:border-foreground/40"
                  }`}
                >
                  Just add it
                </button>
              </div>
            </div>

            <p className="text-center">
              <Link href="/dashboard" className="font-mono text-[9px] uppercase tracking-[0.2em] text-muted-foreground/50 hover:text-primary transition-colors">
                ← Back to portfolio
              </Link>
            </p>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
