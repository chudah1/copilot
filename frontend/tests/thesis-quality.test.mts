import test from "node:test";
import assert from "node:assert/strict";

import { classifyCaseQuality } from "../src/lib/decision-state.ts";
import type { Thesis } from "../src/types/index.ts";

function thesis(overrides: Partial<Thesis> = {}): Thesis {
  return {
    id: "thesis-1",
    holding_id: "holding-1",
    status: "active",
    thesis_kind: "company",
    why_own_it: "Margins stay above 60% while revenue keeps compounding from AI demand.",
    must_remain_true: "Gross margin stays above 60% and management keeps guiding to sustained data-center demand.",
    what_would_change_my_mind: "Two quarters of margin compression below 55% or a clear demand slowdown would break the case.",
    confidence: "high",
    review_cadence_days: 30,
    ai_summary: null,
    interpretation: {
      labels: ["growth", "quality"],
      monitorability: "high",
      watch_hints: [],
      proxy_signals: [],
      ambiguity_note: "",
    },
    source: "user",
    created_at: "2026-05-01T00:00:00.000Z",
    updated_at: "2026-06-01T00:00:00.000Z",
    invalidated_at: null,
    invalidation_reason: null,
    health_score: null,
    health_label: null,
    ...overrides,
  };
}

const now = Date.parse("2026-06-03T00:00:00.000Z");

test("classifies missing thesis", () => {
  const result = classifyCaseQuality(undefined, { now });
  assert.equal(result.kind, "missing");
});

test("keeps decision state out of case quality", () => {
  const result = classifyCaseQuality(thesis({ status: "needs_review" }), { now });
  assert.equal(result.kind, "sharp");
});

test("classifies vague thesis as weak", () => {
  const result = classifyCaseQuality(
    thesis({
      interpretation: {
        labels: ["theme"],
        monitorability: "low",
        watch_hints: [],
        proxy_signals: [],
        ambiguity_note: "Too vague to map to clear evidence.",
      },
      must_remain_true: null,
      what_would_change_my_mind: null,
    }),
    { now },
  );
  assert.equal(result.kind, "weak");
});

test("classifies a case overdue for review", () => {
  const result = classifyCaseQuality(
    thesis({
      review_cadence_days: 14,
      updated_at: "2026-04-20T00:00:00.000Z",
    }),
    { now },
  );
  assert.equal(result.kind, "review_overdue");
});

test("classifies medium-monitorability thesis as workable, not sharp", () => {
  const result = classifyCaseQuality(
    thesis({
      interpretation: {
        labels: ["growth"],
        monitorability: "medium",
        watch_hints: [],
        proxy_signals: [],
        ambiguity_note: "",
      },
    }),
    { now },
  );
  assert.equal(result.kind, "workable");
});

test("classifies fully explicit thesis as sharp", () => {
  const result = classifyCaseQuality(thesis(), { now });
  assert.equal(result.kind, "sharp");
});
