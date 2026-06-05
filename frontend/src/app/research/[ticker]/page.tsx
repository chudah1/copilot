"use client";

import { useState, useSyncExternalStore } from "react";
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
const SESSION_EVENT = "penkeep:stress-test-session";

function subscribeToSessionUsage(onStoreChange: () => void) {
  if (typeof window === "undefined") {
    return () => {};
  }

  const handleChange = () => onStoreChange();
  window.addEventListener("storage", handleChange);
  window.addEventListener(SESSION_EVENT, handleChange);

  return () => {
    window.removeEventListener("storage", handleChange);
    window.removeEventListener(SESSION_EVENT, handleChange);
  };
}

function getSessionUsageSnapshot() {
  if (typeof window === "undefined") {
    return false;
  }
  return sessionStorage.getItem(SESSION_KEY) === "1";
}

export default function ResearchPage() {
  const params = useParams();
  const router = useRouter();
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const ticker = (params.ticker as string).toUpperCase();
  const hasUsedSessionTest = useSyncExternalStore(
    subscribeToSessionUsage,
    getSessionUsageSnapshot,
    () => false,
  );

  const [draftThesis, setDraftThesis] = useState("");
  const [result, setResult] = useState<StressTestResult | null>(null);
  const [loading, setLoading] = useState(false);
  const hasDraftContext = draftThesis.trim().length > 0;

  const showGate = !authLoading && !isAuthenticated && hasUsedSessionTest;

  async function runStressTest() {
    if (!isAuthenticated) {
      if (hasUsedSessionTest) {
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
        window.dispatchEvent(new Event(SESSION_EVENT));
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
    <div className="min-h-[calc(100vh-54px)] px-4 py-10 sm:px-8">
      <div className="mx-auto max-w-4xl space-y-5">

        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}>
          <div className="product-panel product-panel-muted overflow-hidden p-5 sm:p-6">
            <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(16rem,20rem)]">
              <div className="space-y-2">
                <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                  Pre-Buy Stress Test
                </p>
                <h1 className="font-display italic text-[2.8rem] leading-none text-foreground">
                  {ticker}
                </h1>
                <p className="font-sans text-sm text-muted-foreground">
                  Stress-test the case before you buy.
                </p>
              </div>

              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1">
                <div className="border border-border/60 bg-background/70 p-4">
                  <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                    Output
                  </p>
                  <p className="mt-2 font-sans text-sm leading-relaxed text-foreground/80">
                    Bear case, key risks, blind spots, and what to watch.
                  </p>
                </div>
                <div className="border border-border/60 bg-background/70 p-4">
                  <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                    Best used before
                  </p>
                  <p className="mt-2 font-sans text-sm leading-relaxed text-foreground/80">
                    Buying or sizing up.
                  </p>
                </div>
              </div>
            </div>
          </div>
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
            className="product-panel p-5 sm:p-6"
          >
            <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_17rem]">
              <div className="space-y-4">
                <div>
                  <label className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground block mb-2">
                    Your current case{" "}
                    <span className="normal-case tracking-normal opacity-60">(optional)</span>
                  </label>
                  <textarea
                    className="w-full min-h-[140px] border border-border bg-card px-3 py-2.5 font-sans text-sm text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:border-foreground/30 resize-none"
                    placeholder={`Why are you considering ${ticker}? E.g. "Their AI chip dominance gives them pricing power for the next 3 years..."`}
                    value={draftThesis}
                    onChange={(e) => setDraftThesis(e.target.value)}
                  />
                </div>

                <div className="flex flex-wrap items-center gap-3">
                  <Button onClick={runStressTest} loading={loading}>
                    <span className="font-mono text-[11px] uppercase tracking-[0.15em]">Run Stress Test</span>
                  </Button>
                  <p className="font-sans text-xs leading-relaxed text-muted-foreground">
                    Leave it blank if you just want the bear case.
                  </p>
                </div>

                {!isAuthenticated && (
                  <p className="font-mono text-[10px] text-muted-foreground/60">
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
              </div>

              <aside className="space-y-3">
                <div className="border border-border/60 bg-background/70 p-4">
                  <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                    Stronger with
                  </p>
                  <ul className="mt-3 space-y-2">
                    {[
                      "What has to go right",
                      "Where you think the market is wrong",
                      "What would change your mind",
                    ].map((item, i) => (
                      <li key={item} className="flex gap-2 font-sans text-sm leading-relaxed text-foreground/80">
                        <span className="font-mono text-[10px] text-muted-foreground/50 mt-0.5">
                          {String(i + 1).padStart(2, "0")}
                        </span>
                        <span>{item}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                <div className="border border-border/60 bg-background/70 p-4">
                  <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                    You&apos;ll get
                  </p>
                  <p className="mt-2 font-sans text-sm leading-relaxed text-foreground/80">
                    A fast bear-case memo.
                  </p>
                </div>
              </aside>
            </div>
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
            className="space-y-3"
          >
            <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground/60 mb-6 flex items-center gap-2">
              <span className="inline-block w-1.5 h-1.5 rounded-full bg-primary animate-pulse" />
              Analysing {ticker}…
            </div>
            {[{ w: "w-full", h: "h-28" }, { w: "w-full", h: "h-36" }, { w: "w-3/4", h: "h-20" }].map((s, i) => (
              <div key={i} className={`product-panel p-5 ${s.h} animate-pulse`}>
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
              <p className="font-mono text-[11px] text-muted-foreground/70 flex flex-wrap items-center gap-x-2 gap-y-1">
                {ticker} ·{" "}
                <span className="text-foreground tabular-nums">{formatCurrency(result.current_price, result.currency)}</span>
                {result.cached && <span className="opacity-50">(cached)</span>}
              </p>
            )}

            <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.02 }}>
              <div className="grid gap-3 sm:grid-cols-3">
                <div className="product-panel p-4">
                  <p className="font-mono text-[9px] uppercase tracking-[0.18em] text-muted-foreground/60">
                    Risks flagged
                  </p>
                  <p className="mt-2 font-display text-[1.5rem] italic leading-none text-foreground">
                    {result.key_risks.length}
                  </p>
                </div>
                <div className="product-panel p-4">
                  <p className="font-mono text-[9px] uppercase tracking-[0.18em] text-muted-foreground/60">
                    Blind spots
                  </p>
                  <p className="mt-2 font-display text-[1.5rem] italic leading-none text-foreground">
                    {result.blind_spots.length > 0 ? result.blind_spots.length : "None flagged"}
                  </p>
                </div>
                <div className="product-panel p-4">
                  <p className="font-mono text-[9px] uppercase tracking-[0.18em] text-muted-foreground/60">
                    Read it as
                  </p>
                  <p className="mt-2 font-sans text-sm leading-relaxed text-foreground/80">
                    {hasDraftContext ? "A counter-case against your draft." : "A fast bear-case memo."}
                  </p>
                </div>
              </div>
            </motion.div>

            {/* Bear case — lead section, visually prominent */}
            <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }}>
              <div className="product-panel p-5">
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
              <div className="product-panel p-5">
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
            <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.19 }}>
              <div className="product-panel p-5 border-amber-500/25 bg-amber-500/5">
                <p className="font-mono text-[9px] uppercase tracking-[0.25em] text-amber-700/70 mb-3 flex items-center gap-2">
                  <Eye className="w-3 h-3" />
                  Blind Spots
                </p>
                {result.blind_spots.length > 0 ? (
                  <ul className="space-y-3">
                    {result.blind_spots.map((spot, i) => (
                      <li key={i} className="flex gap-3">
                        <span className="text-amber-600/70 shrink-0 mt-0.5 font-mono text-[10px]">→</span>
                        <span className="font-sans text-sm text-foreground/85 leading-relaxed">{spot}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="font-sans text-sm text-foreground/80 leading-relaxed">
                    No blind spot was flagged from this input. Add your own draft next time for a sharper check.
                  </p>
                )}
              </div>
            </motion.div>

            {/* What to watch */}
            <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.26 }}>
              <div className="product-panel p-5">
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
              className="product-panel p-5 space-y-3 border-primary/25 bg-primary/5"
            >
              <div>
                <p className="font-mono text-[9px] uppercase tracking-[0.2em] text-primary/70 mb-1">
                  Next step
                </p>
                <p className="font-display italic text-[1.3rem] text-foreground leading-snug">
                  {isAuthenticated ? `If you buy ${ticker}, track it from the dashboard` : `Monitor ${ticker} once you buy`}
                </p>
              </div>
              <p className="font-sans text-sm text-muted-foreground leading-relaxed">
                {isAuthenticated
                  ? "Write the thesis and monitor it once it becomes a position."
                  : "We&apos;ll alert you when something threatens or confirms the thesis."}
              </p>
              <div className="flex gap-2 pt-1">
                {isAuthenticated ? (
                  <Button onClick={() => router.push("/dashboard")} className="flex-1">
                    <span className="font-mono text-[11px] uppercase tracking-[0.15em]">Open dashboard</span>
                    <ArrowRight className="w-3.5 h-3.5 ml-2" />
                  </Button>
                ) : (
                  <Button onClick={() => router.push("/register")} className="flex-1">
                    <span className="font-mono text-[11px] uppercase tracking-[0.15em]">Create free account</span>
                    <ArrowRight className="w-3.5 h-3.5 ml-2" />
                  </Button>
                )}
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
        className="product-panel max-w-sm w-full p-7 space-y-4"
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
