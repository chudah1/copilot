import type { Holding, Thesis } from "@/types";

export type InvestorProfile = "thesis_driven" | "hearsay_driven";

export interface WizardState {
  holdingId: string | null;
  investorProfile: InvestorProfile;
  answer1: string;
  answer2: string;
}

export const EMPTY_WIZARD_STATE: WizardState = {
  holdingId: null,
  investorProfile: "thesis_driven",
  answer1: "",
  answer2: "",
};

export function resolveInitialWizardState(
  stored: WizardState,
  options: { queryHoldingId: string | null; freshImport: boolean },
): WizardState {
  const baseState = options.freshImport
    ? { ...EMPTY_WIZARD_STATE, investorProfile: stored.investorProfile }
    : stored;

  return options.queryHoldingId
    ? { ...baseState, holdingId: options.queryHoldingId }
    : baseState;
}

function holdingSelectionValue(holding: Holding): number {
  if (holding.current_value !== null && Number.isFinite(holding.current_value)) {
    return holding.current_value;
  }

  const costValue = holding.quantity * holding.average_cost_basis;
  return Number.isFinite(costValue) ? costValue : 0;
}

export function selectLargestUncoveredHolding(
  holdings: Holding[],
  theses: Thesis[],
): Holding | null {
  const coveredHoldingIds = new Set(theses.map((thesis) => thesis.holding_id));
  return holdings
    .filter((holding) => !coveredHoldingIds.has(holding.id))
    .sort((a, b) => {
      const valueDifference = holdingSelectionValue(b) - holdingSelectionValue(a);
      return valueDifference || a.ticker.localeCompare(b.ticker);
    })[0] ?? null;
}
