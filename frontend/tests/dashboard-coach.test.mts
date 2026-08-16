import assert from "node:assert/strict";
import test from "node:test";

import { deriveDashboardCoach } from "../src/lib/dashboard-coach.ts";
import type {
  DashboardBlindSpot,
  DashboardCoachMemory,
  DashboardDecisionMemory,
  DashboardOpenLoop,
  DashboardWorkspace,
  DashboardWorkspaceItem,
  Holding,
} from "../src/types/index.ts";

function holding(ticker: string): Holding {
  return {
    id: `${ticker}-id`,
    ticker,
    name: ticker,
    exchange: null,
    quantity: 1,
    average_cost_basis: 100,
    average_cost_native: null,
    currency: "GBP",
    current_price: 100,
    current_value: 100,
    portfolio_currency: "GBP",
    preferred_currency: "GBP",
    fx_unavailable: false,
    sector: null,
    geography: null,
    asset_class: null,
    last_updated_at: "2026-08-11T10:00:00Z",
  };
}

function topDecision(overrides: Partial<DashboardWorkspaceItem> = {}): DashboardWorkspaceItem {
  return {
    holding: holding("NVDA"),
    thesis_id: "thesis-1",
    decision_state: "needs_decision",
    case_quality: "sharp",
    pulse_status: "review",
    pulse_basis: "evidence",
    assumption_label: "Demand stays strong",
    reason: "Demand is under pressure and needs a call.",
    latest_event_summary: null,
    urgency_score: 9,
    days_since_thesis_update: 7,
    review_cadence_days: 30,
    ...overrides,
  };
}

function decisionMemory(overrides: Partial<DashboardDecisionMemory> = {}): DashboardDecisionMemory {
  return {
    resolved_count: 4,
    open_followups_count: 1,
    has_pattern: true,
    primary_pattern: {
      kind: "attention",
      tone: "warning",
      headline: "You tend to wave off the first warning.",
      detail: "Early evidence often gets noticed, but not closed out.",
      instances: 3,
      hits: 2,
    },
    secondary_patterns: [],
    ...overrides,
  };
}

function blindSpot(overrides: Partial<DashboardBlindSpot> = {}): DashboardBlindSpot {
  return {
    holding: holding("TSLA"),
    thesis_id: "thesis-2",
    blind_spot_kind: "weak",
    reason: "Still vague.",
    review_cadence_days: 30,
    days_since_thesis_update: 60,
    ...overrides,
  };
}

function workspace(overrides: Partial<DashboardWorkspace> = {}): DashboardWorkspace {
  return {
    investor_profile: "thesis_driven",
    portfolio_state: {
      kind: "needs_decision",
      primary_holding_id: "NVDA-id",
      primary_ticker: "NVDA",
      assumption_label: "Demand stays strong",
      needs_decision_count: 1,
      changed_count: 0,
      needs_written_case_count: 0,
    },
    summary_metrics: {
      total_value: 100,
      total_cost: 100,
      total_pnl: 0,
      total_pnl_pct: 0,
      portfolio_currency: "GBP",
      preferred_currency: "GBP",
      fx_unavailable: false,
      holdings_count: 1,
      monitored_count: 1,
      needs_decision_count: 1,
      changed_count: 0,
      needs_written_case_count: 0,
      drafts_ready_count: 0,
      drafts_pending_count: 0,
    },
    top_decision: topDecision(),
    watchlist: [],
    blind_spots: [blindSpot()],
    recent_decisions: [],
    decision_memory: decisionMemory(),
    ...overrides,
  };
}

test("prefers pattern-under-pressure coaching when live pressure and a learned pattern both exist", () => {
  const plan = deriveDashboardCoach({
    workspace: workspace(),
    openLoops: [],
  });

  assert.equal(plan.mode, "pattern_under_pressure");
  assert.equal(plan.primaryCta.href, "/dashboard/positions/NVDA?tab=monitoring");
  assert.match(plan.title, /NVDA/);
  assert.match(plan.body, /Your recent pattern/i);
});

test("uses resolved coach outcomes when available", () => {
  const coachMemory: DashboardCoachMemory = {
    total_presented: 3,
    acted_count: 2,
    skipped_count: 1,
    last_feedback: "acted",
    last_mode: "pattern_under_pressure",
    mode_stats: {
      pattern_under_pressure: {
        presented_count: 3,
        acted_count: 2,
        skipped_count: 1,
        resolved_count: 2,
        helpful_count: 2,
        hurt_count: 0,
      },
    },
  };

  const plan = deriveDashboardCoach({
    workspace: workspace(),
    openLoops: [],
    coachMemory,
  });

  assert.match(plan.context, /later read held up/i);
  assert.deepEqual(plan.stats[1], { label: "Held up", value: "2" });
});

test("falls back to closing the oldest open loop when there is no live pressure", () => {
  const plan = deriveDashboardCoach({
    workspace: workspace({
      portfolio_state: {
        kind: "calm",
        primary_holding_id: null,
        primary_ticker: null,
        assumption_label: null,
        needs_decision_count: 0,
        changed_count: 0,
        needs_written_case_count: 0,
      },
      top_decision: topDecision({ decision_state: "calm", pulse_status: "intact" }),
    }),
    openLoops: [
      {
        loop_key: "claim_review:1",
        loop_type: "claim_review",
        holding_id: "META-id",
        thesis_id: "thesis-3",
        ticker: "META",
        name: "Meta",
        title: "META needs a call.",
        detail: "Fresh evidence still needs a decision.",
        opened_at: "2026-08-10T10:00:00Z",
        age_days: 1,
        priority: 0,
        cta_label: "Finish claim review",
        cta_href: "/dashboard/positions/META?tab=monitoring",
      } satisfies DashboardOpenLoop,
    ],
  });

  assert.equal(plan.mode, "close_open_loop");
  assert.equal(plan.primaryCta.label, "Finish claim review");
  assert.match(plan.title, /META/);
});
