"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { AlertTriangle, Eye, Shield, TrendingDown, ArrowRight, CheckCircle } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatCurrency } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import type { StressTestResult } from "@/types";

const SESSION_KEY = "stress_test_used";

export default function ResearchPage() {
  const params = useParams();
  const router = useRouter();
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const ticker = (params.ticker as string).toUpperCase();

  const [draftThesis, setDraftThesis] = useState("");
  const [result, setResult] = useState<StressTestResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [showGate, setShowGate] = useState(false);

  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      const used = sessionStorage.getItem(SESSION_KEY);
      if (used) setShowGate(true);
    }
  }, [authLoading, isAuthenticated]);

  async function runStressTest() {
    if (!isAuthenticated) {
      const used = sessionStorage.getItem(SESSION_KEY);
      if (used) {
        setShowGate(true);
        return;
      }
    }

    setLoading(true);
    try {
      const data = await api.post<StressTestResult>("/api/research/stress-test", {
        ticker,
        draft_thesis: draftThesis.trim() || null,
      });
      setResult(data);
      if (!isAuthenticated) {
        sessionStorage.setItem(SESSION_KEY, "1");
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Something went wrong";
      if (msg.includes("429")) {
        toast.error("Too many requests — try again in an hour.");
      } else {
        toast.error(msg);
      }
    } finally {
      setLoading(false);
    }
  }

  if (showGate && !isAuthenticated) {
    return <GatePage ticker={ticker} onLogin={() => router.push("/login")} onRegister={() => router.push("/register")} />;
  }

  return (
    <div className="min-h-[calc(100vh-54px)] px-4 sm:px-8 py-10 max-w-2xl mx-auto">

      {/* Header */}
      <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}>
        <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground mb-2">
          Pre-Buy Stress Test
        </p>
        <h1 className="font-display italic text-[2.8rem] leading-none text-foreground mb-2">
          {ticker}
        </h1>
        <p className="font-sans text-sm text-muted-foreground mb-8">
          Before you buy — stress-test the case against it.
        </p>
      </motion.div>

      {/* Input form */}
      <AnimatePresence mode="wait">
        {!result && !loading && (
          <motion.div
            key="form"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.25, delay: 0.1 }}
            className="space-y-4"
          >
            <div>
              <label className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground block mb-2">
                Your draft thesis{" "}
                <span className="normal-case tracking-normal opacity-60">(optional — sharpens the analysis)</span>
              </label>
              <textarea
                className="w-full min-h-[120px] border border-border bg-card px-3 py-2.5 font-sans text-sm text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:border-foreground/30 resize-none"
                placeholder={`Why are you considering ${ticker}? E.g. "Their AI chip dominance gives them pricing power for the next 3 years..."`}
                value={draftThesis}
                onChange={(e) => setDraftThesis(e.target.value)}
              />
            </div>

            <Button onClick={runStressTest} loading={loading} className="w-full">
              <span className="font-mono text-[11px] uppercase tracking-[0.15em]">Run Stress Test</span>
            </Button>

            {!isAuthenticated && (
              <p className="font-mono text-[10px] text-muted-foreground/60 text-center">
                1 free test per session ·{" "}
                <button
                  onClick={() => router.push("/login")}
                  className="underline underline-offset-2 hover:text-foreground transition-colors"
                >
                  Sign in
                </button>{" "}
                for unlimited
              </p>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Loading skeleton */}
      <AnimatePresence>
        {loading && (
          <motion.div
            key="skeleton"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="space-y-4"
          >
            <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground/60 mb-6 flex items-center gap-2">
              <span className="inline-block w-1.5 h-1.5 rounded-full bg-primary animate-pulse" />
              Analysing {ticker}…
            </div>
            {[{ w: "w-full", h: "h-28" }, { w: "w-full", h: "h-36" }, { w: "w-3/4", h: "h-20" }].map((s, i) => (
              <div key={i} className={`border border-border/40 bg-card p-5 ${s.h} animate-pulse`}>
                <div className="h-2 w-20 bg-muted rounded mb-3" />
                <div className={`${s.w} h-3 bg-muted/60 rounded`} />
              </div>
            ))}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Results */}
      <AnimatePresence>
        {result && (
          <motion.div
            key="results"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.3 }}
            className="space-y-4"
          >
            {/* Price line */}
            {result.current_price && (
              <p className="font-mono text-[11px] text-muted-foreground/70">
                {ticker} ·{" "}
                <span className="text-foreground tabular-nums">{formatCurrency(result.current_price, result.currency)}</span>
                {result.cached && <span className="ml-2 opacity-50">(cached)</span>}
              </p>
            )}

            {/* Bear case — lead section, visually prominent */}
            <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }}>
              <div className="border border-border/80 bg-card p-5">
                <p className="font-mono text-[9px] uppercase tracking-[0.25em] text-muted-foreground/60 mb-3 flex items-center gap-2">
                  <TrendingDown className="w-3 h-3" />
                  Bear Case
                </p>
                <p className="font-display italic text-[1.35rem] leading-snug text-foreground">
                  {result.bear_case}
                </p>
              </div>
            </motion.div>

            {/* Key risks */}
            <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.12 }}>
              <div className="border border-border/60 bg-card p-5">
                <p className="font-mono text-[9px] uppercase tracking-[0.25em] text-muted-foreground/60 mb-3 flex items-center gap-2">
                  <AlertTriangle className="w-3 h-3" />
                  Key Risks
                </p>
                <ul className="space-y-3">
                  {result.key_risks.map((risk, i) => (
                    <li key={i} className="flex gap-3">
                      <span className="font-mono text-[10px] text-muted-foreground/40 tabular-nums shrink-0 mt-0.5 w-4">
                        {String(i + 1).padStart(2, "0")}
                      </span>
                      <span className="font-sans text-sm text-foreground/85 leading-relaxed">{risk}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </motion.div>

            {/* Blind spots */}
            {result.blind_spots.length > 0 && (
              <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.19 }}>
                <div className="border border-amber-500/25 bg-amber-500/5 p-5">
                  <p className="font-mono text-[9px] uppercase tracking-[0.25em] text-amber-700/70 mb-3 flex items-center gap-2">
                    <Eye className="w-3 h-3" />
                    Blind Spots
                  </p>
                  <ul className="space-y-3">
                    {result.blind_spots.map((spot, i) => (
                      <li key={i} className="flex gap-3">
                        <span className="text-amber-600/70 shrink-0 mt-0.5 font-mono text-[10px]">→</span>
                        <span className="font-sans text-sm text-foreground/85 leading-relaxed">{spot}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </motion.div>
            )}

            {/* What to watch */}
            <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.26 }}>
              <div className="border border-border/60 bg-card p-5">
                <p className="font-mono text-[9px] uppercase tracking-[0.25em] text-muted-foreground/60 mb-3 flex items-center gap-2">
                  <Shield className="w-3 h-3" />
                  What to Watch
                </p>
                <ul className="space-y-3">
                  {result.what_to_watch.map((signal, i) => (
                    <li key={i} className="flex gap-3">
                      <CheckCircle className="w-3.5 h-3.5 text-emerald-600 shrink-0 mt-0.5" />
                      <span className="font-sans text-sm text-foreground/85 leading-relaxed">{signal}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </motion.div>

            {/* Conversion CTA */}
            <motion.div
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.33 }}
              className="border border-primary/25 bg-primary/5 p-5 space-y-3"
            >
              <div>
                <p className="font-mono text-[9px] uppercase tracking-[0.2em] text-primary/70 mb-1">
                  Next step
                </p>
                <p className="font-display italic text-[1.3rem] text-foreground leading-snug">
                  Monitor {ticker} once you buy
                </p>
              </div>
              <p className="font-sans text-sm text-muted-foreground leading-relaxed">
                We&apos;ll alert you when something threatens or confirms this thesis — earnings misses, management changes, metric breaches.
              </p>
              <div className="flex gap-2 pt-1">
                <Button onClick={() => router.push("/register")} className="flex-1">
                  <span className="font-mono text-[11px] uppercase tracking-[0.15em]">Create free account</span>
                  <ArrowRight className="w-3.5 h-3.5 ml-2" />
                </Button>
                {!isAuthenticated && (
                  <Button variant="outline" onClick={() => router.push("/login")} className="flex-1">
                    <span className="font-mono text-[11px] uppercase tracking-[0.15em]">Sign in</span>
                  </Button>
                )}
              </div>
              <button
                onClick={() => setResult(null)}
                className="w-full font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground/60 hover:text-muted-foreground transition-colors pt-1"
              >
                Run another test →
              </button>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function GatePage({
  ticker,
  onLogin,
  onRegister,
}: {
  ticker: string;
  onLogin: () => void;
  onRegister: () => void;
}) {
  return (
    <div className="min-h-[calc(100vh-54px)] flex items-center justify-center px-4">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        className="max-w-sm w-full border border-border/60 bg-card p-7 space-y-4"
      >
        <div>
          <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground mb-2">
            Free limit reached
          </p>
          <h2 className="font-display italic text-[1.8rem] leading-tight text-foreground">
            Monitor {ticker} instead
          </h2>
        </div>
        <p className="font-sans text-sm text-muted-foreground leading-relaxed">
          You&apos;ve used your free stress test. Create an account to run unlimited tests and get alerted when your thesis is challenged.
        </p>
        <div className="space-y-2 pt-1">
          <Button onClick={onRegister} className="w-full">
            <span className="font-mono text-[11px] uppercase tracking-[0.15em]">Create free account</span>
            <ArrowRight className="w-3.5 h-3.5 ml-2" />
          </Button>
          <Button variant="outline" onClick={onLogin} className="w-full">
            <span className="font-mono text-[11px] uppercase tracking-[0.15em]">Sign in</span>
          </Button>
        </div>
      </motion.div>
    </div>
  );
}
