"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

import { api } from "@/lib/api";
import { DecisionPatterns } from "./decision-patterns";
import { getErrorMessage } from "@/lib/errors";
import { formatCurrency } from "@/lib/utils";
import type { QuarterlyReviewCurrent, QuarterlyReviewHolding, QuarterlyReviewSubmission } from "@/types";
import { toast } from "sonner";

function cleanTicker(ticker: string) {
  return ticker.replace(/_US_EQ$/, "").replace(/_EQ$/, "");
}

function formatReasonAgeLabel(days: number) {
  if (days <= 0) return "Written today";
  if (days === 1) return "Written yesterday";
  return `Written ${days}d ago`;
}

function formatReasonAgeCompact(days: number) {
  if (days <= 0) return "Today";
  if (days === 1) return "1d";
  return `${days}d`;
}

const RESPONSE_OPTIONS: Array<{
  value: "yes_absolutely" | "probably" | "not_sure" | "no";
  label: string;
  description: string;
  border: string;
  bg: string;
  text: string;
}> = [
  {
    value: "yes_absolutely",
    label: "Yes, absolutely",
    description: "This still feels strong at today's price.",
    border: "border-emerald-500/30",
    bg: "hover:bg-emerald-500/8",
    text: "group-hover:text-emerald-800",
  },
  {
    value: "probably",
    label: "Probably",
    description: "Still valid, but with a little less certainty.",
    border: "border-teal-500/30",
    bg: "hover:bg-teal-500/8",
    text: "group-hover:text-teal-800",
  },
  {
    value: "not_sure",
    label: "Not sure",
    description: "Something feels off. This needs another pass.",
    border: "border-amber-500/30",
    bg: "hover:bg-amber-500/8",
    text: "group-hover:text-amber-900",
  },
  {
    value: "no",
    label: "No",
    description: "You would not start this position today.",
    border: "border-[#5C2018]/30",
    bg: "hover:bg-red-500/8",
    text: "group-hover:text-[#5C2018]",
  },
];

const RESPONSE_LABELS: Record<string, { label: string; color: string }> = {
  yes_absolutely: { label: "Yes, absolutely", color: "text-emerald-700" },
  probably:       { label: "Probably",        color: "text-teal-700"   },
  not_sure:       { label: "Not sure",        color: "text-amber-700"  },
  no:             { label: "No",              color: "text-[#5C2018]"  },
};

// ── Loading skeleton ────────────────────────────────────────────────────────

function LoadingSkeleton() {
  return (
    <div className="min-h-[calc(100vh-84px)] flex items-center justify-center px-4 py-10 sm:px-8">
      <div className="product-panel w-full max-w-xl border border-border/70 bg-background/82 p-8 text-center">
        <p className="font-mono text-[10px] uppercase tracking-[0.3em] text-foreground/30 animate-pulse">
          Loading review queue…
        </p>
      </div>
    </div>
  );
}

// ── Empty state ─────────────────────────────────────────────────────────────

function EmptyState() {
  return (
    <div className="min-h-[calc(100vh-84px)] flex items-center justify-center px-4 py-10 sm:px-8">
      <div className="product-panel w-full max-w-xl border border-border/70 bg-[linear-gradient(180deg,rgba(163,126,79,0.05),rgba(255,255,255,0.96))] p-8 text-center space-y-6">
        <div className="space-y-2">
          <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-foreground/40">
            Quarterly review
          </p>
          <h2 className="font-display italic text-[2rem] leading-tight text-foreground">
            Nothing needs a quarterly revisit yet.
          </h2>
          <p className="font-sans text-sm text-muted-foreground leading-relaxed">
            Once a live position rolls into a new quarter, it will return here for a fresh decision.
          </p>
        </div>
        <Link
          href="/dashboard"
          className="inline-flex items-center border border-border/60 bg-background/72 px-3 py-2 font-mono text-[10px] uppercase tracking-[0.15em] text-foreground/70 transition-colors hover:border-border hover:text-foreground"
        >
          Back to dashboard
        </Link>
      </div>
    </div>
  );
}

// ── Completion state ────────────────────────────────────────────────────────

function CompletionState({ review }: { review: QuarterlyReviewCurrent }) {
  const searchParams = useSearchParams();
  const selectedPattern = searchParams.get("pattern");

  return (
    <div className="min-h-[calc(100vh-84px)]">
      <div className="mx-auto max-w-4xl px-4 py-10 sm:px-8 space-y-6">
        <div className="product-panel border border-emerald-500/20 bg-[linear-gradient(180deg,rgba(16,185,129,0.08),rgba(255,255,255,0.95))] p-6 sm:p-7 space-y-3">
          <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-foreground/40">
            {review.quarter} · {review.completed_count} reviewed
          </p>
          <h1 className="font-display italic text-[3rem] leading-[1.1] text-foreground tracking-tight">
            Review complete.
          </h1>
          <p className="font-sans text-sm text-muted-foreground leading-relaxed max-w-md">
            Every current position has been revisited. Your latest answers are saved.
          </p>
        </div>

        {/* What your decisions reveal — the reckoning across resolved outcomes */}
        <DecisionPatterns selectedKind={selectedPattern} />

        {/* Ledger */}
        <div className="product-panel divide-y divide-border/40 overflow-hidden">
          {/* Ledger header */}
          <div className="grid grid-cols-[1fr_auto_auto] gap-6 px-5 py-3 bg-secondary/40">
            <p className="font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground">Position</p>
            <p className="font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground text-right">Age</p>
            <p className="font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground text-right w-28">Answer</p>
          </div>

          {review.holdings.map((h, i) => {
            const resp = h.response ? RESPONSE_LABELS[h.response] : null;
            return (
              <motion.div
                key={h.holding_id}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.05 }}
                className="grid grid-cols-[1fr_auto_auto] gap-6 px-5 py-4 items-start"
              >
                <div className="min-w-0">
                  <div className="flex items-baseline gap-2">
                    <span className="font-mono text-[11px] font-semibold tracking-[0.15em] text-foreground">
                      {cleanTicker(h.ticker)}
                    </span>
                    <span className="font-sans text-xs text-muted-foreground truncate">{h.name}</span>
                  </div>
                  {h.response_notes && (
                    <p className="font-sans text-[11px] text-foreground/60 mt-1 leading-relaxed line-clamp-2 italic">
                      &ldquo;{h.response_notes}&rdquo;
                    </p>
                  )}
                </div>
                <p className="font-mono text-[11px] text-muted-foreground text-right tabular-nums">
                  {formatReasonAgeCompact(h.reason_age_days)}
                </p>
                <p className={`font-sans text-[12px] font-medium text-right w-28 ${resp?.color ?? "text-muted-foreground"}`}>
                  {resp?.label ?? "—"}
                </p>
              </motion.div>
            );
          })}
        </div>

        <Link
          href="/dashboard"
          className="inline-flex items-center border border-border/60 bg-background/72 px-3 py-2 font-mono text-[10px] uppercase tracking-[0.15em] text-foreground/70 transition-colors hover:border-border hover:text-foreground"
        >
          Back to dashboard
        </Link>
      </div>
    </div>
  );
}

// ── Main page ───────────────────────────────────────────────────────────────

export default function QuarterlyReviewPage() {
  const searchParams = useSearchParams();
  const [review, setReview] = useState<QuarterlyReviewCurrent | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState<QuarterlyReviewSubmission["response"] | null>(null);
  const [lastSubmitted, setLastSubmitted] = useState<QuarterlyReviewSubmission | null>(null);
  const selectedPattern = searchParams.get("pattern");

  const refreshReview = async (options?: { preserveLoading?: boolean }) => {
    try {
      const current = await api.get<QuarterlyReviewCurrent>("/api/quarterly-review/current");
      setReview(current);
      setLoadError(null);
    } catch (err) {
      setLoadError(getErrorMessage(err, "Failed to load quarterly review"));
    } finally {
      if (!options?.preserveLoading) setLoading(false);
    }
  };

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const current = await api.get<QuarterlyReviewCurrent>("/api/quarterly-review/current");
        if (!cancelled) { setReview(current); setLoadError(null); }
      } catch (err) {
        if (!cancelled) setLoadError(getErrorMessage(err, "Failed to load quarterly review"));
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    void load();
    return () => { cancelled = true; };
  }, []);

  const pendingHoldings = useMemo(
    () => review?.holdings.filter((h) => h.response === null) ?? [],
    [review],
  );
  const currentHolding: QuarterlyReviewHolding | null = pendingHoldings[0] ?? null;

  const handleSubmit = async (response: QuarterlyReviewSubmission["response"]) => {
    if (!currentHolding) return;
    try {
      setSubmitting(response);
      const result = await api.post<QuarterlyReviewSubmission>("/api/quarterly-review/current/respond", {
        holding_id: currentHolding.holding_id,
        response,
        notes: notes.trim() || undefined,
      });
      setLastSubmitted(result);
      setNotes("");
      toast.success(`${cleanTicker(currentHolding.ticker)} logged.`);
      await refreshReview({ preserveLoading: true });
    } catch (err) {
      toast.error(getErrorMessage(err, "Failed to save"));
    } finally {
      setSubmitting(null);
    }
  };

  if (loading) return <LoadingSkeleton />;

  if (loadError) {
    return (
      <div className="min-h-[calc(100vh-84px)] flex items-center justify-center px-4 py-10 sm:px-8">
        <div className="product-panel w-full max-w-xl border border-border/70 bg-background/82 p-8 text-center space-y-4">
          <p className="font-sans text-sm text-muted-foreground">{loadError}</p>
          <button
            onClick={() => { setLoading(true); void refreshReview(); }}
            className="inline-flex items-center justify-center border border-border/60 bg-background/72 px-3 py-2 font-mono text-[10px] uppercase tracking-[0.15em] text-foreground/70 transition-colors hover:border-border hover:text-foreground"
          >
            Try again
          </button>
        </div>
      </div>
    );
  }

  if (!review || review.total_holdings === 0) return <EmptyState />;
  if (!currentHolding) return <CompletionState review={review} />;

  const currentIndex = review.completed_count + 1;
  const progressPct = (review.completed_count / review.total_holdings) * 100;
  const remainingCount = Math.max(0, review.total_holdings - review.completed_count - 1);

  return (
    <div className="min-h-[calc(100vh-84px)]">
      <div className="mx-auto max-w-4xl px-4 py-10 sm:px-8 space-y-6">
        <div className="product-panel overflow-hidden border border-border/70 bg-[linear-gradient(180deg,rgba(163,126,79,0.07),rgba(255,255,255,0.96))]">
          <div className="h-1 bg-border/40 w-full">
            <motion.div
              className="h-full bg-[#5C2018]"
              initial={{ width: 0 }}
              animate={{ width: `${progressPct}%` }}
              transition={{ duration: 0.6, ease: "easeOut" }}
            />
          </div>
          <div className="flex flex-wrap items-start justify-between gap-4 px-5 py-5 sm:px-6">
            <div className="space-y-2">
              <Link
                href="/dashboard"
                className="inline-flex items-center border border-border/60 bg-background/72 px-3 py-2 font-mono text-[10px] uppercase tracking-[0.15em] text-foreground/65 transition-colors hover:border-border hover:text-foreground"
              >
                Dashboard
              </Link>
              <h1 className="font-display italic text-[2.6rem] leading-[1.05] text-foreground tracking-tight">
                Would you buy this today?
              </h1>
              <p className="max-w-xl font-sans text-sm text-muted-foreground leading-relaxed">
                Treat it like fresh capital. Does this position still deserve a yes today?
              </p>
            </div>
            <div className="grid gap-3 sm:grid-cols-3 xl:grid-cols-3">
              <div className="border border-border/60 bg-background/70 p-4">
                <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                  Quarter
                </p>
                <p className="mt-2 font-display text-[1.3rem] italic leading-tight text-foreground">
                  {review.quarter}
                </p>
              </div>
              <div className="border border-border/60 bg-background/70 p-4">
                <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                  Progress
                </p>
                <p className="mt-2 font-display text-[1.3rem] italic leading-tight text-foreground">
                  {currentIndex} of {review.total_holdings}
                </p>
              </div>
              <div className="border border-border/60 bg-background/70 p-4">
                <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                  Left after this
                </p>
                <p className="mt-2 font-display text-[1.3rem] italic leading-tight text-foreground">
                  {remainingCount}
                </p>
              </div>
            </div>
          </div>
        </div>

        <div className="grid items-start gap-5 xl:grid-cols-[minmax(0,1fr)_18rem]">
          <AnimatePresence mode="wait">
            <motion.div
              key={currentHolding.holding_id}
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -16 }}
              transition={{ duration: 0.28, ease: "easeOut" }}
            >
              <div className="product-panel p-5 sm:p-6">
                <div className="space-y-6">
                  <div className="flex flex-wrap items-baseline justify-between gap-4 border-b border-border/50 pb-5">
                    <div className="space-y-2">
                      <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                        Current position
                      </p>
                      <div className="flex items-baseline gap-3">
                        <span className="font-mono text-[1.45rem] font-bold tracking-[0.1em] text-foreground">
                          {cleanTicker(currentHolding.ticker)}
                        </span>
                        <span className="font-sans text-sm text-muted-foreground">{currentHolding.name}</span>
                      </div>
                    </div>
                    <div className="flex flex-wrap items-center gap-4 shrink-0">
                      {currentHolding.current_price != null && (
                        <span className="font-mono text-[11px] tabular-nums text-muted-foreground">
                          {formatCurrency(currentHolding.current_price, currentHolding.currency)}
                        </span>
                      )}
                      <span className="border border-border/60 bg-background/70 px-2.5 py-1 font-sans text-[11px] text-foreground/75">
                        {formatReasonAgeLabel(currentHolding.reason_age_days)}
                      </span>
                      <Link
                        href={`/dashboard/positions/${currentHolding.ticker}`}
                        className="inline-flex items-center border border-border/60 bg-background/72 px-3 py-2 font-mono text-[10px] uppercase tracking-[0.14em] text-foreground/70 transition-colors hover:border-border hover:text-foreground"
                      >
                        See position
                      </Link>
                    </div>
                  </div>
                  <div className="product-panel border border-border/70 bg-background/65 p-5">
                    <p className="font-mono text-[10px] uppercase tracking-[0.15em] text-foreground/40 mb-3">
                      Written view
                    </p>
                    <blockquote className="font-display italic text-[1.2rem] leading-[1.65] text-foreground/90">
                      {currentHolding.why_own_it}
                    </blockquote>
                  </div>

                  <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_16rem]">
                    <div className="space-y-5">
                      <div>
                        <p className="font-mono text-[10px] uppercase tracking-[0.15em] text-foreground/40 mb-2">
                          Notes for this review
                        </p>
                        <div className="border border-border/70 bg-background/55 p-4">
                          <textarea
                            value={notes}
                            onChange={(e) => setNotes(e.target.value)}
                            placeholder="What feels different at today's price? (optional)"
                            rows={4}
                            className="w-full resize-none bg-transparent font-sans text-[13px] text-foreground outline-none placeholder:text-foreground/25"
                          />
                        </div>
                      </div>

                      <div className="space-y-2">
                        <p className="font-mono text-[10px] uppercase tracking-[0.15em] text-foreground/40">
                          Your answer
                        </p>
                        {RESPONSE_OPTIONS.map((option) => {
                          const isLoading = submitting === option.value;
                          return (
                            <button
                              key={option.value}
                              type="button"
                              onClick={() => void handleSubmit(option.value)}
                              disabled={submitting !== null}
                              className={`group product-panel w-full flex items-center justify-between gap-4 border bg-background/65 px-5 py-3.5 text-left transition-all duration-150 disabled:cursor-not-allowed disabled:opacity-50 ${option.border} ${option.bg}`}
                            >
                              <div className="flex-1 min-w-0">
                                <p className={`font-sans text-[13px] font-medium text-foreground transition-colors ${option.text}`}>
                                  {option.label}
                                </p>
                                <p className="font-sans text-[11px] text-muted-foreground mt-0.5">
                                  {option.description}
                                </p>
                              </div>
                              <span className="font-mono text-[10px] text-foreground/25 shrink-0 transition-colors group-hover:text-foreground/50">
                                {isLoading ? "…" : "→"}
                              </span>
                            </button>
                          );
                        })}
                      </div>

                      {lastSubmitted && ["not_sure", "no"].includes(lastSubmitted.response) && (
                        <motion.div
                          initial={{ opacity: 0, y: 6 }}
                          animate={{ opacity: 1, y: 0 }}
                          className="product-panel border border-amber-400/40 bg-amber-500/8 px-4 py-3"
                        >
                          <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-amber-800">
                            Keep this on your radar
                          </p>
                          <p className="mt-1 font-sans text-[12px] leading-relaxed text-foreground/82">
                            This keeps the holding on your radar. The best next move is to
                            clarify or rewrite the reason from the holding page.
                          </p>
                        </motion.div>
                      )}

                      {pendingHoldings.length > 1 && (
                        <p className="font-mono text-[10px] uppercase tracking-[0.15em] text-foreground/30 text-center">
                          {pendingHoldings.length - 1} left after this
                        </p>
                      )}
                    </div>

                    <aside className="space-y-3">
                      <div className="product-panel border border-border/60 bg-background/72 p-4 sm:p-5">
                        <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                          Review lens
                        </p>
                        <p className="mt-2 font-sans text-sm leading-relaxed text-foreground/80">
                          Answer as if you were buying the position fresh today, not defending an old decision.
                        </p>
                      </div>
                      <div className="product-panel border border-border/60 bg-background/72 p-4 sm:p-5">
                        <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                          What a no means
                        </p>
                        <p className="mt-2 font-sans text-sm leading-relaxed text-foreground/76">
                          A no does not force a trade. It tells future you the reason needs rewriting or the holding needs a harder look.
                        </p>
                      </div>
                    </aside>
                  </div>
                </div>
              </div>
            </motion.div>
          </AnimatePresence>

          <aside className="space-y-5 xl:sticky xl:top-[96px]">
            <div className="hidden xl:block">
              <DecisionPatterns selectedKind={selectedPattern} variant="compact" />
            </div>
            <div className="product-panel p-4 sm:p-5">
              <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                Why this page matters
              </p>
              <p className="mt-2 font-sans text-sm leading-relaxed text-foreground/80">
                Quarterly review is where you decide whether this position still deserves fresh capital. The pattern beside it shows the part of your behavior that tends to reappear when conviction gets tested.
              </p>
            </div>
          </aside>
        </div>

        <div className="xl:hidden">
          <DecisionPatterns selectedKind={selectedPattern} />
        </div>
      </div>
    </div>
  );
}
