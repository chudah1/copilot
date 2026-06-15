import test from "node:test";
import assert from "node:assert/strict";

import { buildOnboardingAutoConfirmPayload } from "../src/lib/onboarding-decomposition.ts";
import type { ThesisDecompositionEnvelope } from "../src/types/index.ts";

function makeEnvelope(status: ThesisDecompositionEnvelope["status"]): ThesisDecompositionEnvelope {
  return {
    status,
    message: null,
    decomposition: {
      id: "decomp-1",
      thesis_id: "thesis-1",
      version: 1,
      status,
      reason_type: "business_performance",
      monitorability: "medium",
      decomposition_confidence: 0.88,
      provider: "openai",
      model: "gpt-5.5",
      prompt_version: "v7",
      created_at: "2026-06-15T10:00:00Z",
      claims: [
        {
          id: "claim-1",
          claim_text: "Services revenue compounds",
          claim_type: "growth",
          confidence: 0.9,
          position: 1,
          created_at: "2026-06-15T10:00:00Z",
          entities: [
            {
              id: "entity-1",
              entity_name: "Apple Inc.",
              entity_ticker: "AAPL",
              entity_type: "held_company",
              relation_type: "validated_by",
              rationale: "Core business branch",
              confidence: 0.95,
              confirmation_required: false,
              user_confirmed: true,
              created_at: "2026-06-15T10:00:00Z",
              signals: [
                {
                  id: "signal-1",
                  signal_type: "revenue_growth",
                  signal_label: "AAPL Services revenue growth",
                  signal_config_json: { metric: "revenue_growth_yoy", operator: ">=", threshold_pct: 10 },
                  rationale: "Confirms growth branch",
                  confidence: 0.92,
                  confirmation_required: false,
                  user_confirmed: true,
                  active: true,
                  created_at: "2026-06-15T10:00:00Z",
                },
                {
                  id: "signal-2",
                  signal_type: "news_topic",
                  signal_label: "AAPL regulation headline",
                  signal_config_json: { topic: "AAPL regulation headline" },
                  rationale: "Still needs user review",
                  confidence: 0.72,
                  confirmation_required: true,
                  user_confirmed: null,
                  active: false,
                  created_at: "2026-06-15T10:00:00Z",
                },
              ],
            },
          ],
        },
      ],
    },
  };
}

test("buildOnboardingAutoConfirmPayload confirms active draft signals only", () => {
  const payload = buildOnboardingAutoConfirmPayload(makeEnvelope("draft"));

  assert.deepEqual(payload, {
    decomposition_id: "decomp-1",
    entities: [{ id: "entity-1", user_confirmed: true }],
    signals: [{ id: "signal-1", user_confirmed: true, active: true }],
  });
});

test("buildOnboardingAutoConfirmPayload skips already confirmed decompositions", () => {
  const payload = buildOnboardingAutoConfirmPayload(makeEnvelope("confirmed"));
  assert.equal(payload, null);
});

test("buildOnboardingAutoConfirmPayload returns null when draft has no active signals", () => {
  const envelope = makeEnvelope("draft");
  envelope.decomposition!.claims[0].entities[0].signals = [
    {
      id: "signal-3",
      signal_type: "news_topic",
      signal_label: "AAPL ecosystem commentary",
      signal_config_json: { topic: "AAPL ecosystem commentary" },
      rationale: "Needs review",
      confidence: 0.7,
      confirmation_required: true,
      user_confirmed: null,
      active: false,
      created_at: "2026-06-15T10:00:00Z",
    },
  ];
  envelope.decomposition!.claims[0].entities[0].user_confirmed = null;

  const payload = buildOnboardingAutoConfirmPayload(envelope);
  assert.equal(payload, null);
});
