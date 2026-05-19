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
  for (const line of text.split("\n")) {
    const i = line.indexOf(":");
    if (i > 0 && i < 24) {
      const k = line.slice(0, i).trim();
      const v = line.slice(i + 1).trim();
      if (v) out[k] = v;
    }
  }
  return out;
}

// ── Single draggable card ──────────────────────────────────────────────────

interface CardProps {
  event: MonitoringEvent;
  index: number;
  total: number;
  isTop: boolean;
  onSwipe: (action: ReviewAction) => void;
  busy: boolean;
}

function DraggableCard({ event, index, total, isTop, onSwipe, busy }: CardProps) {
  const x = useMotionValue(0);
  const y = useMotionValue(0);

  const rotate = useTransform(x, [-220, 0, 220], [-14, 0, 14]);
  const rightOpacity = useTransform(x, [20, 100], [0, 1]);
  const leftOpacity = useTransform(x, [-100, -20], [1, 0]);
  const upOpacity = useTransform(y, [-100, -20], [1, 0]);

  const narrative = event.evidence_summary ? parseNarrative(event.evidence_summary) : {};
  const displayText = narrative["What happened"] ?? event.summary;
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
              <span className="font-mono text-[9px] uppercase tracking-[0.2em] text-muted-foreground border border-border px-1.5 py-0.5">
                {event.severity.replace("_", " ")}
              </span>
              {event.signal_label && (
                <span className="font-mono text-[9px] uppercase tracking-[0.15em] text-primary/70">
                  {event.signal_label}
                </span>
              )}
            </div>
            <span className="font-mono text-[10px] text-muted-foreground/60">
              {formatDate(event.created_at)}
            </span>
          </div>

          {/* Thesis clause quoted */}
          {narrative["You said"] && (
            <blockquote className="border-l-2 border-primary/30 pl-3 mb-3">
              <p className="font-sans text-xs italic text-muted-foreground leading-relaxed line-clamp-2">
                &ldquo;{narrative["You said"]}&rdquo;
              </p>
            </blockquote>
          )}

          {/* Main event text */}
          <p className="font-sans text-sm text-foreground leading-relaxed flex-1 overflow-hidden line-clamp-5">
            {displayText}
          </p>

          {/* Verdict chip */}
          {verdict && (
            <div className={`mt-3 inline-flex self-start items-center border rounded-sm px-2 py-0.5 font-mono text-[9px] uppercase tracking-[0.15em] ${verdictBg[verdict] ?? verdictBg.neutral}`}>
              {verdict === "supports" ? "Supports thesis" : verdict === "threatens" ? "Threatens thesis" : verdict === "review" ? "Warrants review" : "Neutral"}
            </div>
          )}

          {/* Source */}
          {event.source_url && (
            <a
              href={event.source_url}
              target="_blank"
              rel="noreferrer"
              onClick={(e) => e.stopPropagation()}
              className="mt-2 font-mono text-[9px] uppercase tracking-[0.15em] text-primary/60 hover:text-primary transition-colors underline underline-offset-2"
            >
              Source ↗
            </a>
          )}
        </div>

        {/* Swipe hint row at bottom */}
        {isTop && (
          <div className="flex items-center justify-between border-t border-border px-5 py-2.5 bg-muted/30">
            <span className="font-mono text-[9px] uppercase tracking-[0.12em] text-muted-foreground/50">← Irrelevant</span>
            <span className="font-mono text-[9px] uppercase tracking-[0.12em] text-muted-foreground/50">↑ Eroding</span>
            <span className="font-mono text-[9px] uppercase tracking-[0.12em] text-muted-foreground/50">Holds →</span>
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
              <span className="font-mono text-sm font-bold tracking-[0.2em] text-emerald-600 uppercase">Holds</span>
            </div>
          </motion.div>

          {/* LEFT — Irrelevant */}
          <motion.div
            style={{ opacity: leftOpacity }}
            className="pointer-events-none absolute inset-0 flex items-center justify-end pr-6 rounded-sm"
          >
            <div className="border-2 border-muted-foreground/40 rounded-sm px-3 py-1.5 rotate-[12deg]">
              <span className="font-mono text-sm font-bold tracking-[0.2em] text-muted-foreground uppercase">Skip</span>
            </div>
          </motion.div>

          {/* UP — Eroding confidence */}
          <motion.div
            style={{ opacity: upOpacity }}
            className="pointer-events-none absolute inset-0 flex items-end justify-center pb-14 rounded-sm"
          >
            <div className="border-2 border-amber-500 rounded-sm px-3 py-1.5">
              <span className="font-mono text-sm font-bold tracking-[0.2em] text-amber-600 uppercase">Eroding</span>
            </div>
          </motion.div>
        </>
      )}
    </motion.div>
  );
}

// ── Stack container ────────────────────────────────────────────────────────

export function EventReviewStack({ events, onReview, reviewingEventId }: Props) {
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());

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
          You&apos;ve reviewed every signal. The thesis stands until something changes.
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
        <p className="font-mono text-[10px] text-muted-foreground/50">
          drag to decide · swipe up to flag
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
          Thesis holds
        </Button>
        <Button
          size="sm"
          variant="outline"
          onClick={() => void handleSwipe("lowered_confidence")}
          disabled={!!reviewingEventId}
        >
          Eroding
        </Button>
        <Button
          size="sm"
          variant="outline"
          onClick={() => void handleSwipe("not_relevant")}
          disabled={!!reviewingEventId}
        >
          Skip
        </Button>
        <Button
          size="sm"
          variant="destructive"
          onClick={() => void handleInvalidate()}
          disabled={!!reviewingEventId}
        >
          Broken
        </Button>
      </div>
    </div>
  );
}
