"use client";

import { useState } from "react";
import { motion, useMotionValue, useTransform, AnimatePresence } from "framer-motion";
import { Button } from "@/components/ui/button";
import { formatDate } from "@/lib/utils";
import type { MonitoringEvent } from "@/types";

type ReviewAction = "reaffirmed" | "ignored" | "lowered_confidence" | "invalidated" | "not_relevant";

interface Props {
  events: MonitoringEvent[];
  onReview: (event: MonitoringEvent, action: ReviewAction, notes?: string) => Promise<void>;
  reviewingEventId: string | null;
  investorProfile?: "thesis_driven" | "hearsay_driven" | null;
}

const severityStripe: Record<string, string> = {
  info: "bg-blue-500",
  warning: "bg-amber-500",
  thesis_breaking: "bg-red-500",
};

const verdictBg: Record<string, string> = {
  supports: "bg-emerald-50 text-emerald-800 border-emerald-200",
  threatens: "bg-red-50 text-red-800 border-red-200",
  review: "bg-amber-50 text-amber-800 border-amber-200",
  neutral: "bg-muted text-muted-foreground border-border",
};

function parseNarrative(text: string) {
  const out: Record<string, string> = {};
  const body: string[] = [];
  for (const line of text.split("\n")) {
    const i = line.indexOf(":");
    if (i > 0 && i < 28) {
      const k = line.slice(0, i).trim();
      const v = line.slice(i + 1).trim().replace(/^"|"$/g, "");
      if (v) {
        out[k] = v;
        continue;
      }
    }
    if (line.trim()) body.push(line.trim());
  }
  if (body[0]) out._body0 = body[0];
  if (body[1]) out._body1 = body[1];
  if (body[2]) out._body2 = body[2];
  return out;
}

function eventDecisionCopy(
  event: MonitoringEvent,
  investorProfile?: "thesis_driven" | "hearsay_driven" | null,
) {
  const narrative = event.evidence_summary ? parseNarrative(event.evidence_summary) : {};
  const assumption =
    event.signal_label ??
    narrative["We were watching"] ??
    narrative["What the app was checking"] ??
    narrative["We watched"] ??
    null;
  const thesisLine =
    narrative["Your thesis"] ??
    narrative["You said"] ??
    narrative["Your reason"] ??
    null;
  const whatChanged =
    narrative["What changed"] ??
    narrative["What happened"] ??
    narrative._body0 ??
    event.summary;
  const whyItMatters =
    narrative["Why this matters now"] ??
    narrative["Why it matters now"] ??
    narrative._body1 ??
    event.ai_analysis ??
    null;

  const prompt = investorProfile === "hearsay_driven"
    ? "Does this actually change the original story?"
    : investorProfile === "thesis_driven"
      ? "Does this actually weaken the thesis?"
      : "Does this change the reason enough to act?";

  return {
    assumption,
    thesisLine,
    whatChanged,
    whyItMatters,
    prompt,
  };
}

// ── Single draggable card ──────────────────────────────────────────────────

interface CardProps {
  event: MonitoringEvent;
  index: number;
  total: number;
  isTop: boolean;
  onSwipe: (action: ReviewAction) => void;
  busy: boolean;
  investorProfile?: "thesis_driven" | "hearsay_driven" | null;
}

function reviewCopy(investorProfile?: "thesis_driven" | "hearsay_driven" | null) {
  if (investorProfile === "thesis_driven") {
    return {
      right: "Thesis holds",
      up: "Assumption weaker",
      left: "Not relevant",
      buttonHold: "Thesis holds",
      buttonErode: "Assumption weaker",
      buttonSkip: "Not relevant",
      buttonBroken: "Thesis broken",
      reviewHint: "drag to decide · swipe up to flag weakening confidence",
      allCaughtUp: "You've reviewed every signal. Your thesis stands until something changes.",
    };
  }

  if (investorProfile === "hearsay_driven") {
    return {
      right: "Reason holds",
      up: "Less sure",
      left: "Not relevant",
      buttonHold: "Reason holds",
      buttonErode: "Less sure now",
      buttonSkip: "Not relevant",
      buttonBroken: "Story broken",
      reviewHint: "drag to decide · swipe up if the story feels weaker",
      allCaughtUp: "You've reviewed every signal. Your reason stands until something real changes.",
    };
  }

  return {
    right: "Holds",
    up: "Eroding",
    left: "Irrelevant",
    buttonHold: "Reason holds",
    buttonErode: "Eroding",
    buttonSkip: "Skip",
    buttonBroken: "Broken",
    reviewHint: "drag to decide · swipe up to flag",
    allCaughtUp: "You've reviewed every signal. Your reason stands until something changes.",
  };
}

function DraggableCard({ event, index, total, isTop, onSwipe, busy, investorProfile }: CardProps) {
  const x = useMotionValue(0);
  const y = useMotionValue(0);
  const copy = reviewCopy(investorProfile);

  const rotate = useTransform(x, [-220, 0, 220], [-14, 0, 14]);
  const rightOpacity = useTransform(x, [20, 100], [0, 1]);
  const leftOpacity = useTransform(x, [-100, -20], [1, 0]);
  const upOpacity = useTransform(y, [-100, -20], [1, 0]);

  const narrative = eventDecisionCopy(event, investorProfile);
  const verdict = event.verdict;

  const handleDragEnd = (_: unknown, info: { offset: { x: number; y: number }; velocity: { x: number; y: number } }) => {
    if (busy) return;
    const { offset, velocity } = info;
    if (offset.x > 110 || velocity.x > 450) {
      onSwipe("reaffirmed");
    } else if (offset.x < -110 || velocity.x < -450) {
      onSwipe("not_relevant");
    } else if (offset.y < -110 || velocity.y < -450) {
      onSwipe("lowered_confidence");
    } else {
      // snap back
      x.set(0);
      y.set(0);
    }
  };

  // Stack visual: each card behind is slightly smaller and lower
  const stackY = index * 6;
  const stackScale = 1 - index * 0.045;

  return (
    <motion.div
      className="absolute inset-0"
      style={{
        y: isTop ? y : stackY,
        x: isTop ? x : 0,
        rotate: isTop ? rotate : 0,
        scale: stackScale,
        zIndex: total - index,
      }}
      drag={isTop && !busy}
      dragConstraints={{ left: 0, right: 0, top: 0, bottom: 0 }}
      dragElastic={0.65}
      onDragEnd={handleDragEnd}
      initial={isTop ? { scale: 1, y: 0 } : undefined}
      whileDrag={{ cursor: "grabbing" }}
    >
      <div
        className={`h-full w-full overflow-hidden rounded-sm border border-border bg-card shadow-md flex flex-col ${isTop ? "cursor-grab" : "pointer-events-none select-none"}`}
      >
        {/* Severity stripe */}
        <div className={`h-1 w-full flex-shrink-0 ${severityStripe[event.severity] ?? "bg-border"}`} />

        {/* Card body */}
        <div className="flex flex-col flex-1 p-5 overflow-hidden">

          {/* Meta row */}
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <span className="font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground border border-border px-1.5 py-0.5">
                {event.severity.replace("_", " ")}
              </span>
              {narrative.assumption && (
                <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-primary/70">
                  {narrative.assumption}
                </span>
              )}
            </div>
            <span className="font-mono text-[10px] text-muted-foreground/80">
              {formatDate(event.created_at)}
            </span>
          </div>

          {/* Thesis clause quoted */}
          {narrative.thesisLine && (
            <blockquote className="border-l-2 border-primary/30 pl-3 mb-3">
              <p className="font-sans text-xs italic text-muted-foreground leading-relaxed line-clamp-2">
                &ldquo;{narrative.thesisLine}&rdquo;
              </p>
            </blockquote>
          )}

          <div className="space-y-3 flex-1 overflow-hidden">
            <div>
              <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground/80 mb-1">
                What changed
              </p>
              <p className="font-sans text-sm text-foreground leading-relaxed line-clamp-4">
                {narrative.whatChanged}
              </p>
            </div>

            {narrative.whyItMatters && (
              <div>
                <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground/80 mb-1">
                  Why it matters
                </p>
                <p className="font-sans text-sm text-foreground/80 leading-relaxed line-clamp-4">
                  {narrative.whyItMatters}
                </p>
              </div>
            )}
          </div>

          {/* Verdict chip */}
          {verdict && (
            <div className={`mt-3 inline-flex self-start items-center border rounded-sm px-2 py-0.5 font-mono text-[10px] uppercase tracking-[0.12em] ${verdictBg[verdict] ?? verdictBg.neutral}`}>
              {verdict === "supports" ? "Supports reason" : verdict === "threatens" ? "Threatens reason" : verdict === "review" ? "Warrants review" : "Neutral"}
            </div>
          )}

          <p className="mt-3 font-mono text-[10px] uppercase tracking-[0.14em] text-foreground/60">
            {narrative.prompt}
          </p>

          {/* Source */}
          {event.source_url && (
            <a
              href={event.source_url}
              target="_blank"
              rel="noreferrer"
              onClick={(e) => e.stopPropagation()}
              className="mt-2 font-mono text-[10px] uppercase tracking-[0.12em] text-primary/60 hover:text-primary transition-colors underline underline-offset-2"
            >
              Source ↗
            </a>
          )}
        </div>

        {/* Swipe hint row at bottom */}
        {isTop && (
          <div className="flex items-center justify-between border-t border-border px-5 py-2.5 bg-muted/30">
            <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-muted-foreground/80">← {copy.left}</span>
            <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-muted-foreground/80">↑ {copy.up}</span>
            <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-muted-foreground/80">{copy.right} →</span>
          </div>
        )}
      </div>

      {/* Drag direction overlays — fade in as card is dragged */}
      {isTop && (
        <>
          {/* RIGHT — Thesis holds */}
          <motion.div
            style={{ opacity: rightOpacity }}
            className="pointer-events-none absolute inset-0 flex items-center justify-start pl-6 rounded-sm"
          >
            <div className="border-2 border-emerald-500 rounded-sm px-3 py-1.5 rotate-[-12deg]">
              <span className="font-mono text-sm font-bold tracking-[0.2em] text-emerald-600 uppercase">{copy.right}</span>
            </div>
          </motion.div>

          {/* LEFT — Irrelevant */}
          <motion.div
            style={{ opacity: leftOpacity }}
            className="pointer-events-none absolute inset-0 flex items-center justify-end pr-6 rounded-sm"
          >
            <div className="border-2 border-muted-foreground/40 rounded-sm px-3 py-1.5 rotate-[12deg]">
              <span className="font-mono text-sm font-bold tracking-[0.2em] text-muted-foreground uppercase">{copy.left}</span>
            </div>
          </motion.div>

          {/* UP — Eroding confidence */}
          <motion.div
            style={{ opacity: upOpacity }}
            className="pointer-events-none absolute inset-0 flex items-end justify-center pb-14 rounded-sm"
          >
            <div className="border-2 border-amber-500 rounded-sm px-3 py-1.5">
              <span className="font-mono text-sm font-bold tracking-[0.2em] text-amber-600 uppercase">{copy.up}</span>
            </div>
          </motion.div>
        </>
      )}
    </motion.div>
  );
}

// ── Stack container ────────────────────────────────────────────────────────

export function EventReviewStack({ events, onReview, reviewingEventId, investorProfile }: Props) {
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());
  const copy = reviewCopy(investorProfile);

  // Events not yet dismissed from stack
  const pending = events.filter((e) => !dismissed.has(e.id));
  const topEvent = pending[0];

  const handleSwipe = async (action: ReviewAction) => {
    if (!topEvent || reviewingEventId) return;
    setDismissed((prev) => new Set([...prev, topEvent.id]));
    // Fire-and-forget — parent handles optimistic update
    void onReview(topEvent, action);
  };

  const handleInvalidate = async () => {
    if (!topEvent || reviewingEventId) return;
    setDismissed((prev) => new Set([...prev, topEvent.id]));
    void onReview(topEvent, "invalidated");
  };

  // ── All cleared ─────────────────────────────────────
  if (pending.length === 0) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: "easeOut" }}
        className="py-12 text-center space-y-2"
      >
        <p className="font-display text-2xl italic text-foreground">All caught up.</p>
        <p className="font-sans text-sm text-muted-foreground">
          {copy.allCaughtUp}
        </p>
      </motion.div>
    );
  }

  // Show up to 3 cards in the stack (current + 2 behind)
  const visibleCards = pending.slice(0, 3);

  return (
    <div className="space-y-5">
      {/* Counter */}
      <div className="flex items-center justify-between">
        <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
          {pending.length} to review
        </p>
        <p className="font-mono text-[10px] text-muted-foreground/80">
          {copy.reviewHint}
        </p>
      </div>

      {/* Card stack */}
      <div className="relative h-[340px]">
        <AnimatePresence>
          {visibleCards.map((event, index) => (
            <motion.div
              key={event.id}
              className="absolute inset-0"
              exit={
                index === 0
                  ? {
                      x: dismissed.has(event.id) ? 0 : 0,
                      opacity: 0,
                      scale: 0.88,
                      transition: { duration: 0.22, ease: "easeIn" },
                    }
                  : {}
              }
            >
              <DraggableCard
                event={event}
                index={index}
                total={visibleCards.length}
                isTop={index === 0}
                onSwipe={handleSwipe}
                busy={!!reviewingEventId}
                investorProfile={investorProfile}
              />
            </motion.div>
          ))}
        </AnimatePresence>
      </div>

      {/* Explicit action buttons under stack */}
      <div className="flex items-center gap-2 pt-1">
        <Button
          size="sm"
          onClick={() => void handleSwipe("reaffirmed")}
          disabled={!!reviewingEventId}
          className="flex-1"
        >
          {copy.buttonHold}
        </Button>
        <Button
          size="sm"
          variant="outline"
          onClick={() => void handleSwipe("lowered_confidence")}
          disabled={!!reviewingEventId}
        >
          {copy.buttonErode}
        </Button>
        <Button
          size="sm"
          variant="outline"
          onClick={() => void handleSwipe("not_relevant")}
          disabled={!!reviewingEventId}
        >
          {copy.buttonSkip}
        </Button>
        <Button
          size="sm"
          variant="destructive"
          onClick={() => void handleInvalidate()}
          disabled={!!reviewingEventId}
        >
          {copy.buttonBroken}
        </Button>
      </div>
    </div>
  );
}
