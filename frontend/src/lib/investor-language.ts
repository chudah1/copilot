export function normalizeInvestorTerminology(
  value: string,
  investorProfile: "thesis_driven" | "hearsay_driven" | null | undefined,
) {
  if (investorProfile !== "thesis_driven") {
    return value;
  }

  return value
    .replace(/\bYour reason\b/g, "Your thesis")
    .replace(/\byour reason\b/g, "your thesis")
    .replace(/\bThe reason\b/g, "The thesis")
    .replace(/\bthe reason\b/g, "the thesis")
    .replace(/\bThis reason\b/g, "This thesis")
    .replace(/\bthis reason\b/g, "this thesis")
    .replace(/\bWritten reason\b/g, "Written thesis")
    .replace(/\bwritten reason\b/g, "written thesis")
    .replace(/\bOriginal reason\b/g, "Original thesis")
    .replace(/\boriginal reason\b/g, "original thesis")
    .replace(/\bSupports reason\b/g, "Supports thesis")
    .replace(/\bThreatens reason\b/g, "Threatens thesis");
}

export function tightenInvestorCopy(
  value: string,
  investorProfile: "thesis_driven" | "hearsay_driven" | null | undefined,
) {
  return normalizeInvestorTerminology(value, investorProfile)
    .replace(
      /This (thesis|reason) is (\d+) days old and (\d+) days past its review cadence\./gi,
      (_match, noun: string, daysOld: string, daysPast: string) =>
        `This ${noun.toLowerCase()} is ${daysOld}d old. ${daysPast}d past cadence.`,
    )
    .replace(
      /This (thesis|reason) is (\d+) days old and past its (\d+)-day cadence\./gi,
      (_match, noun: string, daysOld: string, cadenceDays: string) =>
        `This ${noun.toLowerCase()} is ${daysOld}d old. Cadence ${cadenceDays}d.`,
    )
    .replace(
      /This (thesis|reason) is (\d+) days old and behind its (\d+)-day cadence\./gi,
      (_match, noun: string, daysOld: string, cadenceDays: string) =>
        `This ${noun.toLowerCase()} is ${daysOld}d old. Cadence ${cadenceDays}d.`,
    );
}
