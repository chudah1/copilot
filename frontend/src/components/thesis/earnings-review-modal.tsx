"use client";

import { AlertTriangle, ArrowRight, CheckCircle2, LoaderCircle, X } from "lucide-react";
import { useState } from "react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { getErrorMessage } from "@/lib/errors";
import { Button } from "@/components/ui/button";
import type { ClaimVerdict, EarningsReviewResult } from "@/types";

interface EarningsReviewModalProps {
  thesisId: string;
  ticker: string;
  investorProfile?: "thesis_driven" | "hearsay_driven" | null;
  onClose: () => void;
}

const VERDICT_CONFIG: Record<
  ClaimVerdict["verdict"],
  { label: string; tone: string; chip: string; dot: string }
> = {
  holds: {
    label: "Holds",
    tone: "border-emerald-500/25 bg-emerald-500/6",
    chip: "text-emerald-700 bg-emerald-500/10 border-emerald-500/20",
    dot: "bg-emerald-500",
  },
  watch: {
    label: "Watch",
    tone: "border-amber-500/25 bg-amber-500/6",
    chip: "text-amber-700 bg-amber-500/10 border-amber-500/20",
    dot: "bg-amber-500",
  },
  broken: {
    label: "Broken",
    tone: "border-red-500/25 bg-red-500/6",
    chip: "text-red-600 bg-red-500/10 border-red-500/20",
    dot: "bg-red-500",
  },
  unclear: {
    label: "Unclear",
    tone: "border-border/80 bg-background/70",
    chip: "text-muted-foreground bg-muted/50 border-border",
    dot: "bg-muted-foreground/50",
  },
};

function assessmentConfigForProfile(investorProfile?: "thesis_driven" | "hearsay_driven" | null) {
  if (investorProfile === "thesis_driven") {
    return {
      thesis_intact: {
        eyebrow: "Review result",
        label: "Thesis intact",
        tone: "border-emerald-500/25 bg-emerald-500/8",
        chip: "text-emerald-700 bg-emerald-500/10 border-emerald-500/20",
      },
      watch: {
        eyebrow: "Review result",
        label: "Assumption to watch",
        tone: "border-amber-500/25 bg-amber-500/8",
        chip: "text-amber-700 bg-amber-500/10 border-amber-500/20",
      },
      thesis_challenged: {
        eyebrow: "Review result",
        label: "Thesis challenged",
        tone: "border-red-500/25 bg-red-500/8",
        chip: "text-red-600 bg-red-500/10 border-red-500/20",
      },
    } as const;
  }

  return {
    thesis_intact: {
      eyebrow: "Review result",
      label: "Reason intact",
      tone: "border-emerald-500/25 bg-emerald-500/8",
      chip: "text-emerald-700 bg-emerald-500/10 border-emerald-500/20",
    },
    watch: {
      eyebrow: "Review result",
      label: "Worth watching",
      tone: "border-amber-500/25 bg-amber-500/8",
      chip: "text-amber-700 bg-amber-500/10 border-amber-500/20",
    },
    thesis_challenged: {
      eyebrow: "Review result",
      label: investorProfile === "hearsay_driven" ? "Reason challenged" : "Thesis challenged",
      tone: "border-red-500/25 bg-red-500/8",
      chip: "text-red-600 bg-red-500/10 border-red-500/20",
    },
  } as const;
}

function reviewSubtitle(ticker: string, investorProfile?: "thesis_driven" | "hearsay_driven" | null) {
  if (investorProfile === "thesis_driven") {
    return `${ticker} · check whether the thesis still holds up after earnings.`;
  }
  if (investorProfile === "hearsay_driven") {
    return `${ticker} · check whether the original reason still holds up after earnings.`;
  }
  return `${ticker} · check whether your case still holds up after earnings.`;
}

function formatReviewedAt(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(date);
}

function VerdictCard({ verdict }: { verdict: ClaimVerdict }) {
  const config = VERDICT_CONFIG[verdict.verdict] ?? VERDICT_CONFIG.unclear;

  return (
    <div className={cn("product-panel p-4 sm:p-5", config.tone)}>
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 space-y-2">
          <div className="flex items-start gap-3">
            <span className={cn("mt-1 h-2.5 w-2.5 shrink-0 rounded-full", config.dot)} />
            <p className="font-sans text-sm leading-relaxed text-foreground/90">{verdict.claim_text}</p>
          </div>
          <div className="pl-5">
            <p className="font-sans text-sm leading-relaxed text-muted-foreground">{verdict.explanation}</p>
            {verdict.evidence && (
              <p className="mt-2 font-mono text-[10px] uppercase tracking-[0.12em] text-foreground/55">
                Evidence: {verdict.evidence}
              </p>
            )}
          </div>
        </div>
        <span
          className={cn(
            "shrink-0 border px-2 py-1 font-mono text-[10px] uppercase tracking-[0.14em]",
            config.chip,
          )}
        >
          {config.label}
        </span>
      </div>
    </div>
  );
}

export function EarningsReviewModal({
  thesisId,
  ticker,
  investorProfile,
  onClose,
}: EarningsReviewModalProps) {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<EarningsReviewResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const runReview = async () => {
    setLoading(true);
    setError(null);
    try {
      const nextResult = await api.post<EarningsReviewResult>(`/api/theses/${thesisId}/earnings-review`);
      setResult(nextResult);
    } catch (nextError: unknown) {
      setError(getErrorMessage(nextError, "Review failed"));
    } finally {
      setLoading(false);
    }
  };

  const assessmentMap = assessmentConfigForProfile(investorProfile);
  const assessmentConfig = result
    ? assessmentMap[result.overall_assessment] ?? assessmentMap.watch
    : null;
  const verdictCounts = result?.verdicts.reduce(
    (counts, verdict) => {
      counts[verdict.verdict] += 1;
      return counts;
    },
    { holds: 0, watch: 0, broken: 0, unclear: 0 },
  ) ?? { holds: 0, watch: 0, broken: 0, unclear: 0 };
  const reviewedAt = result ? formatReviewedAt(result.reviewed_at) : null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-[rgba(17,15,10,0.58)] p-0 backdrop-blur-[2px] sm:items-center sm:p-6"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="product-panel flex max-h-[92vh] w-full max-w-3xl flex-col overflow-hidden rounded-t-2xl sm:rounded-2xl">
        <div className="flex items-start justify-between gap-4 border-b border-border/70 px-5 py-4 sm:px-6 sm:py-5">
          <div className="space-y-2">
            <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
              Post-earnings review
            </p>
            <div>
              <h2 className="font-display text-[1.9rem] italic leading-none text-foreground sm:text-[2.2rem]">
                Re-read the case
              </h2>
              <p className="mt-2 max-w-2xl font-sans text-sm leading-relaxed text-muted-foreground">
                {reviewSubtitle(ticker, investorProfile)}
              </p>
            </div>
          </div>
          <Button aria-label="Close review" variant="ghost" size="icon-sm" onClick={onClose}>
            <X className="size-4" />
          </Button>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-5 sm:px-6 sm:py-6">
          {!result && !loading && (
            <div className="space-y-5">
              <div className="product-panel border border-border/60 bg-background/82 p-6 sm:p-7">
                <div className="flex items-start gap-3">
                  <div className="mt-0.5 rounded-full border border-primary/20 bg-primary/8 p-2 text-primary">
                    <ArrowRight className="size-4" />
                  </div>
                  <div className="space-y-3">
                    <div>
                      <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                        What this does
                      </p>
                      <p className="mt-2 font-sans text-base leading-relaxed text-foreground/90">
                        Check the latest quarter against the reason you wrote down.
                      </p>
                    </div>
                    <div className="grid gap-3 sm:grid-cols-3">
                      <div className="product-panel p-4">
                        <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
                          Overall call
                        </p>
                        <p className="mt-2 font-sans text-sm leading-relaxed text-foreground/85">
                          Intact, worth watching, or challenged.
                        </p>
                      </div>
                      <div className="product-panel p-4">
                        <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
                          Claim checks
                        </p>
                        <p className="mt-2 font-sans text-sm leading-relaxed text-foreground/85">
                          Each core claim gets its own verdict and evidence line.
                        </p>
                      </div>
                      <div className="product-panel p-4">
                        <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
                          Saved after review
                        </p>
                        <p className="mt-2 font-sans text-sm leading-relaxed text-foreground/85">
                          The result is saved to the decision trail automatically.
                        </p>
                      </div>
                    </div>
                    {error && (
                      <div className="border border-red-500/20 bg-red-500/6 px-4 py-3">
                        <p className="font-sans text-sm text-red-600">{error}</p>
                      </div>
                    )}
                    <div className="flex flex-wrap items-center gap-3">
                      <Button onClick={runReview}>Run review</Button>
                      <p className="font-sans text-sm text-muted-foreground">
                        Best used right after the quarter lands.
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {loading && (
            <div className="product-panel border border-border/60 bg-background/82 flex min-h-[280px] flex-col items-center justify-center gap-4 px-6 py-10 text-center">
              <LoaderCircle className="size-8 animate-spin text-primary" />
              <div className="space-y-2">
                <p className="font-sans text-base text-foreground/90">Checking the latest quarter against your case.</p>
                <p className="font-sans text-sm text-muted-foreground">
                  This usually takes a moment while the review is written and saved.
                </p>
              </div>
            </div>
          )}

          {result && assessmentConfig && (
            <div className="space-y-5">
              <div className={cn("product-panel p-5 sm:p-6", assessmentConfig.tone)}>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="space-y-2">
                    <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-foreground/60">
                      {assessmentConfig.eyebrow}
                    </p>
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="font-display text-[1.7rem] italic leading-none text-foreground">
                        {assessmentConfig.label}
                      </h3>
                      <span className={cn("border px-2 py-1 font-mono text-[10px] uppercase tracking-[0.14em]", assessmentConfig.chip)}>
                        {ticker}
                      </span>
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    {result.fiscal_quarter && (
                      <span className="border border-border/70 bg-background/70 px-2 py-1 font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
                        {result.fiscal_quarter}
                      </span>
                    )}
                    {result.earnings_surprise_pct !== null && (
                      <span className="border border-border/70 bg-background/70 px-2 py-1 font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
                        {result.earnings_surprise_pct > 0 ? "+" : ""}
                        {result.earnings_surprise_pct.toFixed(1)}% surprise
                      </span>
                    )}
                  </div>
                </div>
                <p className="mt-4 font-sans text-sm leading-relaxed text-foreground/88 sm:text-[0.95rem]">
                  {result.summary}
                </p>
                <div className="mt-5 grid gap-3 sm:grid-cols-4">
                  <div className="product-panel border-border/60 bg-background/65 p-4">
                    <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
                      Holds
                    </p>
                    <p className="mt-2 font-display text-[1.45rem] italic leading-none text-emerald-700">
                      {verdictCounts.holds}
                    </p>
                  </div>
                  <div className="product-panel border-border/60 bg-background/65 p-4">
                    <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
                      Watch
                    </p>
                    <p className="mt-2 font-display text-[1.45rem] italic leading-none text-amber-700">
                      {verdictCounts.watch}
                    </p>
                  </div>
                  <div className="product-panel border-border/60 bg-background/65 p-4">
                    <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
                      Broken
                    </p>
                    <p className="mt-2 font-display text-[1.45rem] italic leading-none text-red-600">
                      {verdictCounts.broken}
                    </p>
                  </div>
                  <div className="product-panel border-border/60 bg-background/65 p-4">
                    <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
                      Unclear
                    </p>
                    <p className="mt-2 font-display text-[1.45rem] italic leading-none text-foreground/70">
                      {verdictCounts.unclear}
                    </p>
                  </div>
                </div>
              </div>

              <div className="space-y-3">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                      Claim review
                    </p>
                    <p className="mt-1 font-sans text-sm text-foreground/80">
                      Each written claim checked against the quarter.
                    </p>
                  </div>
                  <span className="border border-primary/20 bg-primary/6 px-2 py-1 font-mono text-[10px] uppercase tracking-[0.14em] text-primary/75">
                    {result.verdicts.length} checked
                  </span>
                </div>

                <div className="space-y-3">
                  {result.verdicts.map((verdict) => (
                    <VerdictCard key={verdict.claim_id} verdict={verdict} />
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>

        {result && (
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border/70 px-5 py-4 sm:px-6">
            <div className="flex items-center gap-2 text-muted-foreground">
              <CheckCircle2 className="size-4 text-emerald-600" />
              <p className="font-mono text-[10px] uppercase tracking-[0.14em]">
                Saved to decision trail{reviewedAt ? ` · ${reviewedAt}` : ""}
              </p>
            </div>
            <div className="flex items-center gap-2">
              {verdictCounts.broken > 0 && (
                <div className="hidden items-center gap-1.5 text-red-600 sm:flex">
                  <AlertTriangle className="size-4" />
                  <span className="font-sans text-sm">One or more claims came back broken.</span>
                </div>
              )}
              <Button variant="outline" onClick={onClose}>
                Done
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
