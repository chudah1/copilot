"use client";

import Link from "next/link";
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
    border: "border-l-emerald-600",
    bg: "hover:bg-emerald-500/8",
    text: "group-hover:text-emerald-800",
  },
  {
    value: "probably",
    label: "Probably",
    description: "Still valid, but with a little less certainty.",
    border: "border-l-teal-500",
    bg: "hover:bg-teal-500/8",
    text: "group-hover:text-teal-800",
  },
  {
    value: "not_sure",
    label: "Not sure",
    description: "Something feels off. This needs another pass.",
    border: "border-l-amber-500",
    bg: "hover:bg-amber-500/8",
    text: "group-hover:text-amber-900",
  },
  {
    value: "no",
    label: "No",
    description: "You would not start this position today.",
    border: "border-l-[#5C2018]",
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
    <div className="min-h-[calc(100vh-53px)] flex items-center justify-center px-4 py-10 sm:px-8">
      <div className="product-panel product-panel-muted w-full max-w-xl p-8 text-center">
        <p className="font-mono text-[10px] uppercase tracking-[0.3em] text-foreground/30 animate-pulse">
          Loading review…
        </p>
      </div>
    </div>
  );
}

// ── Empty state ─────────────────────────────────────────────────────────────

function EmptyState() {
  return (
    <div className="min-h-[calc(100vh-53px)] flex items-center justify-center px-4 py-10 sm:px-8">
      <div className="product-panel product-panel-muted w-full max-w-xl p-8 text-center space-y-6">
        <div className="space-y-2">
          <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-foreground/40">
            Quarterly review
          </p>
          <h2 className="font-display italic text-[2rem] leading-tight text-foreground">
            Nothing to review yet.
          </h2>
          <p className="font-sans text-sm text-muted-foreground leading-relaxed">
            Add a holding with a written case. This review shows up after one quarter.
          </p>
        </div>
        <Link
          href="/dashboard"
          className="inline-block font-mono text-[11px] uppercase tracking-[0.15em] text-foreground/60 border-b border-foreground/20 pb-px hover:text-foreground transition-colors"
        >
          ← Back to dashboard
        </Link>
      </div>
    </div>
  );
}

// ── Completion state ────────────────────────────────────────────────────────

function CompletionState({ review }: { review: QuarterlyReviewCurrent }) {
  return (
    <div className="min-h-[calc(100vh-53px)]">
      <div className="mx-auto max-w-4xl px-4 py-10 sm:px-8 space-y-6">
        <div className="product-panel product-panel-muted p-6 sm:p-7 space-y-3">
          <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-foreground/40">
            {review.quarter} · {review.completed_count} reviewed
          </p>
          <h1 className="font-display italic text-[3rem] leading-[1.1] text-foreground tracking-tight">
            Review complete.
          </h1>
          <p className="font-sans text-sm text-muted-foreground leading-relaxed max-w-md">
            Every current case has been revisited. Your latest answers are on record.
          </p>
        </div>

        {/* What your calls reveal — the reckoning across resolved decisions */}
        <DecisionPatterns />

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
          className="inline-block font-mono text-[10px] uppercase tracking-[0.2em] text-foreground/50 border-b border-foreground/20 pb-px hover:text-foreground transition-colors"
        >
          ← Back to dashboard
        </Link>
      </div>
    </div>
  );
}

// ── Main page ───────────────────────────────────────────────────────────────

export default function QuarterlyReviewPage() {
  const [review, setReview] = useState<QuarterlyReviewCurrent | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState<QuarterlyReviewSubmission["response"] | null>(null);
  const [lastSubmitted, setLastSubmitted] = useState<QuarterlyReviewSubmission | null>(null);

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
      <div className="min-h-[calc(100vh-53px)] flex items-center justify-center px-4 py-10 sm:px-8">
        <div className="product-panel product-panel-muted w-full max-w-xl p-8 text-center space-y-4">
          <p className="font-sans text-sm text-muted-foreground">{loadError}</p>
          <button
            onClick={() => { setLoading(true); void refreshReview(); }}
            className="font-mono text-[10px] uppercase tracking-[0.2em] text-foreground/60 border-b border-foreground/20 pb-px hover:text-foreground transition-colors"
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

  return (
    <div className="min-h-[calc(100vh-53px)]">
      <div className="mx-auto max-w-4xl px-4 py-10 sm:px-8 space-y-6">
        <div className="product-panel product-panel-muted overflow-hidden">
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
                className="font-mono text-[10px] uppercase tracking-[0.18em] text-foreground/40 hover:text-foreground transition-colors"
              >
                ← Dashboard
              </Link>
              <h1 className="font-display italic text-[2.6rem] leading-[1.05] text-foreground tracking-tight">
                Would you buy this today?
              </h1>
              <p className="max-w-xl font-sans text-sm text-muted-foreground leading-relaxed">
                Treat it like fresh capital. Does the written case still earn a buy today?
              </p>
            </div>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1">
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
            </div>
          </div>
        </div>

        <AnimatePresence mode="wait">
          <motion.div
            key={currentHolding.holding_id}
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -16 }}
            transition={{ duration: 0.28, ease: "easeOut" }}
          >
            <div className="product-panel p-5 sm:p-6">
              <div className="flex flex-wrap items-baseline justify-between gap-4 border-b border-border/50 pb-5 mb-7">
                <div className="flex items-baseline gap-3">
                  <span className="font-mono text-[1.45rem] font-bold tracking-[0.1em] text-foreground">
                    {cleanTicker(currentHolding.ticker)}
                  </span>
                  <span className="font-sans text-sm text-muted-foreground">{currentHolding.name}</span>
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
                    className="font-mono text-[10px] uppercase tracking-[0.12em] text-foreground/50 border-b border-foreground/20 pb-px hover:text-foreground transition-colors"
                  >
                    Position page
                  </Link>
                </div>
              </div>

              <div className="space-y-5">
                <div className="border border-border/70 bg-background/55 p-5">
                  <p className="font-mono text-[10px] uppercase tracking-[0.15em] text-foreground/40 mb-3">
                    Your case
                  </p>
                  <blockquote className="font-display italic text-[1.2rem] leading-[1.65] text-foreground/90 border-l-2 border-[#5C2018]/30 pl-5">
                    {currentHolding.why_own_it}
                  </blockquote>
                </div>

                <div>
                  <p className="font-mono text-[10px] uppercase tracking-[0.15em] text-foreground/40 mb-2">
                    Notes for your future self
                  </p>
                  <div className="border border-border/70 bg-background/55 p-4">
                    <textarea
                      value={notes}
                      onChange={(e) => setNotes(e.target.value)}
                      placeholder="What changed, if anything? (optional)"
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
                    className={`group w-full flex items-center justify-between gap-4 border-l-[3px] border border-border/50 bg-background/55 px-5 py-3.5 text-left transition-all duration-150 disabled:opacity-50 disabled:cursor-not-allowed ${option.border} ${option.bg}`}
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
                    className="border border-amber-400/40 bg-amber-500/8 px-4 py-3"
                  >
                    <p className="font-sans text-[12px] text-amber-800 leading-relaxed">
                      This keeps the holding on your radar. The best next move is to
                      tighten or rewrite the case from the holding page.
                    </p>
                  </motion.div>
                )}

                {pendingHoldings.length > 1 && (
                  <p className="font-mono text-[10px] uppercase tracking-[0.15em] text-foreground/30 text-center">
                    {pendingHoldings.length - 1} left
                  </p>
                )}
              </div>
            </div>
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  );
}
