import type { ConfirmDecompositionRequest, ThesisDecompositionEnvelope } from "@/types";

export function buildOnboardingAutoConfirmPayload(
  envelope: ThesisDecompositionEnvelope | null,
): ConfirmDecompositionRequest | null {
  const decomposition = envelope?.decomposition;
  if (!decomposition || decomposition.status !== "draft") {
    return null;
  }

  const entities: ConfirmDecompositionRequest["entities"] = [];
  const signals: ConfirmDecompositionRequest["signals"] = [];

  for (const claim of decomposition.claims ?? []) {
    for (const entity of claim.entities ?? []) {
      const confirmableSignals = (entity.signals ?? []).filter(
        (signal) => signal.active || signal.user_confirmed === true,
      );
      if (confirmableSignals.length === 0) {
        continue;
      }

      entities.push({
        id: entity.id,
        user_confirmed: true,
      });

      for (const signal of confirmableSignals) {
        signals.push({
          id: signal.id,
          user_confirmed: true,
          active: signal.active,
        });
      }
    }
  }

  if (entities.length === 0 && signals.length === 0) {
    return null;
  }

  return {
    decomposition_id: decomposition.id,
    entities,
    signals,
  };
}
