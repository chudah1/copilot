import assert from "node:assert/strict";
import test from "node:test";

import { buildDashboardActionQueue } from "../src/lib/dashboard-action-queue.ts";
import type { DashboardCommandCenter, Digest } from "../src/types/index.ts";

const sameHolding = {
  id: "hims-id",
  ticker: "HIMS_US_EQ",
  name: "Hims",
} as DashboardCommandCenter["sections"][number]["items"][number]["holding"];

function commandCenter(): DashboardCommandCenter {
  return {
    investor_profile: "thesis_driven",
    summary: {
      needs_review_count: 0,
      held_up_count: 0,
      unclear_theses_count: 1,
      decision_debt_count: 1,
    },
    sections: [
      {
        kind: "decision_debt",
        title: "Decision debt",
        count: 1,
        empty_copy: "",
        items: [{
          holding: sameHolding,
          workflow_state: "decision_needed",
          workflow_label: "Needs closure",
          workflow_reason: "A review is still waiting.",
          primary_cta_label: "Resolve HIMS",
          primary_cta_href: "/dashboard/positions/HIMS?tab=monitoring",
          pulse_status: "review",
          pulse_basis: "case_review",
          assumption_label: "Demand stays strong",
          case_quality: "sharp",
          days_since_thesis_update: 5,
          latest_event_summary: null,
          supporting_title: null,
          supporting_summary: null,
          supporting_created_at: null,
          open_loop_count: 1,
          open_loop_title: "Review waiting",
          open_loop_detail: "A review is still waiting.",
          thesis_id: "thesis-id",
        }],
      },
      {
        kind: "unclear_theses",
        title: "Needs clarity",
        count: 1,
        empty_copy: "",
        items: [{
          holding: sameHolding,
          workflow_state: "signals_unconfirmed",
          workflow_label: "Confirm signals",
          workflow_reason: "Confirm the checks.",
          primary_cta_label: "Confirm signals",
          primary_cta_href: "/dashboard/positions/HIMS?tab=signals",
          pulse_status: "watch",
          pulse_basis: "case_review",
          assumption_label: "Demand stays strong",
          case_quality: "workable",
          days_since_thesis_update: 5,
          latest_event_summary: null,
          supporting_title: null,
          supporting_summary: null,
          supporting_created_at: null,
          open_loop_count: 0,
          open_loop_title: null,
          open_loop_detail: null,
          thesis_id: "thesis-id",
        }],
      },
    ],
  };
}

test("deduplicates a holding that appears in multiple dashboard sections", () => {
  const queue = buildDashboardActionQueue({
    commandCenter: commandCenter(),
    latestDigest: null,
    weeklyDigestReady: false,
    quarterlyReview: null,
    investorProfile: "thesis_driven",
  });

  assert.equal(queue.length, 1);
  assert.equal(queue[0].ticker, "HIMS");
  assert.equal(queue[0].kind, "follow_up");
});

test("puts an unread weekly review before position work", () => {
  const digest = {
    id: "digest-id",
    sent_at: null,
    reviewed_at: null,
    period_start: "2026-08-01T00:00:00Z",
    period_end: "2026-08-08T00:00:00Z",
    status: "sent",
    content: {
      headline: "One reason needs review this week.",
      next_action: {
        action_key: "follow-up:hims",
        kind: "follow_up",
        ticker: "HIMS",
        title: "Close the open review.",
        detail: "A review is still waiting.",
        cta_label: "Review",
        cta_href: "/dashboard/positions/HIMS",
        priority: 1,
        carried_forward: true,
      },
    },
  } as Digest;

  const queue = buildDashboardActionQueue({
    commandCenter: commandCenter(),
    latestDigest: digest,
    weeklyDigestReady: true,
    quarterlyReview: null,
    investorProfile: "thesis_driven",
  });

  assert.equal(queue[0].kind, "weekly_review");
  assert.equal(queue[0].carriedForward, true);
  assert.equal(queue[1].ticker, "HIMS");
});
