import test from "node:test";
import assert from "node:assert/strict";

import {
  encodePositionTab,
  resolvePositionTabs,
} from "../src/app/dashboard/positions/[ticker]/position-tab-state.ts";

test("resolves monitoring route state", () => {
  assert.deepEqual(resolvePositionTabs("monitoring"), {
    activeTab: "monitoring",
    thesisSubTab: "thesis",
  });
});

test("resolves signals route state", () => {
  assert.deepEqual(resolvePositionTabs("signals"), {
    activeTab: "thesis",
    thesisSubTab: "signals",
  });
});

test("resolves legacy decisions route state", () => {
  assert.deepEqual(resolvePositionTabs("decisions"), {
    activeTab: "thesis",
    thesisSubTab: "log",
  });
});

test("encodes thesis root without a tab param", () => {
  assert.equal(encodePositionTab("thesis", "thesis"), null);
});

test("encodes signals as a route tab", () => {
  assert.equal(encodePositionTab("thesis", "signals"), "signals");
});

test("encodes monitoring as a route tab", () => {
  assert.equal(encodePositionTab("monitoring", "thesis"), "monitoring");
});
