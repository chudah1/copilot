"use client";

import { useEffect, useEffectEvent, useState } from "react";
import { motion, useMotionValue, useTransform, AnimatePresence } from "framer-motion";
import { Textarea } from "@/components/ui/textarea";
import { getErrorMessage } from "@/lib/errors";
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
  const normalizedText = text.replace(/\\n/g, "\n");
  const structuredKeys = new Set([
    "Your thesis",
    "You said",
    "Your reason",
    "We were watching",
    "What the app was checking",
    "We watched",
    "What changed",
    "What happened",
    "Why this matters now",
    "Why it matters now",
    "Next step",
    "Verdict",
  ]);
  const out: Record<string, string> = {};
  const body: string[] = [];
  for (const line of normalizedText.split("\n")) {
    const i = line.indexOf(":");
    if (i > 0 && i < 28) {
      const k = line.slice(0, i).trim();
      const v = line.slice(i + 1).trim().replace(/^"|"$/g, "");
      if (v && structuredKeys.has(k)) {
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

function verdictLabel(
  verdict: MonitoringEvent["verdict"],
  investorProfile?: "thesis_driven" | "hearsay_driven" | null,
) {
  const subject = investorProfile === "hearsay_driven"
    ? "reason"
    : investorProfile === "thesis_driven"
      ? "thesis"
      : "case";

  if (verdict === "supports") return `Supports ${subject}`;
  if (verdict === "threatens") return `Threatens ${subject}`;
  if (verdict === "review") return "Needs review";
  return "Neutral";
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
      right: "Holds",
      up: "Weaker",
      left: "Noise",
      buttonHold: "Thesis holds",
      buttonErode: "Less sure",
      buttonSkip: "Noise",
      buttonBroken: "Broken",
      reviewHint: "drag to decide · swipe up to flag weakening confidence",
      allCaughtUp: "Every alert reviewed.",
      noteLabel: "Note",
      notePlaceholder: "Optional note",
      noteHelper: "Optional. Saved to the decision log.",
      actionLabel: "Decide",
      keyboardHint: "→ holds · ↑ weaker · ← noise · X broken",
      descriptions: {
        reaffirmed: "Keep the thesis intact.",
        lowered_confidence: "The thesis still holds, but with less conviction.",
        not_relevant: "This does not matter to the thesis.",
        invalidated: "The thesis is broken.",
      },
    };
  }

  if (investorProfile === "hearsay_driven") {
    return {
      right: "Holds",
      up: "Less sure",
      left: "Noise",
      buttonHold: "Reason holds",
      buttonErode: "Less sure now",
      buttonSkip: "Noise",
      buttonBroken: "Broken",
      reviewHint: "drag to decide · swipe up if the story feels weaker",
      allCaughtUp: "Every alert reviewed.",
      noteLabel: "Note",
      notePlaceholder: "Optional note",
      noteHelper: "Optional. Saved to the decision log.",
      actionLabel: "Decide",
      keyboardHint: "→ holds · ↑ less sure · ← noise · X broken",
      descriptions: {
        reaffirmed: "Keep the story intact.",
        lowered_confidence: "The story still holds, but with less conviction.",
        not_relevant: "This is noise relative to the reason.",
        invalidated: "The story is broken.",
      },
    };
  }

  return {
    right: "Holds",
    up: "Eroding",
    left: "Noise",
    buttonHold: "Case holds",
    buttonErode: "Eroding",
    buttonSkip: "Noise",
    buttonBroken: "Broken",
    reviewHint: "drag to decide · swipe up to flag",
    allCaughtUp: "Every alert reviewed.",
    noteLabel: "Note",
    notePlaceholder: "Optional note",
    noteHelper: "Optional. Saved to the decision log.",
    actionLabel: "Decide",
    keyboardHint: "→ holds · ↑ weaker · ← noise · X broken",
    descriptions: {
      reaffirmed: "Keep the case intact.",
      lowered_confidence: "The case still holds, but with less conviction.",
      not_relevant: "This should not move the case.",
      invalidated: "The case is broken.",
    },
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
              {verdictLabel(verdict, investorProfile)}
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
  const [notesByEvent, setNotesByEvent] = useState<Record<string, string>>({});
  const [actionErrorsByEvent, setActionErrorsByEvent] = useState<Record<string, string>>({});
  const copy = reviewCopy(investorProfile);
  const pending = events;
  const topEvent = pending[0];
  const note = topEvent ? (notesByEvent[topEvent.id] ?? "") : "";
  const actionError = topEvent ? (actionErrorsByEvent[topEvent.id] ?? "") : "";

  const submitReview = async (action: ReviewAction) => {
    if (!topEvent || reviewingEventId) return;
    try {
      setActionErrorsByEvent((current) => ({ ...current, [topEvent.id]: "" }));
      await onReview(topEvent, action, note);
    } catch (error) {
      setActionErrorsByEvent((current) => ({
        ...current,
        [topEvent.id]: getErrorMessage(error, "Failed to save review"),
      }));
    }
  };
  const handleShortcutReview = useEffectEvent((action: ReviewAction) => {
    void submitReview(action);
  });

  useEffect(() => {
    if (!topEvent || reviewingEventId) return;

    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      const tag = target?.tagName;
      if (tag === "TEXTAREA" || tag === "INPUT" || target?.isContentEditable) return;

      if (event.key === "ArrowRight") {
        event.preventDefault();
        handleShortcutReview("reaffirmed");
      } else if (event.key === "ArrowLeft") {
        event.preventDefault();
        handleShortcutReview("not_relevant");
      } else if (event.key === "ArrowUp") {
        event.preventDefault();
        handleShortcutReview("lowered_confidence");
      } else if (event.key.toLowerCase() === "x") {
        event.preventDefault();
        handleShortcutReview("invalidated");
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [topEvent, reviewingEventId]);

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
        <div>
          <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
            {pending.length} left
          </p>
          <p className="mt-1 font-sans text-xs text-muted-foreground/80">
            {copy.keyboardHint}
          </p>
        </div>
        <p className="font-mono text-[10px] text-muted-foreground/80">
          swipe or keys
        </p>
      </div>

      {/* Card stack */}
      <div className="relative h-[340px] sm:h-[360px]">
        <AnimatePresence>
          {visibleCards.map((event, index) => (
            <motion.div
              key={event.id}
              className="absolute inset-0"
              exit={
                index === 0
                  ? {
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
                onSwipe={(action) => void submitReview(action)}
                busy={!!reviewingEventId}
                investorProfile={investorProfile}
              />
            </motion.div>
          ))}
        </AnimatePresence>
      </div>

      <div className="product-panel overflow-hidden">
        <div className="grid gap-0 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)]">
          <div className="space-y-3 p-4 sm:p-5">
            <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
              {copy.noteLabel}
            </p>
            <Textarea
              value={note}
              onChange={(event) => {
                if (!topEvent) return;
                setNotesByEvent((current) => ({
                  ...current,
                  [topEvent.id]: event.target.value,
                }));
              }}
              placeholder={copy.notePlaceholder}
              className="min-h-28 bg-background/85"
            />
            {actionError && (
              <p className="font-sans text-sm text-red-600">
                {actionError}
              </p>
            )}
          </div>

          <div className="border-t border-border/60 bg-muted/15 p-4 sm:p-5 lg:border-l lg:border-t-0">
            <div className="space-y-3">
              <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                {copy.actionLabel}
              </p>

              <div className="grid gap-3 sm:grid-cols-2">
                <button
                  type="button"
                  onClick={() => void submitReview("reaffirmed")}
                  disabled={!!reviewingEventId}
                  className="border border-emerald-500/25 bg-emerald-500/8 p-4 text-left transition-colors hover:bg-emerald-500/12 disabled:opacity-40"
                >
                  <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-emerald-700">
                    Hold
                  </p>
                  <p className="mt-2 font-sans text-sm text-foreground">{copy.buttonHold}</p>
                  <p className="mt-1 font-sans text-xs leading-relaxed text-foreground/70">
                    {copy.descriptions.reaffirmed}
                  </p>
                </button>

                <button
                  type="button"
                  onClick={() => void submitReview("lowered_confidence")}
                  disabled={!!reviewingEventId}
                  className="border border-amber-500/25 bg-amber-500/8 p-4 text-left transition-colors hover:bg-amber-500/12 disabled:opacity-40"
                >
                  <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-amber-700">
                    Weaker
                  </p>
                  <p className="mt-2 font-sans text-sm text-foreground">{copy.buttonErode}</p>
                  <p className="mt-1 font-sans text-xs leading-relaxed text-foreground/70">
                    {copy.descriptions.lowered_confidence}
                  </p>
                </button>

                <button
                  type="button"
                  onClick={() => void submitReview("not_relevant")}
                  disabled={!!reviewingEventId}
                  className="border border-border/70 bg-background/80 p-4 text-left transition-colors hover:bg-background disabled:opacity-40"
                >
                  <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                    Noise
                  </p>
                  <p className="mt-2 font-sans text-sm text-foreground">{copy.buttonSkip}</p>
                  <p className="mt-1 font-sans text-xs leading-relaxed text-foreground/70">
                    {copy.descriptions.not_relevant}
                  </p>
                </button>

                <button
                  type="button"
                  onClick={() => void submitReview("invalidated")}
                  disabled={!!reviewingEventId}
                  className="border border-red-500/25 bg-red-500/8 p-4 text-left transition-colors hover:bg-red-500/12 disabled:opacity-40"
                >
                  <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-red-700">
                    Break
                  </p>
                  <p className="mt-2 font-sans text-sm text-foreground">{copy.buttonBroken}</p>
                  <p className="mt-1 font-sans text-xs leading-relaxed text-foreground/70">
                    {copy.descriptions.invalidated}
                  </p>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
