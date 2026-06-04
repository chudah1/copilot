type InvestorProfile = "thesis_driven" | "hearsay_driven" | null | undefined;

export function assumptionFallback(investorProfile: InvestorProfile) {
  return investorProfile === "hearsay_driven" ? "the original story" : "the core assumption";
}

function truncateAtWordBoundary(value: string, maxLength: number) {
  if (value.length <= maxLength) {
    return value;
  }

  const sliced = value.slice(0, maxLength - 1);
  const boundary = sliced.lastIndexOf(" ");
  const trimmed = (boundary > Math.floor(maxLength * 0.6) ? sliced.slice(0, boundary) : sliced).trim();
  return `${trimmed}…`;
}

export function formatAssumptionLabel(
  label: string | null | undefined,
  investorProfile: InvestorProfile,
  options?: { maxLength?: number; sentenceCaseFallback?: boolean },
) {
  const fallback = assumptionFallback(investorProfile);
  if (!label || !label.trim()) {
    return options?.sentenceCaseFallback ? fallback.replace(/^the /, "The ") : fallback;
  }

  let cleaned = label.trim().replace(/\s+/g, " ");
  cleaned = cleaned.replace(/^(?:[A-Z0-9_.-]+:)+/g, "").trim();
  cleaned = cleaned.replace(/^(news touches|earnings touch|event touches)\s*/i, "").trim();
  cleaned = cleaned.replace(/^['"]+|['"]+$/g, "").trim();
  cleaned = cleaned.replace(/[.,;:-]+$/g, "").trim();

  if (!cleaned) {
    return options?.sentenceCaseFallback ? fallback.replace(/^the /, "The ") : fallback;
  }

  if (options?.maxLength && cleaned.length > options.maxLength) {
    cleaned = truncateAtWordBoundary(cleaned, options.maxLength);
  }

  return cleaned;
}
