import type { Thesis } from "@/types";

export type ThesisQualityKind =
  | "missing"
  | "review"
  | "weak"
  | "stale"
  | "workable"
  | "sharp";

export interface ThesisQuality {
  kind: ThesisQualityKind;
  rank: number;
  daysOld: number | null;
  cadenceDays: number | null;
  monitorability: "high" | "medium" | "low" | null;
  ambiguityNote: string;
  missingBreakCondition: boolean;
  missingMustRemainTrue: boolean;
}

export function ageInDays(dateString: string, now = Date.now()) {
  const then = new Date(dateString).getTime();
  return Math.max(0, Math.floor((now - then) / (1000 * 60 * 60 * 24)));
}

export function classifyThesisQuality(
  thesis: Thesis | undefined,
  options?: { now?: number },
): ThesisQuality {
  if (!thesis) {
    return {
      kind: "missing",
      rank: 0,
      daysOld: null,
      cadenceDays: null,
      monitorability: null,
      ambiguityNote: "",
      missingBreakCondition: true,
      missingMustRemainTrue: true,
    };
  }

  const interpretation = thesis.interpretation ?? {};
  const monitorability =
    interpretation && typeof interpretation.monitorability === "string" && ["high", "medium", "low"].includes(interpretation.monitorability)
      ? (interpretation.monitorability as "high" | "medium" | "low")
      : null;
  const ambiguityNote =
    interpretation && typeof interpretation.ambiguity_note === "string"
      ? interpretation.ambiguity_note.trim()
      : "";
  const cadenceDays = Math.max(thesis.review_cadence_days || 30, 14);
  const daysOld = ageInDays(thesis.updated_at, options?.now);
  const missingBreakCondition = !thesis.what_would_change_my_mind?.trim();
  const missingMustRemainTrue = !thesis.must_remain_true?.trim();

  if (thesis.status === "needs_review") {
    return {
      kind: "review",
      rank: 1,
      daysOld,
      cadenceDays,
      monitorability,
      ambiguityNote,
      missingBreakCondition,
      missingMustRemainTrue,
    };
  }

  if (monitorability === "low" || ambiguityNote || (missingBreakCondition && missingMustRemainTrue)) {
    return {
      kind: "weak",
      rank: 2,
      daysOld,
      cadenceDays,
      monitorability,
      ambiguityNote,
      missingBreakCondition,
      missingMustRemainTrue,
    };
  }

  if (daysOld > cadenceDays) {
    return {
      kind: "stale",
      rank: 3,
      daysOld,
      cadenceDays,
      monitorability,
      ambiguityNote,
      missingBreakCondition,
      missingMustRemainTrue,
    };
  }

  if (monitorability !== "high" || missingBreakCondition || missingMustRemainTrue) {
    return {
      kind: "workable",
      rank: 4,
      daysOld,
      cadenceDays,
      monitorability,
      ambiguityNote,
      missingBreakCondition,
      missingMustRemainTrue,
    };
  }

  return {
    kind: "sharp",
    rank: 5,
    daysOld,
    cadenceDays,
    monitorability,
    ambiguityNote,
    missingBreakCondition,
    missingMustRemainTrue,
  };
}
