import { classifyCaseQuality, getDecisionState } from "./decision-state.ts";
import type { CaseQuality, DecisionState } from "@/lib/decision-state";
import type { Holding, HoldingPulse, Thesis, UpcomingEarnings } from "@/types";

export const EARNINGS_HORIZON_DAYS = 21;

export interface DecisionInboxEntry {
  holding: Holding;
  thesis?: Thesis;
  pulse?: HoldingPulse;
  earnings?: UpcomingEarnings;
  decisionState: DecisionState;
  caseQuality: CaseQuality;
}

export interface DecisionInbox {
  entries: DecisionInboxEntry[];
  entriesByHoldingId: Record<string, DecisionInboxEntry>;
  thesesByHoldingId: Record<string, Thesis>;
  pulsesByHoldingId: Record<string, HoldingPulse>;
  earningsByHoldingId: Record<string, UpcomingEarnings>;
  attentionEntries: DecisionInboxEntry[];
  counts: {
    needsDecision: number;
    changed: number;
    needsWrittenCase: number;
  };
  caseQualityCounts: Record<CaseQuality["kind"], number>;
  weakestCaseEntry: DecisionInboxEntry | null;
  primaryEntry: DecisionInboxEntry | null;
  nextEarnings: UpcomingEarnings | null;
  nearTermEarnings: UpcomingEarnings | null;
  visibleEarnings: UpcomingEarnings[];
}

export function buildDecisionInbox(args: {
  holdings: Holding[];
  theses: Thesis[];
  pulses: HoldingPulse[];
  upcomingEarnings: UpcomingEarnings[];
  now?: number;
}): DecisionInbox {
  const { holdings, theses, pulses, upcomingEarnings, now } = args;
  const thesisByHoldingId = Object.fromEntries(theses.map((thesis) => [thesis.holding_id, thesis]));
  const pulseByHoldingId = Object.fromEntries(pulses.map((pulse) => [pulse.holding_id, pulse]));
  const earningsByHoldingId = Object.fromEntries(upcomingEarnings.map((earnings) => [earnings.holding_id, earnings]));

  const entries = holdings.map((holding) => {
    const thesis = thesisByHoldingId[holding.id];
    const pulse = pulseByHoldingId[holding.id];
    return {
      holding,
      thesis,
      pulse,
      earnings: earningsByHoldingId[holding.id],
      decisionState: getDecisionState({ thesis, pulse }),
      caseQuality: classifyCaseQuality(thesis, { now }),
    };
  }).sort(compareEntries);

  const entriesByHoldingId = Object.fromEntries(entries.map((entry) => [entry.holding.id, entry]));
  const attentionEntries = entries.filter(
    (entry) => entry.decisionState.kind === "needs_decision" || entry.decisionState.kind === "changed",
  );
  const counts = {
    needsDecision: entries.filter((entry) => entry.decisionState.kind === "needs_decision").length,
    changed: entries.filter((entry) => entry.decisionState.kind === "changed").length,
    needsWrittenCase: entries.filter((entry) => entry.decisionState.kind === "needs_written_case").length,
  };
  const caseQualityCounts = {
    missing: 0,
    weak: 0,
    review_overdue: 0,
    workable: 0,
    sharp: 0,
  };
  for (const entry of entries) caseQualityCounts[entry.caseQuality.kind] += 1;

  const weakestCaseEntry = [...entries].sort((a, b) => {
    const qualityDifference = a.caseQuality.rank - b.caseQuality.rank;
    return qualityDifference || holdingValue(b.holding) - holdingValue(a.holding);
  })[0] ?? null;
  const nextEarnings = [...upcomingEarnings].sort((a, b) => a.days_until - b.days_until)[0] ?? null;
  const nearTermEarnings = nextEarnings && nextEarnings.days_until <= EARNINGS_HORIZON_DAYS
    ? nextEarnings
    : null;
  const visibleEarnings = upcomingEarnings
    .filter((earnings) => earnings.days_until <= EARNINGS_HORIZON_DAYS)
    .sort((a, b) => a.days_until - b.days_until);
  const largestMissingEntry = entries
    .filter((entry) => entry.decisionState.kind === "needs_written_case")
    .sort((a, b) => holdingValue(b.holding) - holdingValue(a.holding))[0] ?? null;
  const earningsEntry = nearTermEarnings ? entriesByHoldingId[nearTermEarnings.holding_id] ?? null : null;
  const largestEntry = [...entries].sort((a, b) => holdingValue(b.holding) - holdingValue(a.holding))[0] ?? null;
  const primaryEntry = attentionEntries[0] ?? largestMissingEntry ?? earningsEntry ?? largestEntry;

  return {
    entries,
    entriesByHoldingId,
    thesesByHoldingId: thesisByHoldingId,
    pulsesByHoldingId: pulseByHoldingId,
    earningsByHoldingId,
    attentionEntries,
    counts,
    caseQualityCounts,
    weakestCaseEntry,
    primaryEntry,
    nextEarnings,
    nearTermEarnings,
    visibleEarnings,
  };
}

function compareEntries(a: DecisionInboxEntry, b: DecisionInboxEntry) {
  const stateDifference = a.decisionState.priority - b.decisionState.priority;
  if (stateDifference) return stateDifference;
  const urgencyDifference = (b.pulse?.urgency_score ?? 0) - (a.pulse?.urgency_score ?? 0);
  if (urgencyDifference) return urgencyDifference;
  const qualityDifference = a.caseQuality.rank - b.caseQuality.rank;
  if (qualityDifference) return qualityDifference;
  return holdingValue(b.holding) - holdingValue(a.holding);
}

function holdingValue(holding: Holding) {
  return holding.current_value ?? 0;
}
