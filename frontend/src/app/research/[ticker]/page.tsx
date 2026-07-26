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
  const [showAllSources, setShowAllSources] = useState(false);
  const riskGroups = result?.risk_groups ?? [];
  const sourceNotes = result?.source_notes ?? [];
  const blindSpots = result?.blind_spots ?? [];
  const watchItems = result?.what_to_watch ?? [];
  const candidateSignals = result?.candidate_signals ?? [];

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
                  Stress Test
                </p>
                <h1 className="font-display italic text-[2.8rem] leading-none text-foreground">
                  {ticker}
                </h1>
                <p className="font-sans text-sm text-muted-foreground">
                  See what could go wrong before you buy.
                </p>
              </div>

              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1">
                <div className="border border-border/60 bg-background/70 p-4">
                  <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                    You get
                  </p>
                  <p className="mt-2 font-sans text-sm leading-relaxed text-foreground/80">
                    A direct risk summary, the evidence behind it, and what to check next.
                  </p>
                </div>
                <div className="border border-border/60 bg-background/70 p-4">
                  <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                    Use before
                  </p>
                  <p className="mt-2 font-sans text-sm leading-relaxed text-foreground/80">
                    Buying or adding more.
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
                    Why you are considering it{" "}
                    <span className="normal-case tracking-normal opacity-60">(optional)</span>
                  </label>
                  <textarea
                    className="w-full min-h-[140px] border border-border bg-card px-3 py-2.5 font-sans text-sm text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:border-foreground/30 resize-none"
                    placeholder={`Why buy ${ticker}? What has to go right?`}
                    value={draftThesis}
                    onChange={(e) => setDraftThesis(e.target.value)}
                  />
                </div>

                <div className="flex flex-wrap items-center gap-3">
                  <Button onClick={runStressTest} loading={loading}>
                    <span className="font-mono text-[11px] uppercase tracking-[0.15em]">Run Stress Test</span>
                  </Button>
                  <p className="font-sans text-xs leading-relaxed text-muted-foreground">
                    Leave this blank for a general risk check.
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
                    Better with
                  </p>
                  <ul className="mt-3 space-y-2">
                    {[
                      "Why the business should improve",
                      "What other investors may be missing",
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
                    Result
                  </p>
                  <p className="mt-2 font-sans text-sm leading-relaxed text-foreground/80">
                    A plain-English case against buying.
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

            {/* Bear case — lead section, visually prominent */}
            <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }}>
              <div className="product-panel p-5">
                <p className="font-mono text-[9px] uppercase tracking-[0.25em] text-muted-foreground/60 mb-3 flex items-center gap-2">
                  <TrendingDown className="w-3 h-3" />
                  Read this first
                </p>
                <p className="font-display italic text-[1.35rem] leading-snug text-foreground">
                  {result.bear_case}
                </p>
              </div>
            </motion.div>

            {/* Risk groups */}
            <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.12 }}>
              <div className="product-panel p-5">
                <p className="font-mono text-[9px] uppercase tracking-[0.25em] text-muted-foreground/60 mb-3 flex items-center gap-2">
                  <AlertTriangle className="w-3 h-3" />
                  What could go wrong
                </p>
                {riskGroups.length > 0 ? (
                  <div className="grid gap-3 md:grid-cols-2">
                    {riskGroups.map((group) => (
                      <div key={group.category} className="border border-border/60 bg-background/70 p-4 space-y-3">
                        <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                          {group.category}
                        </p>
                        <ul className="space-y-2.5">
                          {group.items.map((risk, i) => (
                            <li key={`${group.category}:${i}`} className="flex gap-3">
                              <span className="font-mono text-[10px] text-muted-foreground/40 tabular-nums shrink-0 mt-0.5 w-4">
                                {String(i + 1).padStart(2, "0")}
                              </span>
                              <span className="font-sans text-sm text-foreground/85 leading-relaxed">{risk}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="font-sans text-sm text-foreground/80 leading-relaxed">
                    No additional risk groups were returned. Start with the summary above.
                  </p>
                )}
              </div>
            </motion.div>

            {/* Blind spots */}
            <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.19 }}>
              <div className="product-panel p-5 border-amber-500/25 bg-amber-500/5">
                <p className="font-mono text-[9px] uppercase tracking-[0.25em] text-amber-700/70 mb-3 flex items-center gap-2">
                  <Eye className="w-3 h-3" />
                  What you may be missing
                </p>
                {blindSpots.length > 0 ? (
                  <ul className="space-y-3">
                    {blindSpots.map((spot, i) => (
                      <li key={i} className="flex gap-3">
                        <span className="text-amber-600/70 shrink-0 mt-0.5 font-mono text-[10px]">→</span>
                        <span className="font-sans text-sm text-foreground/85 leading-relaxed">{spot}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="font-sans text-sm text-foreground/80 leading-relaxed">
                    Nothing specific was flagged. Add your own reason next time for a more targeted check.
                  </p>
                )}
              </div>
            </motion.div>

            {/* Source notes */}
            <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.23 }}>
              <div className="product-panel p-5">
                <p className="font-mono text-[9px] uppercase tracking-[0.25em] text-muted-foreground/60 mb-3">
                  Evidence used
                </p>
                {sourceNotes.length > 0 ? (
                  <div className="space-y-3">
                    {(showAllSources ? sourceNotes : sourceNotes.slice(0, 3)).map((note, i) => (
                      <div key={`${note.label}:${i}`} className="border border-border/60 bg-background/70 p-3">
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-foreground/75">
                            {note.label}
                          </p>
                          <span className="font-mono text-[9px] uppercase tracking-[0.14em] text-muted-foreground/70">
                            {note.source}
                          </span>
                        </div>
                        <p className="mt-2 font-sans text-sm text-foreground/85 leading-relaxed">
                          {note.detail}
                        </p>
                        {note.url && (
                          <a
                            href={note.url}
                            target="_blank"
                            rel="noreferrer"
                            className="mt-2 inline-block font-mono text-[10px] uppercase tracking-[0.14em] text-primary/70 underline underline-offset-2"
                          >
                            Open source ↗
                          </a>
                        )}
                      </div>
                    ))}
                    {sourceNotes.length > 3 && (
                      <button
                        onClick={() => setShowAllSources((current) => !current)}
                        className="font-mono text-[10px] uppercase tracking-[0.14em] text-primary hover:text-primary/75"
                      >
                        {showAllSources ? "Show less" : `See all ${sourceNotes.length} sources`}
                      </button>
                    )}
                  </div>
                ) : (
                  <p className="font-sans text-sm text-foreground/80 leading-relaxed">
                    No source links were attached to this result.
                  </p>
                )}
              </div>
            </motion.div>

            {/* What to watch */}
            <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.26 }}>
              <div className="product-panel p-5">
                <p className="font-mono text-[9px] uppercase tracking-[0.25em] text-muted-foreground/60 mb-3 flex items-center gap-2">
                  <Shield className="w-3 h-3" />
                  What to check next
                </p>
                {watchItems.length > 0 ? (
                  <ul className="space-y-3">
                    {watchItems.map((signal, i) => (
                      <li key={i} className="flex gap-3">
                        <CheckCircle className="w-3.5 h-3.5 text-emerald-600 shrink-0 mt-0.5" />
                        <span className="font-sans text-sm text-foreground/85 leading-relaxed">{signal}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="font-sans text-sm text-foreground/80 leading-relaxed">
                    No additional checks were returned.
                  </p>
                )}
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
                  If you buy {ticker}, save the reason and keep checking whether it remains true.
                </p>
              </div>
              <p className="font-sans text-sm text-muted-foreground leading-relaxed">
                {isAuthenticated
                  ? "Add the position, write why you own it, and PenKeep will check new evidence against that reason."
                  : "Create an account to save the decision. PenKeep will alert you only when new evidence directly tests something you wrote."}
              </p>
              {candidateSignals.length > 0 && (
                <div className="grid gap-2 sm:grid-cols-2">
                  {candidateSignals.slice(0, 4).map((signal, i) => (
                    <div key={`${signal.label}:${i}`} className="border border-primary/20 bg-background/75 px-3 py-2.5">
                      <p className="font-sans text-sm text-foreground">{signal.label}</p>
                      <p className="mt-1 font-sans text-xs leading-relaxed text-muted-foreground">
                        {signal.rationale || (signal.signal_type === "news_watch" ? "News and filing check." : "Number-based check.")}
                      </p>
                    </div>
                  ))}
                </div>
              )}
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
                Test another ticker →
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
