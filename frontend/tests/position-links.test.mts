import test from "node:test";
import assert from "node:assert/strict";

import {
  positionBlindSpotHref,
  positionDecisionTrailHref,
  positionDetailHref,
  positionMonitoringHref,
} from "../src/lib/position-links.ts";

test("builds a plain position detail href", () => {
  assert.equal(positionDetailHref("TSLA"), "/dashboard/positions/TSLA");
});

test("builds a monitoring tab href", () => {
  assert.equal(positionMonitoringHref("NVDA"), "/dashboard/positions/NVDA?tab=monitoring");
  assert.equal(
    positionDetailHref("NVDA", { tab: "monitoring" }),
    "/dashboard/positions/NVDA?tab=monitoring",
  );
});

test("builds a decision-trail href", () => {
  assert.equal(positionDecisionTrailHref("META"), "/dashboard/positions/META?tab=decisions");
});

test("builds the blind-spot write flow href", () => {
  assert.equal(
    positionBlindSpotHref("TSLA"),
    "/dashboard/positions/TSLA?source=dashboard_blind_spot",
  );
});
