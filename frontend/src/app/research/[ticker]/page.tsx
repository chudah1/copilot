"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { AlertTriangle, Eye, Shield, TrendingDown, ArrowRight, CheckCircle } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatCurrency } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
    <div className="min-h-[calc(100vh-54px)] px-4 sm:px-8 py-8 max-w-2xl mx-auto">
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}>
        <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground mb-2">
          Pre-Buy Stress Test
        </p>
        <h1 className="font-display italic text-[2.4rem] leading-none text-foreground mb-1">
          {ticker}
        </h1>
        <p className="font-sans text-sm text-muted-foreground mb-8">
          Before you buy — let&apos;s stress-test the case against it.
        </p>
      </motion.div>

      {/* Input form */}
      <AnimatePresence mode="wait">
        {!result && (
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
                Your draft thesis <span className="normal-case">(optional — makes the analysis sharper)</span>
              </label>
              <textarea
                className="w-full min-h-[120px] border border-border bg-card rounded-[0.2rem] px-3 py-2 font-sans text-sm text-foreground placeholder:text-muted-foreground/60 focus:outline-none focus:border-foreground/30 resize-none"
                placeholder={`Why are you considering ${ticker}? E.g. "I think their AI chip dominance gives them pricing power for the next 3 years..."`}
                value={draftThesis}
                onChange={(e) => setDraftThesis(e.target.value)}
              />
            </div>

            <Button
              onClick={runStressTest}
              disabled={loading}
              className="w-full"
            >
              {loading ? (
                <span className="font-mono text-[11px] uppercase tracking-[0.15em]">Analysing...</span>
              ) : (
                <span className="font-mono text-[11px] uppercase tracking-[0.15em]">Run Stress Test</span>
              )}
            </Button>

            {!isAuthenticated && (
              <p className="font-mono text-[10px] text-muted-foreground/70 text-center">
                1 free stress test per session · <button onClick={() => router.push("/login")} className="underline hover:text-foreground transition-colors">Sign in</button> for unlimited
              </p>
            )}
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
            {result.current_price && (
              <p className="font-mono text-[11px] text-muted-foreground">
                Current price: <span className="text-foreground tabular-nums">{formatCurrency(result.current_price, result.currency)}</span>
                {result.cached && <span className="ml-2 text-muted-foreground/60">(cached)</span>}
              </p>
            )}

            <StressSection
              icon={<TrendingDown className="w-4 h-4" />}
              label="Bear Case"
              delay={0.05}
            >
              <p className="font-sans text-sm text-foreground leading-relaxed">{result.bear_case}</p>
            </StressSection>

            <StressSection
              icon={<AlertTriangle className="w-4 h-4" />}
              label="Key Risks"
              delay={0.12}
            >
              <ul className="space-y-2">
                {result.key_risks.map((risk, i) => (
                  <li key={i} className="flex gap-2 font-sans text-sm text-foreground">
                    <span className="font-mono text-[10px] text-muted-foreground mt-0.5 shrink-0">{String(i + 1).padStart(2, "0")}</span>
                    {risk}
                  </li>
                ))}
              </ul>
            </StressSection>

            {result.blind_spots.length > 0 && (
              <StressSection
                icon={<Eye className="w-4 h-4" />}
                label="Blind Spots"
                delay={0.19}
              >
                <ul className="space-y-2">
                  {result.blind_spots.map((spot, i) => (
                    <li key={i} className="flex gap-2 font-sans text-sm text-foreground">
                      <span className="text-amber-600 shrink-0 mt-0.5">→</span>
                      {spot}
                    </li>
                  ))}
                </ul>
              </StressSection>
            )}

            <StressSection
              icon={<Shield className="w-4 h-4" />}
              label="What to Watch"
              delay={0.26}
            >
              <ul className="space-y-2">
                {result.what_to_watch.map((signal, i) => (
                  <li key={i} className="flex gap-2 font-sans text-sm text-foreground">
                    <CheckCircle className="w-3.5 h-3.5 text-emerald-600 shrink-0 mt-0.5" />
                    {signal}
                  </li>
                ))}
              </ul>
            </StressSection>

            {/* Conversion CTA */}
            <motion.div
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.35 }}
            >
              <Card className="border-primary/20 bg-primary/5">
                <CardHeader className="pb-2">
                  <CardTitle className="font-display italic text-[1.2rem]">
                    Monitor {ticker} once you buy
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <p className="font-sans text-sm text-muted-foreground">
                    We&apos;ll alert you when something threatens or confirms this thesis — earnings misses, management changes, metric breaches.
                  </p>
                  <div className="flex gap-2">
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
                    className="w-full font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground hover:text-foreground transition-colors"
                  >
                    Run another test
                  </button>
                </CardContent>
              </Card>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function StressSection({
  icon,
  label,
  delay,
  children,
}: {
  icon: React.ReactNode;
  label: string;
  delay: number;
  children: React.ReactNode;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay }}
    >
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-[0.15em] text-muted-foreground font-normal">
            {icon}
            {label}
          </CardTitle>
        </CardHeader>
        <CardContent>{children}</CardContent>
      </Card>
    </motion.div>
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
        className="max-w-sm w-full"
      >
        <Card>
          <CardHeader>
            <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground mb-1">
              Free limit reached
            </p>
            <CardTitle className="font-display italic text-[1.6rem]">
              Monitor {ticker} instead
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="font-sans text-sm text-muted-foreground">
              You&apos;ve used your free stress test. Create a free account to run unlimited tests and get alerted when your thesis is challenged.
            </p>
            <Button onClick={onRegister} className="w-full">
              <span className="font-mono text-[11px] uppercase tracking-[0.15em]">Create free account</span>
              <ArrowRight className="w-3.5 h-3.5 ml-2" />
            </Button>
            <Button variant="outline" onClick={onLogin} className="w-full">
              <span className="font-mono text-[11px] uppercase tracking-[0.15em]">Sign in</span>
            </Button>
          </CardContent>
        </Card>
      </motion.div>
    </div>
  );
}
