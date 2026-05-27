"use client";

import { startTransition, useEffect, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import { api } from "@/lib/api";
import { getErrorMessage } from "@/lib/errors";
import { formatCurrency, formatDate } from "@/lib/utils";
import { toast } from "sonner";
import { ThesisCard } from "@/components/thesis/thesis-card";
import { ConvictionLog } from "@/components/thesis/conviction-log";
import { ThesisDecompositionReview } from "@/components/thesis/thesis-decomposition-review";
import { ThesisEditor } from "@/components/thesis/thesis-editor";
import { EventTimeline } from "@/components/monitoring/event-timeline";
import { EventReviewStack } from "@/components/monitoring/event-review-stack";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { ThesisHealthCheck } from "@/components/thesis/thesis-health-check";
import { CounterThesisCard } from "@/components/thesis/counter-thesis-card";
import { CheckNowButton } from "@/components/monitoring/check-now-button";
import { EarningsReviewModal } from "@/components/thesis/earnings-review-modal";
import type {
  CheckNowResponse,
  ConfirmDecompositionRequest,
  ConvictionLogResponse,
  HealthCheckResult,
  Holding,
  MonitoringEvent,
  MonitoringEventReviewResponse,
  OnboardingState,
  Thesis,
  ThesisAssistResponse,
  ThesisDecompositionEnvelope,
  UpcomingEarnings,
} from "@/types";

type TabId = "thesis" | "monitoring" | "history";
type NextStepAction = "edit" | "generate_signals" | "confirm_signals" | "monitoring";

interface NextStepNotice {
  eyebrow: string;
  title: string;
  body: string;
  ctaLabel?: string;
  action?: NextStepAction;
}

function cleanTicker(ticker: string) {
  return ticker.replace(/_US_EQ$/, "").replace(/_EQ$/, "");
}

function ageInDays(dateString: string) {
  const now = Date.now();
  const then = new Date(dateString).getTime();
  return Math.max(0, Math.floor((now - then) / (1000 * 60 * 60 * 24)));
}

function getStalePressure(thesis: Thesis | undefined) {
  if (!thesis) return null;

  const daysOld = ageInDays(thesis.updated_at);
  const cadenceDays = Math.max(thesis.review_cadence_days || 30, 14);
  const monitorability =
    thesis.interpretation && typeof thesis.interpretation.monitorability === "string"
      ? thesis.interpretation.monitorability
      : null;

  let watchThreshold = Math.max(cadenceDays, 21);
  let reviewThreshold = Math.max(cadenceDays * 3, 120);

  if (thesis.confidence === "high") {
    watchThreshold = Math.max(watchThreshold - 7, 21);
    reviewThreshold = Math.max(reviewThreshold - 14, 90);
  }

  if (monitorability === "low") {
    watchThreshold = Math.max(watchThreshold - 7, 14);
    reviewThreshold = Math.max(reviewThreshold - 14, 75);
  }

  if (daysOld >= reviewThreshold) {
    return {
      level: "review" as const,
      daysOld,
      cadenceDays,
    };
  }

  if (daysOld >= watchThreshold) {
    return {
      level: "watch" as const,
      daysOld,
      cadenceDays,
    };
  }

  return null;
}

function getThesisInsights(
  thesis: Thesis | undefined,
  events: MonitoringEvent[],
  investorProfile: "thesis_driven" | "hearsay_driven" | null,
) {
  if (!thesis) {
    return {
      nextStep:
        investorProfile === "hearsay_driven"
          ? "Start by turning the original story into a real business reason this app can monitor."
          : "Write your thesis for this position so monitoring has something concrete to watch.",
      qualityLabel: "No reason yet",
      qualityTone: "bg-red-500/15 text-red-600",
      statusDot: "text-red-500",
      watchStatus:
        investorProfile === "hearsay_driven"
          ? "Right now this position has no written reason attached to it, so we can't tell what matters from headline noise."
          : "This position is not being monitored against any written belief yet.",
      canReaffirm: false,
    };
  }

  const interpretation = thesis.interpretation ?? {};
  const monitorability = typeof interpretation.monitorability === "string" ? interpretation.monitorability : "medium";
  const ambiguity = typeof interpretation.ambiguity_note === "string" ? interpretation.ambiguity_note : "";
  const stalePressure = getStalePressure(thesis);
  const latestEvent = events[0];

  if (thesis.status === "needs_review") {
    return {
      nextStep: latestEvent?.ai_analysis || "Review what changed and decide whether your reason still holds.",
      qualityLabel: "Needs review",
      qualityTone: "bg-orange-500/15 text-orange-600",
      statusDot: "text-orange-500",
      watchStatus: "Monitoring found something that hits your reason — worth a look.",
      canReaffirm: true,
    };
  }

  if (stalePressure) {
    return {
      nextStep:
        stalePressure.level === "review"
          ? "This reason is way past due for a re-read. Update or drop it before you treat it as live conviction."
          : "This reason is overdue for review. Re-read it and either confirm it or tighten the language.",
      qualityLabel: stalePressure.level === "review" ? "Needs refresh" : "Stale",
      qualityTone: "bg-amber-500/15 text-amber-700",
      statusDot: "text-amber-500",
      watchStatus:
        stalePressure.level === "review"
          ? `Nothing necessarily broke, but this reasoning is ${stalePressure.daysOld} days old and far past its ${stalePressure.cadenceDays}-day review cadence.`
          : `Nothing necessarily broke, but this reasoning is ${stalePressure.daysOld} days old and overdue for its ${stalePressure.cadenceDays}-day review cadence.`,
      canReaffirm: true,
    };
  }

  if (monitorability === "low") {
    return {
      nextStep:
        ambiguity ||
        (investorProfile === "hearsay_driven"
          ? "Tighten this story into a clearer business reason and a sharper break condition."
          : "Tighten the thesis so we can monitor something more precise."),
      qualityLabel: "Weak signals",
      qualityTone: "bg-muted text-muted-foreground",
      statusDot: "text-muted-foreground",
      watchStatus:
        investorProfile === "hearsay_driven"
          ? "The current reason still reads more like a narrative than a thesis."
          : "The current reason is too vague for reliable monitoring.",
      canReaffirm: false,
    };
  }

  return {
    nextStep: latestEvent ? latestEvent.ai_analysis || "Monitoring is active. Review the latest event if it still matters." : "Your reason looks healthy. No action needed.",
    qualityLabel: "Intact",
    qualityTone: "bg-emerald-500/15 text-emerald-700",
    statusDot: "text-emerald-500",
    watchStatus: latestEvent ? "Monitoring has context to evaluate new changes against your reason." : "Monitoring is active, nothing meaningful flagged yet.",
    canReaffirm: false,
  };
}

function positionCopy(investorProfile: "thesis_driven" | "hearsay_driven" | null) {
  if (investorProfile === "thesis_driven") {
    return {
      earningsEmpty: "Tighten your thesis so we know which assumption should matter the morning after.",
      postEarningsReview: "Review which assumption still holds after the quarter landed.",
      noReasonTitle: "No thesis written yet.",
      noReasonBody: "Write the core reason, the assumption that must stay true, and the condition that would break the thesis.",
      noReasonCta: "Write your thesis",
      monitoringEmptyTitle: "Nothing to monitor yet.",
      monitoringEmptyBody: "Write your thesis first — monitoring needs an specific assumption set to test against.",
      monitoringEmptyCta: "Go to your thesis →",
      afterEarningsCta: "After earnings?",
    };
  }

  if (investorProfile === "hearsay_driven") {
    return {
      earningsEmpty: "Turn the original story into a reason first, so we know what evidence should matter the morning after.",
      postEarningsReview: "Review whether the original story still holds now that the quarter is out.",
      noReasonTitle: "No reason written yet.",
      noReasonBody: "Start with the story behind the position, then turn it into a concrete reason, what has to stay true, and what would break it.",
      noReasonCta: "Write your reason",
      monitoringEmptyTitle: "Nothing to check yet.",
      monitoringEmptyBody: "Write the real reason first — without that, we can't tell what matters from noise.",
      monitoringEmptyCta: "Go to your reason →",
      afterEarningsCta: "After earnings?",
    };
  }

  return {
    earningsEmpty: "Tighten your reason so we know what evidence should matter the morning after.",
    postEarningsReview: "Review whether your reason still holds.",
    noReasonTitle: "No reason written yet.",
    noReasonBody: "Start with the reason this position exists, what has to stay true, and what would make you rethink it.",
    noReasonCta: "Write your reason",
    monitoringEmptyTitle: "Nothing to watch yet.",
    monitoringEmptyBody: "Write your reason first — monitoring needs an written belief to test against.",
    monitoringEmptyCta: "Go to your reason →",
    afterEarningsCta: "After earnings?",
  };
}

function getDecisionPrompt(
  thesis: Thesis | undefined,
  events: MonitoringEvent[],
  investorProfile: "thesis_driven" | "hearsay_driven" | null,
) {
  if (!thesis) {
    return {
      eyebrow: "Before you add more",
      title:
        investorProfile === "hearsay_driven"
          ? "Do not add to a story you have not written down yet."
          : "Do not add to a position before the thesis is explicit.",
      body:
        investorProfile === "hearsay_driven"
          ? "Turn the original story into a real reason first, or it becomes too easy to size up a hope trade."
          : "Write the thesis, what must remain true, and what would break it before treating this like conviction.",
      ctaLabel: investorProfile === "thesis_driven" ? "Write the thesis now →" : "Write the reason now →",
      action: "edit" as const,
      tone: "border-amber-500/25 bg-amber-500/8",
    };
  }

  const monitorability =
    thesis.interpretation && typeof thesis.interpretation.monitorability === "string"
      ? thesis.interpretation.monitorability
      : null;
  const ambiguity =
    thesis.interpretation && typeof thesis.interpretation.ambiguity_note === "string"
      ? thesis.interpretation.ambiguity_note
      : "";
  const stalePressure = getStalePressure(thesis);
  const unresolvedEvent = events.find((event) => !event.review_action);

  if (thesis.status === "needs_review" && unresolvedEvent) {
    return {
      eyebrow: "Before you add more",
      title:
        investorProfile === "hearsay_driven"
          ? "Resolve whether the original story still holds."
          : "Resolve this thesis review before you add.",
      body:
        unresolvedEvent.ai_analysis ||
        unresolvedEvent.evidence_summary ||
        (investorProfile === "hearsay_driven"
          ? "New evidence already challenged the story behind this position. Review it before increasing size."
          : "New evidence already challenged part of this thesis. Review it before increasing size."),
      ctaLabel: "Review the latest evidence →",
      action: "monitoring" as const,
      tone: "border-red-500/25 bg-red-500/8",
    };
  }

  if (monitorability === "low" || ambiguity) {
    return {
      eyebrow: "Before you size up",
      title:
        investorProfile === "hearsay_driven"
          ? "The reason is still too story-like."
          : "The thesis is still too vague.",
      body:
        ambiguity ||
        (investorProfile === "hearsay_driven"
          ? "Make the business driver and break condition clearer before you commit more capital."
          : "Tighten the assumptions before you commit more capital."),
      ctaLabel: investorProfile === "hearsay_driven" ? "Tighten the reason →" : "Tighten the thesis →",
      action: "edit" as const,
      tone: "border-sky-500/25 bg-sky-500/8",
    };
  }

  if (stalePressure) {
    return {
      eyebrow: "Before you keep holding on autopilot",
      title:
        investorProfile === "hearsay_driven"
          ? "Would you still buy this today for the same reason?"
          : "Would you still buy this today for the same thesis?",
      body:
        investorProfile === "hearsay_driven"
          ? `This reason is ${stalePressure.daysOld} days old and behind its ${stalePressure.cadenceDays}-day review cadence. Re-read it before treating this as active conviction.`
          : `This thesis is ${stalePressure.daysOld} days old and past its ${stalePressure.cadenceDays}-day check-in. Re-read it before you treat it as live conviction.`,
      ctaLabel: "Re-read and refresh it →",
      action: "edit" as const,
      tone: "border-amber-500/25 bg-amber-500/8",
    };
  }

  return null;
}

function getThesisHandoffPrompt(args: {
  hasThesis: boolean;
  hasSignals: boolean;
  hasActiveSignals: boolean;
  decompositionStatus: string | null;
  investorProfile: "thesis_driven" | "hearsay_driven" | null;
}) {
  const { hasThesis, hasSignals, hasActiveSignals, decompositionStatus, investorProfile } = args;
  if (!hasThesis) return null;

  if (!hasSignals) {
    return {
      title:
        investorProfile === "hearsay_driven"
          ? "The reason is written. Next, define what would really test it."
          : "The thesis is written. Next, define what would really test it.",
      body:
        investorProfile === "hearsay_driven"
          ? "Build the first watchlist so we know which evidence should count against this reason and which noise to ignore."
          : "Build the first watchlist so we know which evidence should count against this thesis and which noise to ignore.",
      ctaLabel: "Define the first watchlist →",
      action: "generate" as const,
    };
  }

  if (!hasActiveSignals || decompositionStatus === "draft" || decompositionStatus === "partially_confirmed") {
    return {
      title:
        investorProfile === "hearsay_driven"
          ? "The watchlist is ready. Now confirm what should count."
          : "The watchlist is ready. Now confirm what should count.",
      body:
        investorProfile === "hearsay_driven"
          ? "We already suggested a monitoring setup. Review it once so future alerts reflect the reason you actually mean."
          : "We already suggested a monitoring setup. Review it once so future alerts reflect the thesis you actually mean.",
      ctaLabel: "Review signals →",
      action: "monitoring" as const,
    };
  }

  return null;
}

function getBlindSpotArrivalCopy(investorProfile: "thesis_driven" | "hearsay_driven" | null) {
  if (investorProfile == "hearsay_driven") {
    return {
      eyebrow: "Blind spot",
      title: "This position still has no written reason.",
      body: "Until you turn the original story into a real reason, we can't tell signal from panic here.",
      cta: "Write the real reason now →",
    };
  }

  if (investorProfile === "thesis_driven") {
    return {
      eyebrow: "Blind spot",
      title: "This position still has no written thesis.",
      body: "Until you've written the thesis, we can't tell whether new evidence is noise or a real assumption break.",
      cta: "Write the thesis now →",
    };
  }

  return {
    eyebrow: "Blind spot",
    title: "This position still has no written reason.",
    body: "Until you've written the reason, we can't tell whether new evidence should change your mind.",
    cta: "Write the reason now →",
  };
}

function getMonitoringCalmState(args: {
  hasReviewedEvents: boolean;
  lastReviewedEventAgeDays: number | null;
  upcomingEarnings: UpcomingEarnings | null;
  monitoringPreviewItems: Array<{ key: string; label: string; detail: string }>;
  watchHints: string[];
  activeSignalCount: number;
  investorProfile: "thesis_driven" | "hearsay_driven" | null;
}) {
  const {
    hasReviewedEvents,
    lastReviewedEventAgeDays,
    upcomingEarnings,
    monitoringPreviewItems,
    watchHints,
    activeSignalCount,
    investorProfile,
  } = args;

  const title =
    investorProfile === "hearsay_driven"
      ? "Reason intact. Nothing needs a decision right now."
      : "Thesis intact. Nothing needs a decision right now.";

  const body = hasReviewedEvents
    ? `All reviewed evidence is on file${lastReviewedEventAgeDays != null ? ` and the last decision was ${lastReviewedEventAgeDays} day${lastReviewedEventAgeDays === 1 ? "" : "s"} ago` : ""}.`
    : investorProfile === "hearsay_driven"
      ? `Monitoring is live and now watching ${activeSignalCount > 0 ? `${activeSignalCount} watchpoint${activeSignalCount === 1 ? "" : "s"}` : "your first watchlist"} so the next interruption is tied to the reason you wrote down.`
      : `Monitoring is live and now watching ${activeSignalCount > 0 ? `${activeSignalCount} watchpoint${activeSignalCount === 1 ? "" : "s"}` : "your first watchlist"} so the next interruption is tied to the thesis you wrote down.`;

  const nextCheck =
    upcomingEarnings && upcomingEarnings.days_until >= 0 && upcomingEarnings.days_until <= 30
      ? `Next likely checkpoint: earnings ${upcomingEarnings.days_until === 0 ? "today" : upcomingEarnings.days_until === 1 ? "tomorrow" : `in ${upcomingEarnings.days_until} days`}.`
      : activeSignalCount > 0
        ? `We're watching ${activeSignalCount} signal${activeSignalCount === 1 ? "" : "s"} on this position.`
        : "We're waiting for news that actually hits one of your assumptions.";

  return {
    title,
    body,
    nextCheck,
    previewItems: monitoringPreviewItems.slice(0, 2),
    fallbackHints: watchHints.slice(0, 2),
  };
}

const METRIC_LABELS: Record<string, string> = {
  revenue_growth_yoy: "Revenue growth (YoY)",
  earnings_growth_yoy: "Earnings growth (YoY)",
  pe_ratio: "P/E ratio",
  dividend_yield: "Dividend yield",
  gross_margin: "Gross margin",
  operating_margin: "Operating margin",
  debt_to_equity: "Debt / equity",
};

function formatThreshold(unit: string | undefined, value: number): string {
  if (unit === "pct") {
    const pct = value <= 1 && value >= -1 ? value * 100 : value;
    return `${pct % 1 === 0 ? pct.toFixed(0) : pct.toFixed(1)}%`;
  }
  return String(value);
}

function describeWatchHint(hint: Record<string, unknown>) {
  if (hint.kind === "price_move_pct" && typeof hint.threshold === "number") {
    return `Price discipline if the stock moves ${hint.threshold}% or more.`;
  }
  if (
    hint.kind === "metric_threshold" &&
    typeof hint.metric === "string" &&
    typeof hint.operator === "string" &&
    typeof hint.threshold === "number"
  ) {
    if (hint.threshold === 0) {
      return null;
    }
    const label = typeof hint.label === "string" ? hint.label : (METRIC_LABELS[hint.metric] ?? hint.metric.replaceAll("_", " "));
    const unit = typeof hint.unit === "string" ? hint.unit : undefined;
    return `${label} stays ${hint.operator} ${formatThreshold(unit, hint.threshold)}.`;
  }
  return null;
}

function getMonitoringPreviewItems(
  decompositionEnvelope: ThesisDecompositionEnvelope | null,
  fallbackWatchHints: Record<string, unknown>[],
) {
  const signalItems =
    decompositionEnvelope?.decomposition?.claims.flatMap((claim) =>
      claim.entities.flatMap((entity) =>
        entity.signals
          .filter((signal) => signal.active)
          .map((signal) => ({
            key: signal.id,
            label: signal.signal_label || signal.signal_type.replaceAll("_", " "),
            detail: signal.rationale || `Watch ${entity.entity_name} for evidence tied to this thesis signal.`,
          })),
      ),
    ) ?? [];

  if (signalItems.length > 0) {
    return signalItems.slice(0, 3);
  }

  return fallbackWatchHints
    .map((hint, index) => {
      const label = describeWatchHint(hint);
      if (!label) return null;
      return {
        key: `watch_hint_${index}`,
        label,
        detail:
          typeof hint.rationale === "string" && hint.rationale.trim()
            ? hint.rationale.trim()
            : "This is the first monitoring rule we can evaluate against your reason.",
      };
    })
    .filter((item): item is { key: string; label: string; detail: string } => Boolean(item))
    .slice(0, 3);
}

function buildPostSaveNotice(args: {
  investorProfile: "thesis_driven" | "hearsay_driven" | null;
  blindSpotStart?: boolean;
}): NextStepNotice {
  const { investorProfile, blindSpotStart = false } = args;
  if (blindSpotStart) {
    return {
      eyebrow: "Blind spot closed",
      title:
        investorProfile === "hearsay_driven"
          ? "Now choose what should actually test this reason."
          : "Now choose what should actually test this thesis.",
      body:
        investorProfile === "hearsay_driven"
          ? "The position now has a real written reason. Generate the first watchlist so the next alert is tied to the story you actually mean."
          : "The position now has a real written thesis. Generate the first watchlist so the next alert is tied to the assumption you actually mean.",
      ctaLabel: "Generate the first watchlist →",
      action: "generate_signals",
    };
  }

  return {
    eyebrow: "Reason saved",
    title:
      investorProfile === "hearsay_driven"
        ? "Next, choose what parts of the story to watch."
        : "Next, turn the thesis into watchable signals.",
    body:
      investorProfile === "hearsay_driven"
        ? "Your reason is written down. Generate signal candidates now so we can separate real evidence from headline churn."
        : "Your thesis is saved. Generate signal candidates now so monitoring knows which assumptions should matter.",
    ctaLabel: "Generate signals now →",
    action: "generate_signals",
  };
}

function buildPostDecompositionNotice(
  envelope: ThesisDecompositionEnvelope,
  investorProfile: "thesis_driven" | "hearsay_driven" | null,
): NextStepNotice {
  if (envelope.status === "failed" || envelope.status === "pending") {
    return {
      eyebrow: "Signal generation failed",
      title: "Something went wrong mapping your reason.",
      body: envelope.message || "This happens occasionally. Try again — it usually works on the second attempt.",
      ctaLabel: "Try again →",
      action: "generate_signals",
    };
  }

  return {
    eyebrow: "Signals ready",
    title:
      investorProfile === "hearsay_driven"
        ? "Review the first tests for this reason."
        : "Review the first tests for this thesis.",
    body:
      investorProfile === "hearsay_driven"
        ? "The recommended setup is preselected. Keep it if it matches the story you meant, or edit signal by signal."
        : "The recommended setup is preselected. Keep it if it matches your thesis, or edit signal by signal.",
    ctaLabel: "Review the first watchlist →",
    action: "confirm_signals",
  };
}

function buildPostConfirmationNotice(args: {
  investorProfile: "thesis_driven" | "hearsay_driven" | null;
  activeSignalCount: number;
}): NextStepNotice {
  const { investorProfile, activeSignalCount } = args;
  const signalText =
    activeSignalCount > 0
      ? `${activeSignalCount} watchpoint${activeSignalCount === 1 ? "" : "s"}`
      : "an watchlist";

  return {
    eyebrow: "Monitoring setup confirmed",
    title:
      investorProfile === "hearsay_driven"
        ? "Alerts now only fire when something hits your reason."
        : "Alerts now only fire when something hits your thesis.",
    body:
      investorProfile === "hearsay_driven"
        ? `It is now watching ${signalText}, and it will only pull you back when a real change tests the story you wrote down.`
        : `It is now watching ${signalText}, and it will only pull you back when a real change tests the thesis you wrote down.`,
    ctaLabel: "See what is now being watched →",
    action: "monitoring",
  };
}

function buildPostReviewClearNotice(
  investorProfile: "thesis_driven" | "hearsay_driven" | null,
): NextStepNotice {
  return {
    eyebrow: "Decision logged",
    title:
      investorProfile === "hearsay_driven"
        ? "The reason is back in a monitored, quiet state."
        : "The thesis is back in a monitored, quiet state.",
    body:
      investorProfile === "hearsay_driven"
        ? "There is nothing else to decide right now. The next meaningful change will appear here when it tests your reason again."
        : "There is nothing else to decide right now. The next meaningful change will appear here when it tests your thesis again.",
    ctaLabel: "Stay on monitoring →",
    action: "monitoring",
  };
}

function buildPostInvalidationNotice(
  investorProfile: "thesis_driven" | "hearsay_driven" | null,
): NextStepNotice {
  return {
    eyebrow: "Reason broken",
    title:
      investorProfile === "hearsay_driven"
        ? "This position now needs a new reason or a sell decision."
        : "This position now needs a new thesis or a sell decision.",
    body:
      investorProfile === "hearsay_driven"
        ? "You logged that the original story no longer holds. Rework the reason on the thesis tab if you still want to own it."
        : "You logged that the thesis no longer holds. Rework the thesis on the thesis tab if you still want to own it.",
    ctaLabel: investorProfile === "thesis_driven" ? "Rewrite the thesis →" : "Rewrite the reason →",
    action: "edit",
  };
}

function buildCheckNowNotice(args: {
  result: CheckNowResponse;
  investorProfile: "thesis_driven" | "hearsay_driven" | null;
}): NextStepNotice {
  const { result, investorProfile } = args;
  if (result.events_created > 0) {
    return {
      eyebrow: "Fresh evidence found",
      title:
        investorProfile === "hearsay_driven"
          ? `${result.events_created} change${result.events_created !== 1 ? "s" : ""} may test your reason.`
          : `${result.events_created} change${result.events_created !== 1 ? "s" : ""} may test your thesis.`,
      body:
        investorProfile === "hearsay_driven"
          ? "Something new landed that may change the story. Review it below while it's still fresh."
          : "Something new landed that may change the thesis. Review it below while it's still fresh.",
      ctaLabel: "Review the new evidence →",
      action: "monitoring",
    };
  }

  return {
    eyebrow: "Check complete",
    title:
      investorProfile === "hearsay_driven"
        ? "Nothing meaningful changed for this reason."
        : "Nothing meaningful changed for this thesis.",
    body:
      investorProfile === "hearsay_driven"
        ? "We checked what's available — nothing yet that forces a call on your reason."
        : "We checked what's available — nothing yet that forces a call on your thesis.",
    ctaLabel: "Stay on monitoring →",
    action: "monitoring",
  };
}

function isRecentEvent(dateString: string, days: number) {
  const ageMs = Date.now() - new Date(dateString).getTime();
  return ageMs >= 0 && ageMs <= days * 24 * 60 * 60 * 1000;
}

function getEventAssumptionLabel(
  event: MonitoringEvent,
  investorProfile: "thesis_driven" | "hearsay_driven" | null,
) {
  if (event.signal_label && event.signal_label.trim()) {
    return event.signal_label.trim();
  }

  if (event.title && event.title.trim()) {
    return event.title.trim();
  }

  const prefix = investorProfile === "hearsay_driven" ? "this reason" : "this thesis";
  return `${prefix} signal`;
}

// ── Health chip colours ───────────────────────────────────────────────────────

const HEALTH_CHIP: Record<string, string> = {
  Healthy: "text-emerald-700 bg-emerald-500/10",
  "At Risk": "text-amber-700 bg-amber-500/10",
  Broken: "text-red-600 bg-red-500/10",
};

// ── Status dot colour ────────────────────────────────────────────────────────

const STATUS_DOT: Record<string, string> = {
  intact: "bg-emerald-500",
  needs_review: "bg-orange-500",
  stale: "bg-amber-400",
  no_thesis: "bg-red-500",
  low_signal: "bg-border",
};

// ── Page ─────────────────────────────────────────────────────────────────────

export default function PositionDetailPage() {
  const { ticker } = useParams<{ ticker: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<TabId>("thesis");
  const [holdings, setHoldings] = useState<Holding[]>([]);
  const [theses, setTheses] = useState<Thesis[]>([]);
  const [events, setEvents] = useState<MonitoringEvent[]>([]);
  const [decompositionEnvelope, setDecompositionEnvelope] = useState<ThesisDecompositionEnvelope | null>(null);
  const [editing, setEditing] = useState(false);
  const [invalidateOpen, setInvalidateOpen] = useState(false);
  const [invalidateReason, setInvalidateReason] = useState("");
  const [reaffirming, setReaffirming] = useState(false);
  const [decompositionLoading, setDecompositionLoading] = useState(false);
  const [decompositionSaving, setDecompositionSaving] = useState(false);
  const [reviewingEventId, setReviewingEventId] = useState<string | null>(null);
  const [convictionLog, setConvictionLog] = useState<ConvictionLogResponse | null>(null);
  const [convictionLogLoading, setConvictionLogLoading] = useState(false);
  const [noteSaving, setNoteSaving] = useState(false);
  const [upcomingEarnings, setUpcomingEarnings] = useState<UpcomingEarnings | null>(null);
  const [loading, setLoading] = useState(true);
  const [healthCheck, setHealthCheck] = useState<HealthCheckResult | null>(null);
  const [healthCheckLoading, setHealthCheckLoading] = useState(false);
  const [showCounterThesis, setShowCounterThesis] = useState(false);
  const [showAnalysis, setShowAnalysis] = useState(false);
  const [showPositionDetails, setShowPositionDetails] = useState(false);
  const [showEarningsReview, setShowEarningsReview] = useState(false);
  const [onboardingState, setOnboardingState] = useState<OnboardingState | null>(null);
  const [nextStepNotice, setNextStepNotice] = useState<NextStepNotice | null>(null);
  const [hasPromptedBlindSpotEditor, setHasPromptedBlindSpotEditor] = useState(false);
  const [deleteConfirming, setDeleteConfirming] = useState(false);
  const [deleteLoading, setDeleteLoading] = useState(false);

  const holding = holdings.find((h) => h.ticker === ticker);
  const activeThesis = theses.find((t) => t.status === "active" || t.status === "draft" || t.status === "needs_review");
  const fromOnboarding = searchParams.get("source") === "onboarding";
  const fromBlindSpot = searchParams.get("source") === "dashboard_blind_spot";
  const latestInvalidatedThesis = [...theses]
    .filter((t) => t.status === "invalidated")
    .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())[0];

  useEffect(() => {
    async function load() {
      try {
        const h = await api.get<Holding[]>("/api/portfolio/holdings");
        setHoldings(h);
        const match = h.find((x) => x.ticker === ticker);
        if (match) {
          const [t, e, log, earnings, onboarding] = await Promise.all([
            api.get<Thesis[]>(`/api/theses/holding/${match.id}`),
            api.get<MonitoringEvent[]>(`/api/monitoring/holdings/${match.id}/events`),
            api.get<ConvictionLogResponse>(`/api/portfolio/holdings/${match.id}/conviction-log`).catch(() => null),
            api.get<UpcomingEarnings[]>("/api/portfolio/upcoming-earnings").catch(() => []),
            api.get<OnboardingState>("/api/onboarding/state").catch(() => null),
          ]);
          setTheses(t);
          setEvents(e);
          setConvictionLog(log);
          setUpcomingEarnings(earnings.find((item) => item.holding_id === match.id) ?? null);
          setOnboardingState(onboarding);
          const latestThesis = t.find((item) => item.status === "active" || item.status === "draft" || item.status === "needs_review");
          if (latestThesis) {
            setDecompositionLoading(true);
            try {
              const envelope = await api.get<ThesisDecompositionEnvelope>(`/api/theses/${latestThesis.id}/decomposition`);
              setDecompositionEnvelope(envelope);
            } catch (error: unknown) {
              const message = getErrorMessage(error, "Failed to load decomposition");
              if (message.includes("Decomposition not found")) {
                setDecompositionEnvelope(null);
              } else {
                setDecompositionEnvelope({ status: "failed", message, decomposition: null });
              }
            } finally {
              setDecompositionLoading(false);
            }
            // Background health check — detects recent earnings without requiring a monitoring event
            void api.post<HealthCheckResult>(`/api/theses/${latestThesis.id}/health-check`)
              .then(setHealthCheck)
              .catch(() => null);
          } else {
            setDecompositionEnvelope(null);
          }
          // Auto-switch to monitoring if there are unreviewed events
          if (e.some((ev) => !ev.review_action)) {
            setActiveTab("monitoring");
          }
        }
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [ticker]);

  useEffect(() => {
    if (
      loading ||
      hasPromptedBlindSpotEditor ||
      editing ||
      !fromBlindSpot ||
      activeThesis ||
      latestInvalidatedThesis
    ) {
      return;
    }

    const timeoutId = window.setTimeout(() => {
      startTransition(() => {
        setActiveTab("thesis");
        setEditing(true);
        setHasPromptedBlindSpotEditor(true);
      });
    }, 0);

    return () => window.clearTimeout(timeoutId);
  }, [
    activeThesis,
    editing,
    fromBlindSpot,
    hasPromptedBlindSpotEditor,
    latestInvalidatedThesis,
    loading,
  ]);

  const runHealthCheck = async (thesisId: string) => {
    try {
      setHealthCheckLoading(true);
      const result = await api.post<HealthCheckResult>(`/api/theses/${thesisId}/health-check`);
      setHealthCheck(result);
    } catch (err) {
      console.error("Health check failed:", err);
    } finally {
      setHealthCheckLoading(false);
    }
  };

  const refreshCurrentThesis = async () => {
    if (!holding) return;
    const refreshed = await api.get<Thesis[]>(`/api/theses/holding/${holding.id}`);
    setTheses(refreshed);
  };

  const refreshEvents = async () => {
    if (!holding) return;
    const refreshed = await api.get<MonitoringEvent[]>(`/api/monitoring/holdings/${holding.id}/events`);
    setEvents(refreshed);
    return refreshed;
  };

  const refreshConvictionLog = async () => {
    if (!holding) return;
    try {
      setConvictionLogLoading(true);
      const refreshed = await api.get<ConvictionLogResponse>(`/api/portfolio/holdings/${holding.id}/conviction-log`);
      setConvictionLog(refreshed);
    } catch (error) {
      console.error(error);
    } finally {
      setConvictionLogLoading(false);
    }
  };

  const handleAssist = async (draft: {
    why_own_it: string;
    must_remain_true: string;
    what_would_change_my_mind: string;
  }): Promise<ThesisAssistResponse> => {
    if (!holding) throw new Error("Holding not found");
    return api.post<ThesisAssistResponse>("/api/theses/assist", {
      holding_id: holding.id,
      draft_text: draft.why_own_it,
      why_own_it: draft.why_own_it,
      must_remain_true: draft.must_remain_true,
      what_would_change_my_mind: draft.what_would_change_my_mind,
    });
  };

  const handleSave = async (data: {
    thesis_kind: "company";
    why_own_it: string;
    must_remain_true: string | null;
    what_would_change_my_mind: string | null;
    confidence: "high" | "medium" | "low";
    review_cadence_days: number;
    ai_summary: string | null;
    interpretation: Record<string, unknown> | null;
    source: "user" | "ai_assisted";
    status: "active";
  }) => {
    try {
      let savedThesisId: string | null = null;
      if (activeThesis) {
        const updated = await api.put<Thesis>(`/api/theses/${activeThesis.id}`, data);
        setTheses((current) => current.map((t) => (t.id === updated.id ? updated : t)));
        savedThesisId = updated.id;
      } else if (holding) {
        try {
          const created = await api.post<Thesis>("/api/theses", { holding_id: holding.id, ...data });
          setTheses((current) => [created, ...current]);
          savedThesisId = created.id;
        } catch (error) {
          const message = getErrorMessage(error, "");
          if (message === "A current thesis already exists for this holding") {
            const refreshed = await api.get<Thesis[]>(`/api/theses/holding/${holding.id}`);
            setTheses(refreshed);
            const existing = refreshed.find((item) => item.status === "active" || item.status === "draft" || item.status === "needs_review");
            if (!existing) {
              throw error;
            }
            const updated = await api.put<Thesis>(`/api/theses/${existing.id}`, data);
            setTheses((current) => current.map((t) => (t.id === updated.id ? updated : t)));
            savedThesisId = updated.id;
            toast.message("Updated the existing reason for this holding.");
          } else {
            throw error;
          }
        }
      }
      setDecompositionEnvelope(null);
      setEditing(false);
      if (savedThesisId) {
        runHealthCheck(savedThesisId);
        setShowCounterThesis(true);
        setShowAnalysis(true);
        setActiveTab("monitoring");
        setNextStepNotice(buildPostSaveNotice({
          investorProfile: onboardingState?.investor_profile ?? null,
          blindSpotStart: fromBlindSpot && !activeThesis && !latestInvalidatedThesis,
        }));
      }
      await refreshConvictionLog();
    } catch (err) {
      console.error(err);
      toast.error(getErrorMessage(err, "Failed to save reason"));
    }
  };

  const handleInvalidate = async () => {
    if (!activeThesis) return;
    try {
      const updated = await api.post<Thesis>(`/api/theses/${activeThesis.id}/invalidate`, { reason: invalidateReason });
      setTheses(theses.map((t) => (t.id === updated.id ? updated : t)));
      setDecompositionEnvelope(null);
      setInvalidateOpen(false);
      setInvalidateReason("");
      await refreshConvictionLog();
    } catch (err) {
      console.error(err);
    }
  };

  const handleReaffirm = async () => {
    if (!activeThesis) return;
    try {
      setReaffirming(true);
      const updated = await api.post<Thesis>(`/api/theses/${activeThesis.id}/reaffirm`);
      setTheses(theses.map((t) => (t.id === updated.id ? updated : t)));
      await refreshConvictionLog();
    } catch (err) {
      console.error(err);
    } finally {
      setReaffirming(false);
    }
  };

  const handleGenerateDecomposition = async () => {
    if (!activeThesis) return;
    try {
      setDecompositionLoading(true);
      const envelope = await api.post<ThesisDecompositionEnvelope>(`/api/theses/${activeThesis.id}/decompose`);
      setDecompositionEnvelope(envelope);
      setActiveTab("monitoring");
      setNextStepNotice(buildPostDecompositionNotice(envelope, onboardingState?.investor_profile ?? null));
      await refreshCurrentThesis();
    } catch (error) {
      const message = getErrorMessage(error, "Failed to generate thesis signals");
      setDecompositionEnvelope({ status: "failed", message, decomposition: null });
    } finally {
      setDecompositionLoading(false);
    }
  };

  const handleConfirmDecomposition = async (payload: ConfirmDecompositionRequest) => {
    if (!activeThesis) return;
    try {
      setDecompositionSaving(true);
      const envelope = await api.post<ThesisDecompositionEnvelope>(`/api/theses/${activeThesis.id}/decomposition/confirm`, payload);
      const confirmedSignalCount =
        envelope.decomposition?.claims.reduce(
          (sum, claim) =>
            sum +
            claim.entities.reduce(
              (entitySum, entity) => entitySum + entity.signals.filter((signal) => signal.active).length,
              0,
            ),
          0,
        ) ?? 0;
      setDecompositionEnvelope(envelope);
      setActiveTab("monitoring");
      setNextStepNotice(
        buildPostConfirmationNotice({
          investorProfile: onboardingState?.investor_profile ?? null,
          activeSignalCount: confirmedSignalCount,
        }),
      );
      await refreshCurrentThesis();
      await refreshConvictionLog();
    } catch (error) {
      toast.error(getErrorMessage(error, "Failed to save signal setup"));
    } finally {
      setDecompositionSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!holding) return;
    try {
      setDeleteLoading(true);
      await api.delete(`/api/portfolio/holdings/${holding.id}`);
      toast.success("Position removed");
      router.push("/dashboard");
    } catch (error) {
      toast.error(getErrorMessage(error, "Failed to remove position"));
      setDeleteConfirming(false);
    } finally {
      setDeleteLoading(false);
    }
  };

  const handleReviewEvent = async (
    event: MonitoringEvent,
    action: "reaffirmed" | "ignored" | "lowered_confidence" | "invalidated" | "not_relevant",
    notes?: string,
  ) => {
    try {
      setReviewingEventId(event.id);
      const result = await api.post<MonitoringEventReviewResponse>(`/api/monitoring/events/${event.id}/review`, {
        action,
        notes: notes?.trim() ? notes.trim() : undefined,
      });
      setTheses((current) => current.map((thesis) => (thesis.id === result.thesis.id ? result.thesis : thesis)));
      const [refreshedEvents] = await Promise.all([refreshEvents(), refreshConvictionLog()]);
      if (action === "invalidated") {
        setActiveTab("thesis");
        setNextStepNotice(buildPostInvalidationNotice(onboardingState?.investor_profile ?? null));
      } else if (refreshedEvents && refreshedEvents.every((candidate) => candidate.review_action)) {
        setActiveTab("monitoring");
        setNextStepNotice(buildPostReviewClearNotice(onboardingState?.investor_profile ?? null));
      }
      if (typeof window !== "undefined") {
        window.localStorage.setItem(
          "dashboard_recent_review",
          JSON.stringify({
            ticker: holding?.ticker,
            action,
            assumption_label: event.signal_label || event.title || null,
            resolved_all: Boolean(refreshedEvents && refreshedEvents.every((candidate) => candidate.review_action)),
            thesis_status: result.thesis.status,
            saved_at: new Date().toISOString(),
          }),
        );
      }
      const ageText = result.reason_age_days != null ? ` Reason age: ${result.reason_age_days} days.` : "";
      toast.success(`Logged. Reason is now ${result.thesis.status.replace("_", " ")}.${ageText}`);
    } catch (error) {
      console.error(error);
      toast.error("Failed to save review");
    } finally {
      setReviewingEventId(null);
    }
  };

  const handleAddManualNote = async (content: string) => {
    if (!holding) return;
    try {
      setNoteSaving(true);
      await api.post(`/api/portfolio/holdings/${holding.id}/conviction-log`, { content });
      await refreshConvictionLog();
    } catch (error) {
      console.error(error);
    } finally {
      setNoteSaving(false);
    }
  };

  const handleCheckNowComplete = async (result: CheckNowResponse) => {
    await refreshEvents();
    await refreshCurrentThesis();
    setActiveTab("monitoring");
    setNextStepNotice(buildCheckNowNotice({
      result,
      investorProfile: onboardingState?.investor_profile ?? null,
    }));
  };

  // ── Loading ──────────────────────────────────────────────────────────────

  if (loading) return (
    <div className="flex items-center justify-center min-h-[calc(100vh-53px)]">
      <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground animate-pulse">Loading…</p>
    </div>
  );

  if (!holding) return (
    <div className="max-w-4xl mx-auto px-8 py-8">
      <p className="text-sm text-muted-foreground">Holding not found for ticker {ticker}</p>
    </div>
  );

  // ── Derived state ────────────────────────────────────────────────────────

  const cost = holding.quantity * holding.average_cost_basis;
  const value = holding.current_value || 0;
  const pnl = value - cost;
  const pnlPct = cost > 0 ? ((pnl / cost) * 100).toFixed(1) : "0.0";
  const thesisInsights = getThesisInsights(
    activeThesis,
    events,
    onboardingState?.investor_profile ?? null,
  );
  const copy = positionCopy(onboardingState?.investor_profile ?? null);
  const latestEvent = events[0];
  const recentEarningsEvent =
    events.find(
      (e) => ["earnings_surprise", "earnings_call_transcript"].includes(e.event_type) && !e.review_action && isRecentEvent(e.created_at, 14),
    ) ?? null;

  // Show earnings review prompt if a monitoring event fired OR health check shows recent earnings
  const showEarningsBanner =
    Boolean(recentEarningsEvent) ||
    (Boolean(healthCheck?.recent_earnings_surprise_pct) && Boolean(activeThesis));
  const hasSignals = Boolean(decompositionEnvelope?.decomposition);
  const hasActiveSignals =
    decompositionEnvelope?.decomposition?.claims.some((claim) =>
      claim.entities.some((entity) => entity.signals.some((signal) => signal.active)),
    ) ?? false;
  const watchHints = Array.isArray(activeThesis?.interpretation?.watch_hints)
    ? activeThesis.interpretation.watch_hints.filter((hint): hint is Record<string, unknown> => typeof hint === "object" && hint !== null)
    : [];
  const monitoringPreviewItems = getMonitoringPreviewItems(decompositionEnvelope, watchHints);
  const earningsWatchList = watchHints.map((h) => describeWatchHint(h)).filter((h): h is string => Boolean(h)).slice(0, 3);
  const unreviewedEvents = events.filter((e) => !e.review_action).length;
  const reviewedEventsCount = events.filter((e) => Boolean(e.review_action)).length;
  const decisionPrompt = getDecisionPrompt(
    activeThesis,
    events,
    onboardingState?.investor_profile ?? null,
  );
  const thesisHandoffPrompt = getThesisHandoffPrompt({
    hasThesis: Boolean(activeThesis),
    hasSignals,
    hasActiveSignals,
    decompositionStatus: decompositionEnvelope?.status ?? null,
    investorProfile: onboardingState?.investor_profile ?? null,
  });
  const onboardingMonitoringMessage = decompositionLoading
    ? "We’re turning your first reason into watchable signals now."
    : decompositionEnvelope?.decomposition
        ? "Your first reason is live and we've started turning it into something monitorable."
        : "Your first reason is live. The next step is to confirm what to actually watch.";
  const onboardingMonitoringNextStep = decompositionLoading
    ? "Next step: give us a moment to finish turning your reason into signal candidates."
    : decompositionEnvelope?.decomposition
      ? "Next step: confirm these signals so monitoring becomes clear enough to trust."
      : "Next step: review the first monitoring rules below and tighten anything that feels vague.";

  const tabs: { id: TabId; label: string; badge?: number | string }[] = [
    { id: "thesis", label: "Your reason" },
    { id: "monitoring", label: "Monitoring", badge: unreviewedEvents > 0 ? unreviewedEvents : undefined },
    { id: "history", label: "History", badge: convictionLog?.entries.length ?? undefined },
  ];

  const steps = [
    { done: !!activeThesis, label: "Thesis" },
    { done: hasActiveSignals, partial: hasSignals && !hasActiveSignals, label: "Signals" },
    { done: !!(latestEvent && latestEvent.review_action), partial: !!(latestEvent && !latestEvent.review_action), label: "Review" },
  ];

  const lastReviewedEvent = events.filter((e) => e.review_action).sort((a, b) =>
    new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  )[0];
  const firstPendingEvent = events.find((event) => !event.review_action) ?? null;
  const isFirstLiveEvidenceMoment = unreviewedEvents > 0 && reviewedEventsCount === 0;
  const activeSignalCount =
    decompositionEnvelope?.decomposition?.claims.reduce(
      (sum, claim) =>
        sum +
        claim.entities.reduce(
          (entitySum, entity) => entitySum + entity.signals.filter((signal) => signal.active).length,
          0,
        ),
      0,
    ) ?? 0;
  const monitoringCalmState = getMonitoringCalmState({
    hasReviewedEvents: events.some((event) => Boolean(event.review_action)),
    lastReviewedEventAgeDays: lastReviewedEvent ? ageInDays(lastReviewedEvent.created_at) : null,
    upcomingEarnings,
    monitoringPreviewItems,
    watchHints: earningsWatchList,
    activeSignalCount,
    investorProfile: onboardingState?.investor_profile ?? null,
  });
  const invalidatedTheses = theses.filter((t) => t.status === "invalidated");
  const blindSpotArrivalCopy = getBlindSpotArrivalCopy(onboardingState?.investor_profile ?? null);
  const firstPendingAssumptionLabel = firstPendingEvent
    ? getEventAssumptionLabel(firstPendingEvent, onboardingState?.investor_profile ?? null)
    : null;
  const editorSeedThesis = activeThesis ?? latestInvalidatedThesis ?? null;
  const stalePressure = activeThesis ? getStalePressure(activeThesis) : null;
  const editorMode: "write" | "first_write" | "tighten" | "rewrite" =
    !activeThesis && latestInvalidatedThesis
      ? "rewrite"
      : !activeThesis && fromBlindSpot
        ? "first_write"
      : activeThesis && thesisInsights.qualityLabel === "Weak signals"
        ? "tighten"
        : "write";

  const handleNextStepAction = () => {
    if (!nextStepNotice?.action) return;
    const action = nextStepNotice.action;
    setNextStepNotice(null);
    if (action === "edit") {
      setEditing(true);
      setActiveTab("thesis");
      return;
    }
    if (action === "generate_signals") {
      setActiveTab("monitoring");
      void handleGenerateDecomposition();
      return;
    }
    setActiveTab("monitoring");
  };

  // ── Render ───────────────────────────────────────────────────────────────

  return (
    <div className="min-h-[calc(100vh-53px)]">

      {/* ── Sticky header ────────────────────────────────────────────────── */}
      <div className="sticky top-[52px] z-20 bg-background border-b border-border/60">
        <div className="max-w-5xl mx-auto px-6 lg:px-10">

          {/* Nav row */}
          <div className="flex items-center justify-between pt-4 pb-2">
            <Link
              href="/dashboard"
              className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground hover:text-primary transition-colors"
            >
              ← Portfolio
            </Link>
            <div className="flex items-center gap-3">
              {deleteConfirming ? (
                <div className="flex items-center gap-2">
                  <span className="font-mono text-[10px] text-muted-foreground">Remove all data?</span>
                  <button
                    onClick={handleDelete}
                    disabled={deleteLoading}
                    className="font-mono text-[10px] uppercase tracking-[0.15em] text-red-600 hover:text-red-700 transition-colors disabled:opacity-40"
                  >
                    {deleteLoading ? "Removing…" : "Confirm"}
                  </button>
                  <button
                    onClick={() => setDeleteConfirming(false)}
                    className="font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground hover:text-foreground transition-colors"
                  >
                    Cancel
                  </button>
                </div>
              ) : (
                <button
                  onClick={() => setDeleteConfirming(true)}
                  className="font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground/50 hover:text-muted-foreground transition-colors"
                >
                  Remove position
                </button>
              )}
              <CheckNowButton
                holdingId={holding.id}
                ticker={holding.ticker}
                currency={holding.currency}
                investorProfile={onboardingState?.investor_profile ?? null}
                onComplete={handleCheckNowComplete}
              />
            </div>
          </div>

          {/* Identity + value row */}
          <div className="flex items-end justify-between gap-6 pb-3">
            <div>
              <h1 className="font-display italic text-[3.5rem] leading-none text-primary tracking-tight">
                {cleanTicker(holding.ticker)}
              </h1>
              {holding.name && holding.name !== holding.ticker && (
                <p className="font-sans text-[13px] text-muted-foreground mt-1 leading-none">
                  {holding.name}
                </p>
              )}
            </div>
            <div className="text-right shrink-0 pb-0.5">
              <p className="font-mono text-[1.6rem] tabular-nums text-foreground leading-tight">
                {formatCurrency(value)}
              </p>
              <p className={`font-mono text-[13px] tabular-nums mt-0.5 ${pnl >= 0 ? "text-emerald-700" : "text-red-600"}`}>
                {pnl >= 0 ? "+" : ""}{formatCurrency(pnl)}
                <span className="opacity-60 ml-1.5">({pnl >= 0 ? "+" : ""}{pnlPct}%)</span>
              </p>
            </div>
          </div>

          {/* Status ribbon */}
          <div className="flex items-center gap-4 pb-3">
            {/* Pulse dot + label */}
            <div className="flex items-center gap-2">
              <span className={`h-1.5 w-1.5 rounded-full ${STATUS_DOT[activeThesis?.status ?? "no_thesis"] ?? "bg-border"}`} />
              <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                {thesisInsights.qualityLabel}
              </span>
            </div>
            {activeThesis?.health_label && (
              <>
                <span className="text-border text-[10px]">·</span>
                <span className={`font-mono text-[10px] uppercase tracking-[0.12em] px-1.5 py-0.5 ${HEALTH_CHIP[activeThesis.health_label] ?? ""}`}>
                  {activeThesis.health_score != null ? `${activeThesis.health_score} · ` : ""}{activeThesis.health_label}
                </span>
              </>
            )}
            {activeThesis && (
              <>
              <span className="text-border text-[10px]">·</span>
              <span className="font-mono text-[10px] text-muted-foreground/60">
                reason {ageInDays(activeThesis.updated_at)}d old
              </span>
              {stalePressure && (
                <>
                  <span className="text-border text-[10px]">·</span>
                  <span className="font-mono text-[10px] text-amber-700/80">
                    cadence {stalePressure.cadenceDays}d
                  </span>
                </>
              )}
            </>
          )}
            {/* Progress indicators */}
            <div className="flex items-center gap-3 ml-auto">
              {steps.map((step, i) => (
                <div key={step.label} className="flex items-center gap-2">
                  {i > 0 && <span className="text-border text-[10px]">·</span>}
                  <span className={`font-mono text-[10px] uppercase tracking-[0.12em] ${
                    step.done ? "text-emerald-600" : step.partial ? "text-amber-600" : "text-muted-foreground/40"
                  }`}>
                    {step.done ? "●" : step.partial ? "◐" : "○"} {step.label}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Tab strip */}
          <div className="flex gap-1 -mx-1">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className="relative pb-3 px-3 font-mono text-[10px] uppercase tracking-[0.2em] transition-colors flex items-center gap-2"
                style={{ color: activeTab === tab.id ? "var(--primary)" : "var(--muted-foreground)" }}
              >
                {tab.label}
                {tab.badge !== undefined && (
                  <span className={`inline-flex items-center justify-center h-4 min-w-4 px-1 rounded-sm font-mono text-[10px] tabular-nums ${
                    tab.id === "monitoring" && unreviewedEvents > 0
                      ? "bg-primary/10 text-primary"
                      : "text-muted-foreground/60"
                  }`}>
                    {tab.badge}
                  </span>
                )}
                {activeTab === tab.id && (
                  <motion.div
                    layoutId="tab-indicator"
                    className="absolute bottom-0 left-0 right-0 h-px bg-primary"
                    transition={{ type: "spring", stiffness: 400, damping: 35 }}
                  />
                )}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* ── Contextual banners ───────────────────────────────────────────── */}
      <div className="max-w-5xl mx-auto px-6 lg:px-10">

        {fromOnboarding && activeThesis && (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-5 border border-emerald-500/25 bg-emerald-500/8 px-5 py-4 space-y-4"
          >
            <div className="space-y-2">
              <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-emerald-700">
                ● First holding activated
              </p>
              <p className="font-sans text-sm text-foreground/80 leading-relaxed">
                {onboardingMonitoringMessage}
              </p>
            </div>

            {monitoringPreviewItems.length > 0 && (
              <div className="space-y-2">
                <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-foreground/60">
                  What we&apos;re starting to watch
                </p>
                <div className="grid gap-2">
                  {monitoringPreviewItems.map((item) => (
                    <div key={item.key} className="border border-emerald-600/10 bg-background/70 px-3 py-2.5">
                      <p className="font-sans text-sm text-foreground">{item.label}</p>
                      <p className="font-sans text-xs text-muted-foreground mt-1 leading-relaxed">{item.detail}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <p className="font-sans text-xs text-foreground/65 leading-relaxed">
              {onboardingMonitoringNextStep}
            </p>
          </motion.div>
        )}

        {fromBlindSpot && !activeThesis && !editing && (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-5 border border-amber-500/25 bg-amber-500/8 px-5 py-4 space-y-3"
          >
            <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-amber-700">
              {blindSpotArrivalCopy.eyebrow}
            </p>
            <div className="space-y-1.5">
              <p className="font-display italic text-[1.35rem] leading-tight text-foreground">
                {blindSpotArrivalCopy.title}
              </p>
              <p className="font-sans text-sm text-foreground/80 leading-relaxed">
                {blindSpotArrivalCopy.body}
              </p>
            </div>
            <button
              onClick={() => setEditing(true)}
              className="font-mono text-[10px] uppercase tracking-[0.15em] text-primary hover:text-primary/80 transition-colors"
            >
              {blindSpotArrivalCopy.cta}
            </button>
          </motion.div>
        )}

        {nextStepNotice && (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-5 border border-primary/20 bg-primary/5 px-5 py-4 space-y-3"
          >
            <div className="flex items-start justify-between gap-4">
              <div className="space-y-2">
                <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-primary">
                  {nextStepNotice.eyebrow}
                </p>
                <div className="space-y-1">
                  <p className="font-display italic text-[1.35rem] leading-tight text-foreground">
                    {nextStepNotice.title}
                  </p>
                  <p className="font-sans text-sm text-foreground/80 leading-relaxed">
                    {nextStepNotice.body}
                  </p>
                </div>
              </div>
              <button
                onClick={() => setNextStepNotice(null)}
                className="font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground hover:text-foreground transition-colors"
              >
                Dismiss
              </button>
            </div>
            {nextStepNotice.ctaLabel && nextStepNotice.action && (
              <button
                onClick={handleNextStepAction}
                className="font-mono text-[10px] uppercase tracking-[0.15em] text-primary hover:text-primary/80 transition-colors"
              >
                {nextStepNotice.ctaLabel}
              </button>
            )}
          </motion.div>
        )}

        {decisionPrompt && !(fromBlindSpot && !activeThesis && !editing) && (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            className={`mt-5 border px-5 py-4 space-y-3 ${decisionPrompt.tone}`}
          >
            <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-foreground/70">
              {decisionPrompt.eyebrow}
            </p>
            <div className="space-y-1.5">
              <p className="font-display italic text-[1.35rem] leading-tight text-foreground">
                {decisionPrompt.title}
              </p>
              <p className="font-sans text-sm text-foreground/80 leading-relaxed">
                {decisionPrompt.body}
              </p>
            </div>
            <button
              onClick={() => {
                if (decisionPrompt.action === "edit") {
                  setEditing(true);
                  setActiveTab("thesis");
                  return;
                }
                setActiveTab("monitoring");
              }}
              className="font-mono text-[10px] uppercase tracking-[0.15em] text-primary hover:text-primary/80 transition-colors"
            >
              {decisionPrompt.ctaLabel}
            </button>
          </motion.div>
        )}

        {activeThesis && upcomingEarnings && upcomingEarnings.days_until <= 14 && (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-5 border border-sky-500/25 bg-sky-500/8 px-5 py-4 space-y-3"
          >
            <div className="flex items-center gap-3">
              <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-sky-700">
                ● Earnings in {upcomingEarnings.days_until === 0 ? "today" : upcomingEarnings.days_until === 1 ? "tomorrow" : `${upcomingEarnings.days_until} days`}
              </span>
              <span className="font-mono text-[10px] text-muted-foreground">{formatDate(upcomingEarnings.report_date)}</span>
            </div>
            {earningsWatchList.length > 0 ? (
              <div className="flex flex-wrap gap-2">
                {earningsWatchList.map((item) => (
                  <span key={item} className="font-sans text-xs text-foreground/70 border border-border/60 bg-card px-3 py-1">
                    {item}
                  </span>
                ))}
              </div>
            ) : (
              <p className="font-sans text-xs text-muted-foreground">
                {copy.earningsEmpty}
              </p>
            )}
          </motion.div>
        )}

        {showEarningsBanner && (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-5 border border-amber-500/25 bg-amber-500/8 px-5 py-4 space-y-4"
          >
            <div>
              <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-amber-700">
                ● Earnings just landed
              </span>
              <p className="font-sans text-sm text-foreground/80 leading-relaxed mt-1">
                {recentEarningsEvent
                  ? (recentEarningsEvent.ai_analysis || recentEarningsEvent.evidence_summary || recentEarningsEvent.summary)
                  : healthCheck?.recent_earnings_surprise_pct !== null && healthCheck?.recent_earnings_surprise_pct !== undefined
                    ? `${cleanTicker(ticker)} reported earnings with a ${healthCheck.recent_earnings_surprise_pct > 0 ? "+" : ""}${healthCheck.recent_earnings_surprise_pct.toFixed(1)}% surprise. ${copy.postEarningsReview}`
                    : `${cleanTicker(ticker)} recently reported earnings. ${copy.postEarningsReview}`
                }
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              {recentEarningsEvent && [
                { action: "reaffirmed" as const, label: "Reason holds", cls: "border-emerald-500/30 text-emerald-700 hover:bg-emerald-500/8" },
                { action: "lowered_confidence" as const, label: "Lower confidence", cls: "border-amber-500/30 text-amber-700 hover:bg-amber-500/8" },
                { action: "invalidated" as const, label: "Reason broken", cls: "border-red-500/30 text-red-600 hover:bg-red-500/8" },
              ].map(({ action, label, cls }) => (
                <button
                  key={action}
                  disabled={reviewingEventId === recentEarningsEvent.id}
                  onClick={() => void handleReviewEvent(recentEarningsEvent, action)}
                  className={`font-mono text-[10px] uppercase tracking-[0.15em] border px-4 py-2 transition-colors disabled:opacity-40 ${cls}`}
                >
                  {label}
                </button>
              ))}
              <button
                onClick={() => setShowEarningsReview(true)}
                className="font-mono text-[10px] uppercase tracking-[0.15em] border border-amber-600/40 text-amber-700 bg-amber-50 hover:bg-amber-100 px-4 py-2 transition-colors"
              >
                {onboardingState?.investor_profile === "thesis_driven"
                  ? "Review thesis claim by claim →"
                  : onboardingState?.investor_profile === "hearsay_driven"
                    ? "Review the reason claim by claim →"
                    : "Review reason claim by claim →"}
              </button>
            </div>
          </motion.div>
        )}
      </div>

      {showEarningsReview && activeThesis && (
        <EarningsReviewModal
          thesisId={activeThesis.id}
          ticker={cleanTicker(ticker)}
          investorProfile={onboardingState?.investor_profile ?? null}
          onClose={() => setShowEarningsReview(false)}
        />
      )}

      {/* ── Tab content ─────────────────────────────────────────────────── */}
      <div className="max-w-5xl mx-auto px-6 lg:px-10">
        <AnimatePresence mode="wait">
          <motion.div
            key={activeTab}
            initial={{ opacity: 0, y: 5 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -5 }}
            transition={{ duration: 0.16, ease: "easeOut" }}
            className="py-8 space-y-8"
          >

            {/* ─── THESIS TAB ──────────────────────────────────────────── */}
            {activeTab === "thesis" && (
              <>
                {/* Action prompt */}
                {(thesisInsights.canReaffirm || !activeThesis) && !editing && (
                  <div className="border-l-2 border-primary/30 pl-4 py-1 flex items-start justify-between gap-4">
                    <p className="font-sans text-sm text-foreground/80 leading-relaxed max-w-xl">
                      {thesisInsights.nextStep}
                    </p>
                    <div className="flex gap-2 shrink-0">
                      {!activeThesis && (
                        <button
                          onClick={() => setEditing(true)}
                          className="font-mono text-[10px] uppercase tracking-[0.15em] bg-primary text-primary-foreground px-4 py-2 hover:bg-primary/90 transition-colors"
                        >
                          Write your reason
                        </button>
                      )}
                      {activeThesis && thesisInsights.canReaffirm && (
                        <button
                          onClick={handleReaffirm}
                          disabled={reaffirming}
                          className="font-mono text-[10px] uppercase tracking-[0.15em] border border-primary/40 text-primary px-4 py-2 hover:border-primary transition-colors disabled:opacity-40"
                        >
                          {reaffirming ? "Reaffirming…" : "Still holding"}
                        </button>
                      )}
                      {activeThesis && (
                        <button
                          onClick={() => setShowEarningsReview(true)}
                          className="font-mono text-[10px] uppercase tracking-[0.15em] border border-border text-muted-foreground hover:text-foreground px-4 py-2 transition-colors"
                        >
                          {copy.afterEarningsCta}
                        </button>
                      )}
                    </div>
                  </div>
                )}

                {thesisHandoffPrompt && !editing && (
                  <div className="border-l-2 border-sky-500/30 pl-4 py-1 flex items-start justify-between gap-4">
                    <div className="space-y-1">
                      <p className="font-sans text-sm text-foreground/90 leading-relaxed max-w-xl">
                        {thesisHandoffPrompt.title}
                      </p>
                      <p className="font-sans text-sm text-muted-foreground leading-relaxed max-w-xl">
                        {thesisHandoffPrompt.body}
                      </p>
                    </div>
                    <button
                      onClick={() => {
                        if (thesisHandoffPrompt.action === "generate") {
                          setActiveTab("monitoring");
                          void handleGenerateDecomposition();
                          return;
                        }
                        setActiveTab("monitoring");
                      }}
                      className="font-mono text-[10px] uppercase tracking-[0.15em] text-primary px-4 py-2 hover:text-primary/80 transition-colors shrink-0"
                    >
                      {thesisHandoffPrompt.ctaLabel}
                    </button>
                  </div>
                )}

                {/* Editor */}
                {editing && (
                  <ThesisEditor
                    thesis={editorSeedThesis}
                    investorProfile={onboardingState?.investor_profile ?? null}
                    mode={editorMode}
                    onSave={handleSave}
                    onAssist={handleAssist}
                    onCancel={() => setEditing(false)}
                  />
                )}

                {/* Thesis card */}
                {activeThesis && !editing && (
                  <ThesisCard
                    thesis={activeThesis}
                    decomposition={decompositionEnvelope?.decomposition ?? null}
                    investorProfile={onboardingState?.investor_profile ?? null}
                    onEdit={() => setEditing(true)}
                    onInvalidate={() => setInvalidateOpen(true)}
                  />
                )}

                {/* No thesis empty state */}
                {!activeThesis && !editing && (
                  <div className="py-16 text-center space-y-4">
                    <p className="font-display italic text-2xl text-foreground/50">
                      {latestInvalidatedThesis
                        ? (onboardingState?.investor_profile === "thesis_driven"
                            ? "Your last thesis broke."
                            : onboardingState?.investor_profile === "hearsay_driven"
                              ? "Your last reason broke."
                              : "Your last reason broke.")
                        : copy.noReasonTitle}
                    </p>
                    <p className="font-sans text-sm text-muted-foreground max-w-sm mx-auto leading-relaxed">
                      {latestInvalidatedThesis
                        ? (onboardingState?.investor_profile === "thesis_driven"
                            ? "Start from the last thesis, cut what failed, and write the version you'd still own today."
                            : onboardingState?.investor_profile === "hearsay_driven"
                              ? "Start from the last written reason, remove the part of the story that broke, and write the version you would still believe today."
                              : "Start from the last written reason, remove what failed, and write the version you would still believe today.")
                        : copy.noReasonBody}
                    </p>
                    <button
                      onClick={() => setEditing(true)}
                      className="font-mono text-[10px] uppercase tracking-[0.2em] border border-primary/40 text-primary px-5 py-2.5 hover:border-primary transition-colors"
                    >
                      {latestInvalidatedThesis
                        ? (onboardingState?.investor_profile === "thesis_driven" ? "Rewrite the thesis" : "Rewrite the reason")
                        : copy.noReasonCta}
                    </button>
                  </div>
                )}

                {/* Analysis (health check + counter thesis) */}
                {activeThesis && (healthCheck || healthCheckLoading || showCounterThesis) && (
                  <div className="space-y-4 border-t border-border/40 pt-6">
                    <button
                      onClick={() => setShowAnalysis((s) => !s)}
                      className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground hover:text-foreground transition-colors"
                    >
                      {showAnalysis ? "▲" : "▼"} Analysis
                    </button>
                    {showAnalysis && (
                      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-4">
                        {(healthCheck || healthCheckLoading) && (
                          <ThesisHealthCheck
                            result={healthCheck}
                            loading={healthCheckLoading}
                            investorProfile={onboardingState?.investor_profile ?? null}
                          />
                        )}
                        {showCounterThesis && <CounterThesisCard thesisId={activeThesis.id} />}
                      </motion.div>
                    )}
                  </div>
                )}

                {/* Position metrics */}
                <div className="border-t border-border/40 pt-5">
                  <button
                    onClick={() => setShowPositionDetails((s) => !s)}
                    className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground hover:text-foreground transition-colors"
                  >
                    {showPositionDetails ? "▲" : "▼"} Position details
                  </button>
                  {showPositionDetails && (
                    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-4">
                      {[
                        { label: "Shares", value: String(holding.quantity) },
                        { label: "Avg cost", value: formatCurrency(holding.average_cost_basis) },
                        { label: "Current value", value: formatCurrency(value) },
                        { label: "P&L", value: `${pnl >= 0 ? "+" : ""}${formatCurrency(pnl)}`, colored: true },
                      ].map(({ label, value: v, colored }) => (
                        <div key={label} className="border border-border/60 bg-card px-4 py-3">
                          <p className="font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground">{label}</p>
                          <p className={`font-mono text-lg tabular-nums mt-1.5 ${colored ? (pnl >= 0 ? "text-emerald-700" : "text-red-600") : "text-foreground"}`}>
                            {v}
                          </p>
                        </div>
                      ))}
                    </motion.div>
                  )}
                </div>
              </>
            )}

            {/* ─── MONITORING TAB ──────────────────────────────────────── */}
            {activeTab === "monitoring" && (
              <div className="space-y-10">

                {/* No thesis guard */}
                {!activeThesis ? (
                  <div className="py-16 text-center space-y-4">
                    <p className="font-display italic text-2xl text-foreground/50">
                      {copy.monitoringEmptyTitle}
                    </p>
                    <p className="font-sans text-sm text-muted-foreground max-w-xs mx-auto leading-relaxed">
                      {copy.monitoringEmptyBody}
                    </p>
                    <button
                      onClick={() => { setEditing(true); setActiveTab("thesis"); }}
                      className="font-mono text-[10px] uppercase tracking-[0.2em] border border-primary/40 text-primary px-5 py-2.5 hover:border-primary transition-colors"
                    >
                      {copy.monitoringEmptyCta}
                    </button>
                  </div>
                ) : (
                  <>
                    {/* ── DECISION SECTION ────────────────────────────── */}
                    <section>
                      {unreviewedEvents > 0 ? (
                        <div className="space-y-5">
                          {isFirstLiveEvidenceMoment && firstPendingEvent && (
                            <div className="border border-primary/20 bg-primary/5 px-5 py-4 space-y-3">
                              <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-primary">
                                ● First live evidence
                              </p>
                              {firstPendingAssumptionLabel && (
                                <div className="space-y-1">
                                  <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-foreground/55">
                                    Assumption under test
                                  </p>
                                  <p className="font-sans text-sm text-foreground">
                                    {firstPendingAssumptionLabel}
                                  </p>
                                </div>
                              )}
                              <div className="space-y-1.5">
                                <p className="font-display italic text-[1.35rem] leading-tight text-foreground">
                                  {onboardingState?.investor_profile === "hearsay_driven"
                                    ? "This is the first real test of the reason you wrote down."
                                    : "This is the first real test of the thesis you wrote down."}
                                </p>
                                <p className="font-sans text-sm text-foreground/80 leading-relaxed">
                                  {firstPendingEvent.ai_analysis ||
                                    firstPendingEvent.evidence_summary ||
                                    firstPendingEvent.summary ||
                                    (onboardingState?.investor_profile === "hearsay_driven"
                                      ? "First alert that may matter for the story. Decide what it means before you move on."
                                      : "First alert that may matter for the thesis. Decide what it means before you move on.")}
                                </p>
                              </div>
                            </div>
                          )}

                          {/* Decisions pending header */}
                          <div className="flex items-baseline justify-between gap-4">
                            <div>
                              <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground mb-1">
                                Decisions pending
                              </p>
                              <p className="font-display italic text-[1.6rem] leading-tight text-foreground">
                                {onboardingState?.investor_profile === "thesis_driven"
                                  ? (unreviewedEvents === 1
                                      ? "One thesis signal needs your verdict."
                                      : `${unreviewedEvents} thesis signals need your verdict.`)
                                  : onboardingState?.investor_profile === "hearsay_driven"
                                    ? (unreviewedEvents === 1
                                        ? "One change to your reason needs a decision."
                                        : `${unreviewedEvents} changes to your reason need decisions.`)
                                    : (unreviewedEvents === 1
                                        ? "One signal needs your verdict."
                                        : `${unreviewedEvents} signals need your verdict.`)}
                              </p>
                            </div>
                            <span className="font-mono text-[10px] text-muted-foreground/50 shrink-0 self-end pb-0.5">
                              drag to decide
                            </span>
                          </div>

                          {/* Card stack */}
                          <EventReviewStack
                            events={events.filter((e) => !e.review_action)}
                            onReview={handleReviewEvent}
                            reviewingEventId={reviewingEventId}
                            investorProfile={onboardingState?.investor_profile ?? null}
                          />
                        </div>
                      ) : (
                        /* Position clear */
                        <div className="space-y-4 py-6 border-l-[3px] border-emerald-500/40 pl-6">
                          <div className="space-y-1">
                            <p className="font-display italic text-[1.6rem] leading-tight text-foreground">
                              {monitoringCalmState.title}
                            </p>
                            <p className="font-sans text-sm text-muted-foreground leading-relaxed">
                              {monitoringCalmState.body}
                            </p>
                            <p className="font-sans text-sm text-foreground/70 leading-relaxed">
                              {monitoringCalmState.nextCheck}
                            </p>
                          </div>

                          {monitoringCalmState.previewItems.length > 0 && (
                            <div className="grid gap-2 sm:grid-cols-2 max-w-3xl">
                              {monitoringCalmState.previewItems.map((item) => (
                                <div key={item.key} className="border border-emerald-600/10 bg-card px-3 py-2.5">
                                  <p className="font-sans text-sm text-foreground">{item.label}</p>
                                  <p className="font-sans text-xs text-muted-foreground mt-1 leading-relaxed">{item.detail}</p>
                                </div>
                              ))}
                            </div>
                          )}

                          {monitoringCalmState.previewItems.length === 0 && monitoringCalmState.fallbackHints.length > 0 && (
                            <div className="flex flex-wrap gap-2">
                              {monitoringCalmState.fallbackHints.map((hint) => (
                                <span key={hint} className="font-sans text-xs text-foreground/70 border border-border/60 bg-card px-3 py-1">
                                  {hint}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                      )}
                    </section>

                    {/* ── SIGNALS SECTION ─────────────────────────────── */}
                    <section className="border-t border-border/40 pt-8 space-y-4">
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground mb-0.5">
                            Watching for
                          </p>
                          <p className="font-sans text-xs text-muted-foreground/70">
                            {onboardingState?.investor_profile === "thesis_driven"
                              ? "Signals derived from your thesis"
                              : onboardingState?.investor_profile === "hearsay_driven"
                                ? "Signals derived from the reason you wrote down"
                                : "Signals derived from your thesis"}
                          </p>
                        </div>
                        {!hasSignals && !decompositionLoading && (
                          <button
                            onClick={handleGenerateDecomposition}
                            className="font-mono text-[10px] uppercase tracking-[0.15em] border border-primary/40 text-primary px-4 py-2 hover:border-primary transition-colors"
                          >
                            Generate signals
                          </button>
                        )}
                      </div>

                      <ThesisDecompositionReview
                        key={`${decompositionEnvelope?.decomposition?.id ?? "empty"}:${decompositionEnvelope?.status ?? "none"}`}
                        envelope={decompositionEnvelope}
                        loading={decompositionLoading}
                        saving={decompositionSaving}
                        onGenerate={handleGenerateDecomposition}
                        onConfirm={handleConfirmDecomposition}
                      />
                    </section>

                    {/* ── EVIDENCE SECTION ────────────────────────────── */}
                    {events.some((e) => e.review_action) && (
                      <section className="border-t border-border/40 pt-8 space-y-4">
                        <div>
                          <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground mb-0.5">
                            Evidence on file
                          </p>
                          <p className="font-sans text-xs text-muted-foreground/70">
                            Reviewed events and your verdicts
                          </p>
                        </div>
                        <EventTimeline
                          events={events.filter((e) => e.review_action)}
                          reviewingEventId={reviewingEventId}
                          investorProfile={onboardingState?.investor_profile ?? null}
                        />
                      </section>
                    )}

                    {/* No events at all */}
                    {events.length === 0 && !decompositionLoading && (
                      <div className="border border-border/50 bg-card/60 px-4 py-3 space-y-2">
                        <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                          Quiet state
                        </p>
                        <p className="font-sans text-sm text-muted-foreground/80 leading-relaxed">
                          {onboardingState?.investor_profile === "thesis_driven"
                            ? "Monitoring is active. No thesis-level change is worth a decision yet."
                            : onboardingState?.investor_profile === "hearsay_driven"
                              ? "Monitoring is active. Nothing has tested the reason strongly enough to force a decision yet."
                              : "Monitoring is active. Nothing meaningful has changed yet."}
                        </p>
                        <p className="font-sans text-xs text-foreground/65">
                          {monitoringCalmState.nextCheck}
                        </p>
                      </div>
                    )}
                  </>
                )}
              </div>
            )}

            {/* ─── HISTORY TAB ─────────────────────────────────────────── */}
            {activeTab === "history" && (
              <>
                <ConvictionLog
                  data={convictionLog}
                  loading={convictionLogLoading}
                  saving={noteSaving}
                  onAddNote={activeThesis ? handleAddManualNote : undefined}
                  investorProfile={onboardingState?.investor_profile ?? null}
                />

                {invalidatedTheses.length > 0 && (
                  <div className="border-t border-border/40 pt-6 space-y-3">
                    <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                      {onboardingState?.investor_profile === "thesis_driven" ? "Previous theses" : "Previous reasons"}
                    </p>
                    {invalidatedTheses.map((t) => (
                      <div key={t.id} className="border-l-2 border-border/60 pl-4 py-3 space-y-1.5">
                        <p className="font-sans text-sm text-foreground/70 leading-relaxed italic">
                          &ldquo;{t.why_own_it}&rdquo;
                        </p>
                        {t.invalidation_reason && (
                          <p className="font-sans text-xs text-muted-foreground">
                            Closed: {t.invalidation_reason}
                          </p>
                        )}
                        <p className="font-mono text-[10px] text-muted-foreground/60">
                          {formatDate(t.updated_at)}
                        </p>
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}

          </motion.div>
        </AnimatePresence>
      </div>

      {/* ── Invalidate dialog ────────────────────────────────────────────── */}
      <Dialog open={invalidateOpen} onOpenChange={setInvalidateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="font-display italic">Mark as broken</DialogTitle>
          </DialogHeader>
          <Textarea
            placeholder={
              onboardingState?.investor_profile === "thesis_driven"
                ? "Why is this thesis no longer valid?"
                : onboardingState?.investor_profile === "hearsay_driven"
                  ? "Why does the original story no longer hold?"
                  : "Why is this reason no longer valid?"
            }
            value={invalidateReason}
            onChange={(e) => setInvalidateReason(e.target.value)}
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setInvalidateOpen(false)}>Cancel</Button>
            <Button variant="destructive" onClick={handleInvalidate}>Invalidate</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
