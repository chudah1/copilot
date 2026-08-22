import type {
  DashboardCommandCenter,
  DashboardCommandCenterHolding,
  Digest,
  QuarterlyReviewCurrent,
} from "@/types";
import type { DashboardCoachPlan } from "@/lib/dashboard-coach";

function cleanTicker(ticker: string) {
  return ticker.replace(/_US_EQ$/i, "").replace(/_EQ$/i, "");
}

export interface DashboardAction {
  key: string;
  kind: "weekly_review" | "decision" | "setup" | "follow_up" | "quarterly";
  eyebrow: string;
  ticker: string | null;
  title: string;
  detail: string;
  ctaLabel: string;
  href: string;
  carriedForward?: boolean;
  sourceDigestId?: string;
  secondaryHref?: string;
  secondaryLabel?: string;
  coachTarget?: DashboardCoachPlan["primaryCta"];
}

interface ActionQueueInput {
  commandCenter: DashboardCommandCenter | null;
  latestDigest: Digest | null;
  weeklyDigestReady: boolean;
  quarterlyReview: QuarterlyReviewCurrent | null;
  investorProfile: DashboardCommandCenter["investor_profile"] | null;
  coachPlan?: DashboardCoachPlan | null;
}

const SECTION_ORDER: DashboardCommandCenter["sections"][number]["kind"][] = [
  "needs_review",
  "decision_debt",
  "unclear_theses",
];

function orderedSections(commandCenter: DashboardCommandCenter) {
  return [...commandCenter.sections]
    .filter((section) => SECTION_ORDER.includes(section.kind))
    .sort((a, b) => SECTION_ORDER.indexOf(a.kind) - SECTION_ORDER.indexOf(b.kind));
}

function nounFor(profile: ActionQueueInput["investorProfile"]) {
  return profile === "thesis_driven" ? "thesis" : "reason";
}

function positionAction(
  sectionKind: DashboardCommandCenter["sections"][number]["kind"],
  item: DashboardCommandCenterHolding,
  investorProfile: ActionQueueInput["investorProfile"],
): DashboardAction {
  const ticker = cleanTicker(item.holding.ticker);
  const noun = nounFor(investorProfile);

  if (sectionKind === "needs_review") {
    return {
      key: `decision:${item.holding.id}`,
      kind: "decision",
      eyebrow: "Decision due",
      ticker,
      title: `${ticker} needs your read.`,
      detail: item.workflow_reason || item.latest_event_summary || `Review the latest evidence against your ${noun}.`,
      ctaLabel: item.primary_cta_label || `Review ${ticker}`,
      href: item.primary_cta_href,
    };
  }

  if (sectionKind === "decision_debt") {
    return {
      key: `follow-up:${item.holding.id}`,
      kind: "follow_up",
      eyebrow: "Follow-up waiting",
      ticker,
      title: `${ticker} still needs closure.`,
      detail: item.open_loop_detail || item.workflow_reason || "Finish the review before moving on.",
      ctaLabel: item.primary_cta_label || `Revisit ${ticker}`,
      href: item.primary_cta_href,
    };
  }

  if (item.workflow_state === "draft_ready") {
    return {
      key: `draft:${item.holding.id}`,
      kind: "setup",
      eyebrow: "Draft ready",
      ticker,
      title: `Review ${ticker}'s ${noun}.`,
      detail: `An AI draft is waiting for your judgment before it becomes the live ${noun}.`,
      ctaLabel: item.primary_cta_label || `Review ${noun}`,
      href: item.primary_cta_href,
    };
  }

  if (item.workflow_state === "signals_unconfirmed") {
    return {
      key: `signals:${item.holding.id}`,
      kind: "setup",
      eyebrow: "Checks to confirm",
      ticker,
      title: `Confirm ${ticker}'s checks.`,
      detail: `The ${noun} is there. Confirm the suggested checks before monitoring goes live.`,
      ctaLabel: item.primary_cta_label || "Confirm checks",
      href: item.primary_cta_href,
    };
  }

  if (item.workflow_state === "no_thesis") {
    return {
      key: `write:${item.holding.id}`,
      kind: "setup",
      eyebrow: "Reason missing",
      ticker,
      title: `Write why you own ${ticker}.`,
      detail: `Give this position a clear ${noun} before the next weekly read.`,
      ctaLabel: item.primary_cta_label || `Write ${noun}`,
      href: item.primary_cta_href,
    };
  }

  if (item.case_quality === "review_overdue") {
    return {
      key: `refresh:${item.holding.id}`,
      kind: "setup",
      eyebrow: "Refresh due",
      ticker,
      title: `Refresh ${ticker}'s ${noun}.`,
      detail: `The ${noun} is due for a refresh before you rely on it again.`,
      ctaLabel: `Refresh ${noun}`,
      href: item.primary_cta_href,
    };
  }

  return {
    key: `clarify:${item.holding.id}`,
    kind: "setup",
    eyebrow: "Needs clarity",
    ticker,
    title: `Clarify ${ticker}'s ${noun}.`,
    detail: item.workflow_reason || `Make the condition that would change your mind more specific.`,
    ctaLabel: item.primary_cta_label || `Clarify ${noun}`,
    href: item.primary_cta_href,
  };
}

export function buildDashboardActionQueue({
  commandCenter,
  latestDigest,
  weeklyDigestReady,
  quarterlyReview,
  investorProfile,
  coachPlan = null,
}: ActionQueueInput): DashboardAction[] {
  const actions: DashboardAction[] = [];
  const seenKeys = new Set<string>();

  if (weeklyDigestReady && latestDigest) {
    const nextAction = latestDigest.content.next_action ?? latestDigest.content.action_queue?.[0] ?? null;
    actions.push({
      key: `weekly-review:${latestDigest.id}`,
      kind: "weekly_review",
      eyebrow: nextAction?.carried_forward ? "Still open from last week" : "This week's decision",
      ticker: nextAction?.ticker ?? null,
      title: nextAction?.title || latestDigest.content.headline || "See what changed this week.",
      detail: nextAction?.detail || "See what changed, what held up, and what deserves your next read.",
      ctaLabel: nextAction?.cta_label || "Open weekly read",
      href: nextAction?.cta_href || `/digests/${latestDigest.id}`,
      carriedForward: Boolean(nextAction?.carried_forward),
      sourceDigestId: latestDigest.id,
      secondaryHref: `/digests/${latestDigest.id}`,
      secondaryLabel: nextAction ? "Read weekly context" : undefined,
    });
  }

  if (commandCenter) {
    const seenHoldingIds = new Set<string>();
    for (const section of orderedSections(commandCenter)) {
      for (const item of section.items) {
        if (seenHoldingIds.has(item.holding.id)) continue;
        seenHoldingIds.add(item.holding.id);
        const action = positionAction(section.kind, item, investorProfile);
        if (seenKeys.has(action.key)) continue;
        seenKeys.add(action.key);
        actions.push(action);
        if (actions.length >= 4) return actions;
      }
    }
  }

  if (coachPlan) {
    const holdingId = coachPlan.feedback.holdingId;
    const matchingActionIndex = holdingId
      ? actions.findIndex((action) => action.key.endsWith(`:${holdingId}`))
      : -1;
    const coachAction: DashboardAction = {
      key: `coach:${coachPlan.adviceKey}`,
      kind: "follow_up",
      eyebrow: "Pattern prompt",
      ticker: null,
      title: coachPlan.title,
      detail: coachPlan.body,
      ctaLabel: coachPlan.primaryCta.label,
      href: coachPlan.primaryCta.href,
      coachTarget: coachPlan.primaryCta,
    };

    if (matchingActionIndex >= 0) {
      actions[matchingActionIndex] = coachAction;
    } else if (actions.length < 4) {
      actions.push(coachAction);
    }
  }

  if (quarterlyReview && quarterlyReview.pending_count > 0 && actions.length < 4) {
    actions.push({
      key: `quarterly:${quarterlyReview.review_id}`,
      kind: "quarterly",
      eyebrow: "Quarterly review",
      ticker: null,
      title: `${quarterlyReview.pending_count} position${quarterlyReview.pending_count === 1 ? "" : "s"} need a quarterly check-in.`,
      detail: "Take a slower look at whether your reasons still deserve capital.",
      ctaLabel: "Review the quarter",
      href: "/dashboard/quarterly-review",
    });
  }

  return actions.slice(0, 4);
}
