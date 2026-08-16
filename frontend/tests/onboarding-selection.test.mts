import assert from "node:assert/strict";
import test from "node:test";

import {
  recoverWizardStateForMissingHolding,
  resolveInitialWizardState,
  selectLargestUncoveredHolding,
  type WizardState,
} from "../src/lib/onboarding-wizard.ts";
import type { Holding, Thesis } from "../src/types/index.ts";

function holding(
  id: string,
  ticker: string,
  quantity: number,
  averageCostBasis: number,
  currentValue: number | null,
): Holding {
  return {
    id,
    ticker,
    name: ticker,
    exchange: null,
    quantity,
    average_cost_basis: averageCostBasis,
    average_cost_native: null,
    currency: "GBP",
    current_price: null,
    current_value: currentValue,
    sector: null,
    geography: null,
    asset_class: null,
    last_updated_at: "2026-07-22T12:00:00Z",
  };
}

test("selects the largest uncovered holding by cost when live values are unavailable", () => {
  const smallFirst = holding("small", "SMALL", 1, 100, null);
  const largeSecond = holding("large", "LARGE", 10, 200, null);

  const selected = selectLargestUncoveredHolding([smallFirst, largeSecond], []);

  assert.equal(selected?.ticker, "LARGE");
});

test("uses current market value when it is available", () => {
  const higherCost = holding("cost", "COST", 100, 100, 500);
  const higherMarketValue = holding("market", "MARKET", 1, 100, 900);

  const selected = selectLargestUncoveredHolding([higherCost, higherMarketValue], []);

  assert.equal(selected?.ticker, "MARKET");
});

test("does not select a holding that already has a written case", () => {
  const covered = holding("covered", "COVERED", 10, 200, null);
  const uncovered = holding("uncovered", "OPEN", 2, 100, null);
  const thesis = { holding_id: covered.id } as Thesis;

  const selected = selectLargestUncoveredHolding([covered, uncovered], [thesis]);

  assert.equal(selected?.ticker, "OPEN");
});

test("a fresh import clears a stale onboarding position and answers", () => {
  const stored: WizardState = {
    holdingId: "old-holding",
    investorProfile: "hearsay_driven",
    answer1: "An old answer",
    answer2: "An old break condition",
  };

  const resolved = resolveInitialWizardState(stored, {
    queryHoldingId: null,
    freshImport: true,
  });

  assert.deepEqual(resolved, {
    holdingId: null,
    investorProfile: "hearsay_driven",
    answer1: "",
    answer2: "",
  });
});

test("an explicit holding after import keeps the fresh state", () => {
  const stored: WizardState = {
    holdingId: "old-holding",
    investorProfile: "thesis_driven",
    answer1: "An old answer",
    answer2: "An old break condition",
  };

  const resolved = resolveInitialWizardState(stored, {
    queryHoldingId: "selected-holding",
    freshImport: true,
  });

  assert.equal(resolved.holdingId, "selected-holding");
  assert.equal(resolved.answer1, "");
  assert.equal(resolved.answer2, "");
});

test("recovering from a missing onboarding holding resets answers onto the next uncovered name", () => {
  const current: WizardState = {
    holdingId: "missing-holding",
    investorProfile: "thesis_driven",
    answer1: "Old draft",
    answer2: "Old break",
  };

  const covered = holding("covered", "NVDA", 5, 100, 700);
  const next = holding("next", "TSLA", 2, 200, 450);
  const thesis = { holding_id: covered.id } as Thesis;

  const recovered = recoverWizardStateForMissingHolding([covered, next], [thesis], current);

  assert.deepEqual(recovered, {
    holdingId: "next",
    investorProfile: "thesis_driven",
    answer1: "",
    answer2: "",
  });
});

test("recovering from a missing onboarding holding returns null when nothing else is uncovered", () => {
  const current: WizardState = {
    holdingId: "missing-holding",
    investorProfile: "hearsay_driven",
    answer1: "Old draft",
    answer2: "Old break",
  };

  const covered = holding("covered", "NVDA", 5, 100, 700);
  const thesis = { holding_id: covered.id } as Thesis;

  const recovered = recoverWizardStateForMissingHolding([covered], [thesis], current);

  assert.equal(recovered, null);
});
