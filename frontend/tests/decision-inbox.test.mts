import test from "node:test";
import assert from "node:assert/strict";

import { buildDecisionInbox } from "../src/lib/decision-inbox.ts";
import type { Holding, HoldingPulse, Thesis, UpcomingEarnings } from "../src/types/index.ts";

const NOW = Date.parse("2026-07-17T12:00:00Z");

function holding(id: string, value: number): Holding {
  return {
    id,
    ticker: id.toUpperCase(),
    name: id,
    exchange: null,
    quantity: 1,
    average_cost_basis: value,
    average_cost_native: null,
    currency: "GBP",
    current_price: value,
    current_value: value,
    sector: null,
    geography: null,
    asset_class: null,
    last_updated_at: "2026-07-17T12:00:00Z",
  };
}

function thesis(holdingId: string, overrides: Partial<Thesis> = {}): Thesis {
  return {
    id: `thesis-${holdingId}`,
    holding_id: holdingId,
    status: "active",
    thesis_kind: "company",
    why_own_it: "Recurring revenue should compound.",
    must_remain_true: "Retention remains high.",
    what_would_change_my_mind: "Retention falls below 90%.",
    confidence: "medium",
    review_cadence_days: 30,
    ai_summary: null,
    interpretation: { monitorability: "high" },
    source: "user",
    created_at: "2026-01-01T12:00:00Z",
    updated_at: "2026-07-10T12:00:00Z",
    invalidated_at: null,
    invalidation_reason: null,
    health_score: null,
    health_label: null,
    ...overrides,
  };
}

function pulse(
  holdingId: string,
  status: HoldingPulse["pulse_status"],
  urgency: number,
  basis: HoldingPulse["pulse_basis"] = status === "intact" ? "none" : "evidence",
): HoldingPulse {
  return {
    holding_id: holdingId,
    ticker: holdingId.toUpperCase(),
    name: holdingId,
    pulse_status: status,
    pulse_basis: basis,
    reason: "Evidence changed.",
    assumption_label: null,
    latest_event_summary: null,
    days_since_thesis_update: 0,
    has_thesis: true,
    latest_event_at: null,
    urgency_score: urgency,
    pnl_pct: null,
    last_checked_at: null,
    recent_event_count: 0,
    sources_count: null,
  };
}

function earnings(holdingId: string, daysUntil: number): UpcomingEarnings {
  return {
    holding_id: holdingId,
    ticker: holdingId.toUpperCase(),
    name: holdingId,
    report_date: "2026-07-25",
    days_until: daysUntil,
  };
}

test("orders the inbox by decision need before urgency and writing gaps", () => {
  const result = buildDecisionInbox({
    holdings: [holding("missing", 500), holding("watch", 200), holding("review-low", 100), holding("review-high", 50)],
    theses: [thesis("watch"), thesis("review-low"), thesis("review-high")],
    pulses: [pulse("watch", "watch", 90), pulse("review-low", "review", 10), pulse("review-high", "review", 80)],
    upcomingEarnings: [],
    now: NOW,
  });

  assert.deepEqual(result.entries.map((entry) => entry.holding.id), ["review-high", "review-low", "watch", "missing"]);
  assert.deepEqual(result.counts, { needsDecision: 2, changed: 1, needsWrittenCase: 1 });
  assert.equal(result.primaryEntry?.holding.id, "review-high");
});

test("keeps overdue writing out of the attention queue", () => {
  const result = buildDecisionInbox({
    holdings: [holding("old", 100)],
    theses: [thesis("old", { updated_at: "2026-01-01T12:00:00Z" })],
    pulses: [pulse("old", "watch", 60, "case_review")],
    upcomingEarnings: [],
    now: NOW,
  });

  assert.equal(result.entries[0].decisionState.kind, "calm");
  assert.equal(result.entries[0].caseQuality.kind, "review_overdue");
  assert.equal(result.attentionEntries.length, 0);
});

test("uses a near earnings date only after evidence and writing gaps are clear", () => {
  const result = buildDecisionInbox({
    holdings: [holding("soon", 100), holding("large", 500)],
    theses: [thesis("soon"), thesis("large")],
    pulses: [pulse("soon", "intact", 0), pulse("large", "intact", 0)],
    upcomingEarnings: [earnings("soon", 7), earnings("large", 30)],
    now: NOW,
  });

  assert.equal(result.nearTermEarnings?.holding_id, "soon");
  assert.deepEqual(result.visibleEarnings.map((item) => item.holding_id), ["soon"]);
  assert.equal(result.primaryEntry?.holding.id, "soon");
});
