import type {
  CheckNowResponse,
  MonitoringEvent,
  Thesis,
  ThesisDecompositionEnvelope,
  UpcomingEarnings,
} from "@/types";
import { describeWatchHint as baseDescribeWatchHint } from "@/lib/watch-hints";

// Pure presentational helpers + local types extracted from the position
// page to shrink the god-component. No hooks/state — unit-testable in isolation.

export type TabId = "thesis" | "monitoring";
export type ThesisSubTab = "thesis" | "signals" | "log";
export type NextStepAction = "edit" | "generate_signals" | "confirm_signals" | "monitoring";

export interface NextStepNotice {
  eyebrow: string;
  title: string;
  body: string;
  ctaLabel?: string;
  action?: NextStepAction;
}

export function cleanTicker(ticker: string) {
  return ticker.replace(/_US_EQ$/, "").replace(/_EQ$/, "");
}

export function ageInDays(dateString: string) {
  const now = Date.now();
  const then = new Date(dateString).getTime();
  return Math.max(0, Math.floor((now - then) / (1000 * 60 * 60 * 24)));
}

export function getStalePressure(thesis: Thesis | undefined) {
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

export function getThesisInsights(
  thesis: Thesis | undefined,
  events: MonitoringEvent[],
  investorProfile: "thesis_driven" | "hearsay_driven" | null,
) {
  if (!thesis) {
    return {
      nextStep:
        investorProfile === "hearsay_driven"
          ? "Turn the original story into a written reason this app can track."
          : "Write the thesis so monitoring has something concrete to track.",
      qualityLabel: "No reason yet",
      qualityTone: "bg-red-500/15 text-red-600",
      statusDot: "text-red-500",
      watchStatus:
        investorProfile === "hearsay_driven"
          ? "No written reason yet, so this position is still noise-sensitive."
          : "No written thesis yet, so this position is not being monitored.",
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
      nextStep: latestEvent?.ai_analysis || "Review what changed and decide whether the case still holds.",
      qualityLabel: "Needs review",
      qualityTone: "bg-orange-500/15 text-orange-600",
      statusDot: "text-orange-500",
      watchStatus: "Monitoring found something that needs a call.",
      canReaffirm: true,
    };
  }

  if (stalePressure) {
    return {
      nextStep:
        stalePressure.level === "review"
          ? "This case is far past due. Refresh it or stop treating it as live conviction."
          : "This case is overdue. Re-read it and tighten it.",
      qualityLabel: stalePressure.level === "review" ? "Needs refresh" : "Stale",
      qualityTone: "bg-amber-500/15 text-amber-700",
      statusDot: "text-amber-500",
      watchStatus:
        stalePressure.level === "review"
          ? `${stalePressure.daysOld} days old and far past its ${stalePressure.cadenceDays}-day cadence.`
          : `${stalePressure.daysOld} days old and overdue for its ${stalePressure.cadenceDays}-day cadence.`,
      canReaffirm: true,
    };
  }

  if (monitorability === "low") {
    return {
      nextStep:
        ambiguity ||
        (investorProfile === "hearsay_driven"
          ? "Tighten this into a clearer business reason and a sharper break condition."
          : "Tighten the thesis so it can be monitored more precisely."),
      qualityLabel: "Weak signals",
      qualityTone: "bg-muted text-muted-foreground",
      statusDot: "text-muted-foreground",
      watchStatus:
        investorProfile === "hearsay_driven"
          ? "The current reason still reads more like a story than a case."
          : "The current thesis is too vague for reliable monitoring.",
      canReaffirm: false,
    };
  }

  return {
    nextStep: latestEvent ? latestEvent.ai_analysis || "Monitoring is active. Review the latest event if it still matters." : "The case looks clean. No action needed.",
    qualityLabel: "Intact",
    qualityTone: "bg-emerald-500/15 text-emerald-700",
    statusDot: "text-emerald-500",
    watchStatus: latestEvent ? "Monitoring has context for new evidence." : "Monitoring is active. Nothing meaningful flagged yet.",
    canReaffirm: false,
  };
}

export function positionCopy(investorProfile: "thesis_driven" | "hearsay_driven" | null) {
  if (investorProfile === "thesis_driven") {
    return {
      earningsEmpty: "Tighten the thesis so the morning-after review knows what matters.",
      postEarningsReview: "Check which assumption still holds after the quarter.",
      noReasonTitle: "No thesis written yet.",
      noReasonBody: "Write the core case, what must stay true, and what would break it.",
      noReasonCta: "Write your thesis",
      monitoringEmptyTitle: "Nothing to monitor yet.",
      monitoringEmptyBody: "Write the thesis first. Monitoring needs a specific assumption set to test.",
      monitoringEmptyCta: "Go to your thesis →",
      afterEarningsCta: "After earnings?",
    };
  }

  if (investorProfile === "hearsay_driven") {
    return {
      earningsEmpty: "Turn the original story into a reason first so the morning-after review knows what matters.",
      postEarningsReview: "Check whether the original story still holds after the quarter.",
      noReasonTitle: "No reason written yet.",
      noReasonBody: "Start with the story behind the position, then make it concrete: what must stay true and what would break it.",
      noReasonCta: "Write your reason",
      monitoringEmptyTitle: "Nothing to check yet.",
      monitoringEmptyBody: "Write the real reason first. Without that, we cannot tell what matters from noise.",
      monitoringEmptyCta: "Go to your reason →",
      afterEarningsCta: "After earnings?",
    };
  }

  return {
    earningsEmpty: "Tighten the reason so the morning-after review knows what matters.",
    postEarningsReview: "Review whether your reason still holds.",
    noReasonTitle: "No reason written yet.",
    noReasonBody: "Start with why this position exists, what must stay true, and what would change your mind.",
    noReasonCta: "Write your reason",
    monitoringEmptyTitle: "Nothing to watch yet.",
    monitoringEmptyBody: "Write the reason first. Monitoring needs something written to test.",
    monitoringEmptyCta: "Go to your reason →",
    afterEarningsCta: "After earnings?",
  };
}

export function getDecisionPrompt(
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
          ? "Turn the original story into a real reason first, or it stays too easy to size up a hope trade."
          : "Write the thesis, what must stay true, and what would break it before treating this like conviction.",
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
      eyebrow: investorProfile === "hearsay_driven" ? "Stale reason" : "Stale thesis",
      title:
        investorProfile === "hearsay_driven"
          ? "Still buy this on the same reason?"
          : "Still buy this on the same thesis?",
      body:
        investorProfile === "hearsay_driven"
          ? `${stalePressure.daysOld}d old. Your cadence is ${stalePressure.cadenceDays}d. Refresh it before you add or keep sizing on it.`
          : `${stalePressure.daysOld}d old. Your cadence is ${stalePressure.cadenceDays}d. Refresh it before you add or keep sizing on it.`,
      ctaLabel: "Refresh it →",
      action: "edit" as const,
      tone: "border-amber-500/25 bg-amber-500/8",
    };
  }

  return null;
}

export function getThesisHandoffPrompt(args: {
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
          ? "Build the first watchlist so real evidence counts and noise does not."
          : "Build the first watchlist so real evidence counts and noise does not.",
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
          ? "We already suggested a monitoring setup. Review it once so future alerts reflect the reason you meant."
          : "We already suggested a monitoring setup. Review it once so future alerts reflect the thesis you meant.",
      ctaLabel: "Review signals →",
      action: "monitoring" as const,
    };
  }

  return null;
}

export function getBlindSpotArrivalCopy(investorProfile: "thesis_driven" | "hearsay_driven" | null) {
  if (investorProfile == "hearsay_driven") {
    return {
      eyebrow: "Blind spot",
      title: "This position still has no written reason.",
      body: "Until you turn the original story into a real reason, we cannot tell signal from panic here.",
      cta: "Write the real reason now →",
    };
  }

  if (investorProfile === "thesis_driven") {
    return {
      eyebrow: "Blind spot",
      title: "This position still has no written thesis.",
      body: "Until you've written the thesis, we cannot tell whether new evidence is noise or a real assumption break.",
      cta: "Write the thesis now →",
    };
  }

  return {
    eyebrow: "Blind spot",
    title: "This position still has no written reason.",
    body: "Until you've written the reason, we cannot tell whether new evidence should change your mind.",
    cta: "Write the reason now →",
  };
}

export function getMonitoringCalmState(args: {
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
      ? `Monitoring is live and now watching ${activeSignalCount > 0 ? `${activeSignalCount} watchpoint${activeSignalCount === 1 ? "" : "s"}` : "your first watchlist"} against the written reason.`
      : `Monitoring is live and now watching ${activeSignalCount > 0 ? `${activeSignalCount} watchpoint${activeSignalCount === 1 ? "" : "s"}` : "your first watchlist"} against the written thesis.`;

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
    previewItems: monitoringPreviewItems,
    fallbackHints: watchHints.slice(0, 2),
  };
}

export function describeWatchHint(hint: Record<string, unknown>) {
  return baseDescribeWatchHint(hint, { priceStyle: "discipline" });
}

export function getMonitoringPreviewItems(
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
    // Show every active signal — the surrounding copy states the count, so a
    // shorter list reads as a mismatch ("watching 4 signals" but only 2 shown).
    return signalItems;
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

export function buildPostSaveNotice(args: {
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
          ? "The position now has a real written reason. Generate the first watchlist so the next alert is tied to the story you mean."
          : "The position now has a real written thesis. Generate the first watchlist so the next alert is tied to the assumption you mean.",
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
        ? "Your reason is written down. Generate signal candidates now so real evidence stands apart from headline churn."
        : "Your thesis is saved. Generate signal candidates now so monitoring knows which assumptions matter.",
    ctaLabel: "Generate signals now →",
    action: "generate_signals",
  };
}

export function buildPostDecompositionNotice(
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

export function buildPostConfirmationNotice(args: {
  investorProfile: "thesis_driven" | "hearsay_driven" | null;
  activeSignalCount: number;
}): NextStepNotice {
  const { investorProfile, activeSignalCount } = args;
  const signalText =
    activeSignalCount > 0
      ? `${activeSignalCount} watchpoint${activeSignalCount === 1 ? "" : "s"}`
      : "a watchlist";

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

export function buildPostReviewClearNotice(
  investorProfile: "thesis_driven" | "hearsay_driven" | null,
): NextStepNotice {
  return {
    eyebrow: "Decision logged",
      title:
        investorProfile === "hearsay_driven"
        ? "The reason is back to quiet."
        : "The thesis is back to quiet.",
      body:
        investorProfile === "hearsay_driven"
        ? "Nothing else needs a call right now. The next meaningful change will show up here."
        : "Nothing else needs a call right now. The next meaningful change will show up here.",
    ctaLabel: "Stay on monitoring →",
    action: "monitoring",
  };
}

export function buildPostInvalidationNotice(
  investorProfile: "thesis_driven" | "hearsay_driven" | null,
): NextStepNotice {
  return {
    eyebrow: "Reason broken",
      title:
        investorProfile === "hearsay_driven"
        ? "This position now needs a new reason or a sell call."
        : "This position now needs a new thesis or a sell call.",
      body:
        investorProfile === "hearsay_driven"
        ? "You logged that the original story no longer holds. Rewrite the reason if you still want to own it."
        : "You logged that the thesis no longer holds. Rewrite it if you still want to own it.",
    ctaLabel: investorProfile === "thesis_driven" ? "Rewrite the thesis →" : "Rewrite the reason →",
    action: "edit",
  };
}

export function buildCheckNowNotice(args: {
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
        ? "Something new landed that may change the story. Review it while it is still fresh."
        : "Something new landed that may change the thesis. Review it while it is still fresh.",
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
        ? "We checked what is available. Nothing yet forces a call on your reason."
        : "We checked what is available. Nothing yet forces a call on your thesis.",
    ctaLabel: "Stay on monitoring →",
    action: "monitoring",
  };
}

export function isRecentEvent(dateString: string, days: number) {
  const ageMs = Date.now() - new Date(dateString).getTime();
  return ageMs >= 0 && ageMs <= days * 24 * 60 * 60 * 1000;
}

export function getEventAssumptionLabel(
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

export const HEALTH_CHIP: Record<string, string> = {
  Healthy: "text-emerald-700 bg-emerald-500/10",
  "At Risk": "text-amber-700 bg-amber-500/10",
  Broken: "text-red-600 bg-red-500/10",
};

// ── Status dot colour ────────────────────────────────────────────────────────

export const STATUS_DOT: Record<string, string> = {
  intact: "bg-emerald-500",
  needs_review: "bg-orange-500",
  stale: "bg-amber-400",
  no_thesis: "bg-red-500",
  low_signal: "bg-border",
};

// ── Page ─────────────────────────────────────────────────────────────────────
