import test from "node:test";
import assert from "node:assert/strict";

import { classifyCaseQuality } from "../src/lib/decision-state.ts";
import { aiAssistWeakMessaging } from "../src/lib/ai-assisted-thesis.ts";
import type { Thesis } from "../src/types/index.ts";

function thesis(overrides: Partial<Thesis> = {}): Thesis {
  return {
    id: "thesis-1",
    holding_id: "holding-1",
    status: "active",
    thesis_kind: "company",
    why_own_it: "I own Apple because Services keeps taking a bigger share of the mix and deepens the installed-base moat.",
    must_remain_true: "Services growth stays healthy and retention remains strong enough to keep mix and margins improving.",
    what_would_change_my_mind: "I would reconsider if Services growth stalls for multiple quarters or management stops backing the installed-base monetization story.",
    confidence: "medium",
    review_cadence_days: 30,
    ai_summary: "Apple Services thesis.",
    interpretation: {
      labels: ["growth", "quality"],
      monitorability: "medium",
      watch_hints: [
        {
          kind: "metric_threshold",
          metric: "revenue_growth_yoy",
          operator: ">=",
          threshold: 0.1,
          rationale: "Services growth needs to stay healthy.",
        },
      ],
      proxy_signals: [],
      ambiguity_note: "",
    },
    source: "ai_assisted",
    created_at: "2026-06-01T00:00:00.000Z",
    updated_at: "2026-06-05T00:00:00.000Z",
    invalidated_at: null,
    invalidation_reason: null,
    health_score: null,
    health_label: null,
    ...overrides,
  };
}

test("ai-assisted thesis with concrete conditions is not weak once monitorability is medium", () => {
  const result = classifyCaseQuality(thesis(), { now: Date.parse("2026-06-06T00:00:00.000Z") });
  assert.equal(result.kind, "workable");
});

test("shared ai-assist copy treats a weak draft as a starting point, not a scolding verdict", () => {
  const result = aiAssistWeakMessaging("thesis_driven");
  assert.equal(result.insightsLabel, "Needs your pass");
  assert.match(result.insightsNextStep, /The draft is close/i);
  assert.match(result.insightsStatus, /AI drafted the frame/i);
  assert.match(result.cardHeadline, /starting point/i);
});

test("shared ai-assist decision copy tells the user to finish the draft before adding", () => {
  const result = aiAssistWeakMessaging("thesis_driven");
  assert.equal(result.decisionTitle, "Finish the assisted draft before you add.");
  assert.equal(result.decisionCta, "Finish the draft →");
  assert.doesNotMatch(result.decisionBody, /story-like|too vague/i);
});
