import type { HoldingPulse, Thesis } from "@/types";

export type DecisionStateKind = "needs_written_case" | "needs_decision" | "changed" | "calm";
export type CaseQualityKind = "missing" | "weak" | "review_overdue" | "workable" | "sharp";

export interface DecisionState {
  kind: DecisionStateKind;
  label: "Needs a written case" | "Needs a decision" | "Changed" | "Calm";
  priority: number;
}

export interface CaseReviewPressure {
  level: "watch" | "review";
  daysOld: number;
  cadenceDays: number;
}

export interface CaseQuality {
  kind: CaseQualityKind;
  rank: number;
  daysOld: number | null;
  cadenceDays: number | null;
  monitorability: "high" | "medium" | "low" | null;
  ambiguityNote: string;
  missingBreakCondition: boolean;
  missingMustRemainTrue: boolean;
  reviewPressure: CaseReviewPressure | null;
}

export function ageInDays(dateString: string, now = Date.now()) {
  const then = new Date(dateString).getTime();
  return Math.max(0, Math.floor((now - then) / (1000 * 60 * 60 * 24)));
}

export function getDecisionState(args: {
  thesis?: Thesis;
  pulse?: HoldingPulse | null;
}): DecisionState {
  const { thesis, pulse } = args;
  if (!thesis?.why_own_it.trim()) {
    return { kind: "needs_written_case", label: "Needs a written case", priority: 2 };
  }
  if ((pulse?.pulse_basis !== "case_review" && pulse?.pulse_status === "review") || thesis.status === "needs_review") {
    return { kind: "needs_decision", label: "Needs a decision", priority: 0 };
  }
  if (pulse?.pulse_basis !== "case_review" && pulse?.pulse_status === "watch") {
    return { kind: "changed", label: "Changed", priority: 1 };
  }
  return { kind: "calm", label: "Calm", priority: 3 };
}

export function getCaseReviewPressure(
  thesis: Thesis | undefined,
  options?: { now?: number },
): CaseReviewPressure | null {
  if (!thesis) return null;

  const daysOld = ageInDays(thesis.updated_at, options?.now);
  const cadenceDays = Math.max(thesis.review_cadence_days || 30, 14);
  const monitorability = readMonitorability(thesis);
  let watchThreshold = Math.max(cadenceDays, 21);
  let reviewThreshold = Math.max(cadenceDays * 3, 120);

  if (thesis.confidence === "high") {
    watchThreshold = Math.max(watchThreshold - 7, 21);
    reviewThreshold = Math.max(reviewThreshold - 14, 90);
  }
  if (monitorability === "low") {
    watchThreshold = Math.max(watchThreshold - 7, 14);
    reviewThreshold = Math.max(reviewThreshold - 14, 75);
  }

  if (daysOld >= reviewThreshold) return { level: "review", daysOld, cadenceDays };
  if (daysOld >= watchThreshold) return { level: "watch", daysOld, cadenceDays };
  return null;
}

export function classifyCaseQuality(
  thesis: Thesis | undefined,
  options?: { now?: number },
): CaseQuality {
  if (!thesis?.why_own_it.trim()) {
    return {
      kind: "missing",
      rank: 0,
      daysOld: null,
      cadenceDays: null,
      monitorability: null,
      ambiguityNote: "",
      missingBreakCondition: true,
      missingMustRemainTrue: true,
      reviewPressure: null,
    };
  }

  const monitorability = readMonitorability(thesis);
  const ambiguityNote = readAmbiguityNote(thesis);
  const cadenceDays = Math.max(thesis.review_cadence_days || 30, 14);
  const daysOld = ageInDays(thesis.updated_at, options?.now);
  const missingBreakCondition = !thesis.what_would_change_my_mind?.trim();
  const missingMustRemainTrue = !thesis.must_remain_true?.trim();
  const reviewPressure = getCaseReviewPressure(thesis, options);
  const shared = {
    daysOld,
    cadenceDays,
    monitorability,
    ambiguityNote,
    missingBreakCondition,
    missingMustRemainTrue,
    reviewPressure,
  };

  if (monitorability === "low" || ambiguityNote || (missingBreakCondition && missingMustRemainTrue)) {
    return { kind: "weak", rank: 1, ...shared };
  }
  if (reviewPressure) {
    return { kind: "review_overdue", rank: 2, ...shared };
  }
  if (monitorability !== "high" || missingBreakCondition || missingMustRemainTrue) {
    return { kind: "workable", rank: 3, ...shared };
  }
  return { kind: "sharp", rank: 4, ...shared };
}

function readMonitorability(thesis: Thesis) {
  const value = thesis.interpretation?.monitorability;
  return typeof value === "string" && ["high", "medium", "low"].includes(value)
    ? (value as "high" | "medium" | "low")
    : null;
}

function readAmbiguityNote(thesis: Thesis) {
  const value = thesis.interpretation?.ambiguity_note;
  return typeof value === "string" ? value.trim() : "";
}
