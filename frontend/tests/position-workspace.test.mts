import test from "node:test";
import assert from "node:assert/strict";

import {
  loadPositionWorkspace,
  selectActiveThesis,
  selectLatestInvalidatedThesis,
} from "../src/lib/position-workspace.ts";
import type { Holding, HoldingPulse, Thesis } from "../src/types/index.ts";

function holding(id = "holding-1"): Holding {
  return {
    id,
    ticker: "TEST",
    name: "Test Holding",
    exchange: null,
    quantity: 1,
    average_cost_basis: 100,
    average_cost_native: null,
    currency: "GBP",
    current_price: 100,
    current_value: 100,
    sector: null,
    geography: null,
    asset_class: null,
    last_updated_at: "2026-07-17T12:00:00Z",
  };
}

function thesis(id: string, status: Thesis["status"], updatedAt = "2026-07-10T12:00:00Z"): Thesis {
  return {
    id,
    holding_id: "holding-1",
    status,
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
    updated_at: updatedAt,
    invalidated_at: status === "invalidated" ? updatedAt : null,
    invalidation_reason: null,
    health_score: null,
    health_label: null,
  };
}

function pulse(): HoldingPulse {
  return {
    holding_id: "holding-1",
    ticker: "TEST",
    name: "Test Holding",
    pulse_status: "intact",
    pulse_basis: "none",
    reason: "Nothing meaningful changed.",
    assumption_label: null,
    latest_event_summary: null,
    days_since_thesis_update: 7,
    has_thesis: true,
    latest_event_at: null,
    urgency_score: 0,
    pnl_pct: null,
    last_checked_at: null,
    recent_event_count: 0,
    sources_count: null,
  };
}

function reader(routes: Record<string, unknown>) {
  const requests: string[] = [];
  return {
    requests,
    async get<T>(path: string): Promise<T> {
      requests.push(path);
      const value = routes[path];
      if (value instanceof Error) throw value;
      if (!(path in routes)) throw new Error(`Unexpected request: ${path}`);
      return value as T;
    },
  };
}

test("loads one position workspace and selects its related records", async () => {
  const active = thesis("thesis-active", "active");
  const fake = reader({
    "/api/portfolio/holdings": [holding()],
    "/api/theses/holding/holding-1": [active],
    "/api/monitoring/holdings/holding-1/events": [],
    "/api/portfolio/holdings/holding-1/conviction-log": { entries: [] },
    "/api/portfolio/upcoming-earnings": [{ holding_id: "holding-1", ticker: "TEST", name: "Test", report_date: "2026-07-25", days_until: 8 }],
    "/api/onboarding/state": new Error("optional"),
    "/api/monitoring/gaps": [],
    "/api/portfolio/pulse": { pulses: [pulse()], next_digest_at: null },
    "/api/monitoring/holdings/holding-1/reviewed": [],
    "/api/monitoring/holdings/holding-1/supporting": [],
    "/api/theses/thesis-active/decomposition": { status: "ready", message: null, decomposition: null },
  });

  const result = await loadPositionWorkspace(fake, "TEST");
  assert.equal(result.holding?.id, "holding-1");
  assert.equal(result.activeThesis?.id, "thesis-active");
  assert.equal(result.pulse?.holding_id, "holding-1");
  assert.equal(result.upcomingEarnings?.days_until, 8);
  assert.equal(result.onboardingState, null);
  assert.ok(fake.requests.includes("/api/theses/thesis-active/decomposition"));
});

test("returns an empty snapshot without position-specific requests for an unknown ticker", async () => {
  const fake = reader({ "/api/portfolio/holdings": [holding()] });
  const result = await loadPositionWorkspace(fake, "MISSING");
  assert.equal(result.holding, null);
  assert.deepEqual(result.theses, []);
  assert.deepEqual(fake.requests, ["/api/portfolio/holdings"]);
});

test("turns a decomposition failure into workspace state", async () => {
  const active = thesis("thesis-active", "active");
  const fake = reader({
    "/api/portfolio/holdings": [holding()],
    "/api/theses/holding/holding-1": [active],
    "/api/monitoring/holdings/holding-1/events": [],
    "/api/portfolio/holdings/holding-1/conviction-log": null,
    "/api/portfolio/upcoming-earnings": [],
    "/api/onboarding/state": null,
    "/api/monitoring/gaps": [],
    "/api/portfolio/pulse": null,
    "/api/monitoring/holdings/holding-1/reviewed": [],
    "/api/monitoring/holdings/holding-1/supporting": [],
    "/api/theses/thesis-active/decomposition": new Error("Coverage service unavailable"),
  });
  const result = await loadPositionWorkspace(fake, "TEST");
  assert.equal(result.decompositionEnvelope?.status, "failed");
  assert.equal(result.decompositionEnvelope?.message, "Coverage service unavailable");
});

test("workspace selectors keep active and historical cases distinct", () => {
  const old = thesis("old", "invalidated", "2026-06-01T12:00:00Z");
  const recent = thesis("recent", "invalidated", "2026-07-01T12:00:00Z");
  const active = thesis("active", "needs_review");
  assert.equal(selectActiveThesis([old, active, recent])?.id, "active");
  assert.equal(selectLatestInvalidatedThesis([old, active, recent])?.id, "recent");
});
