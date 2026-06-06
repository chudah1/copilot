export function aiAssistWeakMessaging(
  investorProfile?: "thesis_driven" | "hearsay_driven" | null,
) {
  return {
    cardHeadline: "AI gave you a starting point.",
    cardDetail: "One manual pass will make it usable.",
    qualitySummary: "Good starting point. Give it one clean pass.",
    insightsLabel: "Needs your pass",
    insightsNextStep: "The draft is close. Make one clean pass on the driver and break condition.",
    insightsStatus: "AI drafted the frame, but it still needs your final judgment.",
    decisionTitle: "Finish the assisted draft before you add.",
    decisionBody:
      investorProfile === "hearsay_driven"
        ? "The AI gave you a starting point. Make the business reason and break condition fully yours before you add capital."
        : "The AI gave you a starting point. Make the driver and break condition fully yours before you add capital.",
    decisionCta: "Finish the draft →",
  };
}
