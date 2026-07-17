import test from "node:test";
import assert from "node:assert/strict";

import {
  classifyCaseQuality,
  getCaseReviewPressure,
  getDecisionState,
} from "../src/lib/decision-state.ts";
import type { HoldingPulse, Thesis } from "../src/types/index.ts";

const NOW = Date.parse("2026-07-17T12:00:00Z");

function makeThesis(overrides: Partial<Thesis> = {}): Thesis {
  return {
    id: "thesis-1",
    holding_id: "holding-1",
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

function makePulse(
  status: HoldingPulse["pulse_status"],
  basis: HoldingPulse["pulse_basis"] = status === "intact" ? "none" : "evidence",
): HoldingPulse {
  return {
    holding_id: "holding-1",
    ticker: "TEST",
    name: "Test Holding",
    pulse_status: status,
    pulse_basis: basis,
    urgency_score: 0,
    reason: "",
    assumption_label: null,
    recent_event_count: 0,
    unresolved_event_count: 0,
    days_since_thesis_update: 0,
    has_thesis: true,
    latest_event_summary: null,
    latest_event_at: null,
    last_checked_at: null,
    pnl_pct: null,
    sources_count: null,
  };
}

test("decision state precedence is missing, decision, changed, calm", () => {
  assert.equal(getDecisionState({}).kind, "needs_written_case");
  assert.equal(getDecisionState({ thesis: makeThesis({ status: "needs_review" }) }).kind, "needs_decision");
  assert.equal(getDecisionState({ thesis: makeThesis(), pulse: makePulse("review") }).kind, "needs_decision");
  assert.equal(getDecisionState({ thesis: makeThesis(), pulse: makePulse("watch") }).kind, "changed");
  assert.equal(getDecisionState({ thesis: makeThesis(), pulse: makePulse("intact") }).kind, "calm");
});

test("decision priority puts unresolved evidence before missing writing", () => {
  assert.equal(getDecisionState({ thesis: makeThesis(), pulse: makePulse("review") }).priority, 0);
  assert.equal(getDecisionState({ thesis: makeThesis(), pulse: makePulse("watch") }).priority, 1);
  assert.equal(getDecisionState({}).priority, 2);
  assert.equal(getDecisionState({ thesis: makeThesis() }).priority, 3);
});

test("an overdue case remains calm when no evidence changed", () => {
  const thesis = makeThesis({ updated_at: "2026-01-01T12:00:00Z" });
  assert.equal(getDecisionState({ thesis, pulse: makePulse("intact") }).kind, "calm");
  assert.equal(classifyCaseQuality(thesis, { now: NOW }).kind, "review_overdue");
});

test("review timing from the pulse API does not become changed evidence", () => {
  assert.equal(getDecisionState({ thesis: makeThesis(), pulse: makePulse("watch", "case_review") }).kind, "calm");
  assert.equal(getDecisionState({ thesis: makeThesis(), pulse: makePulse("review", "case_review") }).kind, "calm");
});

test("review pressure uses the shared watch and review thresholds", () => {
  const watch = makeThesis({ updated_at: "2026-05-18T12:00:00Z" });
  const review = makeThesis({ updated_at: "2026-03-01T12:00:00Z" });
  assert.equal(getCaseReviewPressure(watch, { now: NOW })?.level, "watch");
  assert.equal(getCaseReviewPressure(review, { now: NOW })?.level, "review");
});

test("case quality keeps weak writing separate from review timing", () => {
  const weak = makeThesis({
    interpretation: { monitorability: "low", ambiguity_note: "No measurable driver." },
    updated_at: "2026-01-01T12:00:00Z",
  });
  const quality = classifyCaseQuality(weak, { now: NOW });
  assert.equal(quality.kind, "weak");
  assert.equal(quality.reviewPressure?.level, "review");
});

test("an empty draft is still a missing written case", () => {
  const thesis = makeThesis({ why_own_it: "   " });
  assert.equal(getDecisionState({ thesis }).kind, "needs_written_case");
  assert.equal(classifyCaseQuality(thesis, { now: NOW }).kind, "missing");
});
