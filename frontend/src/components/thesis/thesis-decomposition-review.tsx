"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { formatDate } from "@/lib/utils";
import type {
  ConfirmDecompositionRequest,
  ThesisDecompositionClaim,
  ThesisDecompositionEntity,
  ThesisDecompositionEnvelope,
} from "@/types";

interface Props {
  envelope: ThesisDecompositionEnvelope | null;
  loading: boolean;
  saving: boolean;
  onGenerate: () => Promise<void>;
  onConfirm: (payload: ConfirmDecompositionRequest) => Promise<void>;
}

const statusTone: Record<string, string> = {
  draft: "bg-sky-100 text-sky-800",
  confirmed: "bg-emerald-100 text-emerald-800",
  partially_confirmed: "bg-amber-100 text-amber-800",
  rejected: "bg-rose-100 text-rose-800",
  pending: "bg-stone-200 text-stone-800",
  failed: "bg-red-100 text-red-800",
};

function collectInitialSelections(envelope: ThesisDecompositionEnvelope | null) {
  const next = new Set<string>();
  if (!envelope?.decomposition) {
    return next;
  }
  for (const claim of envelope.decomposition.claims) {
    for (const entity of claim.entities) {
      for (const signal of entity.signals) {
        if (signal.active || signal.user_confirmed === true) {
          next.add(signal.id);
        }
      }
    }
  }
  return next;
}

function entitySelectionState(entity: ThesisDecompositionEntity, selectedSignalIds: Set<string>) {
  return entity.signals.some((signal) => selectedSignalIds.has(signal.id));
}

function signalMeta(entity: ThesisDecompositionEntity, selected: boolean) {
  if (entity.entity_type === "held_company" && !entity.confirmation_required) {
    return selected ? "Direct signal active" : "Direct signal available";
  }
  return selected ? "AI-suggested signal active" : "AI-suggested signal";
}

function hasSelectionChanges(envelope: ThesisDecompositionEnvelope | null, selectedSignalIds: Set<string>) {
  if (!envelope?.decomposition) return false;
  for (const claim of envelope.decomposition.claims) {
    for (const entity of claim.entities) {
      for (const signal of entity.signals) {
        const initial = signal.active || signal.user_confirmed === true;
        const current = selectedSignalIds.has(signal.id);
        if (initial !== current) {
          return true;
        }
      }
    }
  }
  return false;
}

function buildConfirmationPayload(
  decompositionId: string,
  claims: ThesisDecompositionClaim[],
  selectedSignalIds: Set<string>,
): ConfirmDecompositionRequest {
  const entities: ConfirmDecompositionRequest["entities"] = [];
  const signals: ConfirmDecompositionRequest["signals"] = [];

  for (const claim of claims) {
    for (const entity of claim.entities) {
      const entityConfirmed = entitySelectionState(entity, selectedSignalIds);
      entities.push({
        id: entity.id,
        user_confirmed: entityConfirmed,
      });

      for (const signal of entity.signals) {
        const selected = selectedSignalIds.has(signal.id);
        signals.push({
          id: signal.id,
          user_confirmed: selected,
          active: selected,
        });
      }
    }
  }

  return {
    decomposition_id: decompositionId,
    entities,
    signals,
  };
}

export function ThesisDecompositionReview({ envelope, loading, saving, onGenerate, onConfirm }: Props) {
  const [selectedSignalIds, setSelectedSignalIds] = useState<Set<string>>(() => collectInitialSelections(envelope));

  const decomposition = envelope?.decomposition ?? null;
  const isPending = envelope?.status === "pending";
  const isFailed = envelope?.status === "failed";
  const isReviewable = decomposition !== null;
  const dirty = hasSelectionChanges(envelope, selectedSignalIds);

  const toggleSignal = (signalId: string) => {
    setSelectedSignalIds((current) => {
      const next = new Set(current);
      if (next.has(signalId)) {
        next.delete(signalId);
      } else {
        next.add(signalId);
      }
      return next;
    });
  };

  const handleConfirm = async () => {
    if (!decomposition) return;
    await onConfirm(buildConfirmationPayload(decomposition.id, decomposition.claims, selectedSignalIds));
  };

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Suggested signals</CardTitle>
          <CardDescription>Loading decomposition…</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  if (!envelope) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Suggested signals</CardTitle>
          <CardDescription>
            Turn your written thesis into specific signals you can confirm or reject before monitoring starts.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap items-center justify-between gap-3">
          <p className="max-w-2xl text-sm text-muted-foreground">
            Generate a decomposition once the thesis looks good. We will suggest direct and AI-inferred signals to watch.
          </p>
          <Button onClick={onGenerate}>Generate signals</Button>
        </CardContent>
      </Card>
    );
  }

  if ((isPending || isFailed) && !isReviewable) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Suggested signals</CardTitle>
          <CardDescription>{envelope.message ?? "We could not map this thesis yet."}</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap items-center justify-between gap-3">
          <p className="max-w-2xl text-sm text-muted-foreground">
            Your thesis is saved. Try again once the provider path is available or after you tighten the reasoning.
          </p>
          <Button onClick={onGenerate} variant="outline">
            Retry decomposition
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (!decomposition) {
    return null;
  }

  return (
    <Card>
      <CardHeader className="gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <CardTitle className="text-base">Suggested signals</CardTitle>
          <Badge className={statusTone[envelope.status] ?? statusTone.draft}>{envelope.status.replaceAll("_", " ")}</Badge>
          {decomposition.monitorability && <Badge variant="outline">{decomposition.monitorability} monitorability</Badge>}
          {decomposition.provider && <Badge variant="outline">{decomposition.provider}</Badge>}
        </div>
        <CardDescription>
          Confirm what should actually be monitored. Direct company signals can stay on; speculative ones should earn their place.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        {decomposition.claims.map((claim) => (
          <div key={claim.id} className="rounded-xl border p-4">
            <div className="flex flex-wrap items-center gap-2">
              <p className="font-medium">{claim.claim_text}</p>
              {claim.claim_type && <Badge variant="outline">{claim.claim_type}</Badge>}
            </div>
            <div className="mt-4 space-y-3">
              {claim.entities.map((entity) => {
                const selectedCount = entity.signals.filter((signal) => selectedSignalIds.has(signal.id)).length;
                return (
                  <div key={entity.id} className="rounded-lg border bg-muted/20 p-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="font-medium">
                        {entity.entity_name}
                        {entity.entity_ticker ? ` (${entity.entity_ticker})` : ""}
                      </p>
                      {entity.entity_type && <Badge variant="outline">{entity.entity_type.replaceAll("_", " ")}</Badge>}
                      <Badge className={selectedCount > 0 ? "bg-emerald-100 text-emerald-800" : "bg-stone-200 text-stone-800"}>
                        {selectedCount > 0 ? `${selectedCount} active` : "inactive"}
                      </Badge>
                    </div>
                    {entity.rationale && <p className="mt-2 text-sm text-muted-foreground">{entity.rationale}</p>}
                    <div className="mt-3 space-y-2">
                      {entity.signals.map((signal) => {
                        const selected = selectedSignalIds.has(signal.id);
                        return (
                          <label
                            key={signal.id}
                            className={`flex cursor-pointer items-start gap-3 rounded-lg border p-3 transition ${selected ? "border-emerald-300 bg-emerald-50/70" : "border-border bg-background"}`}
                          >
                            <input
                              type="checkbox"
                              checked={selected}
                              onChange={() => toggleSignal(signal.id)}
                              className="mt-1 h-4 w-4 rounded border-border"
                            />
                            <div className="min-w-0 flex-1">
                              <div className="flex flex-wrap items-center gap-2">
                                <p className="font-medium">{signal.signal_label ?? signal.signal_type.replaceAll("_", " ")}</p>
                                <Badge variant="outline">{signal.signal_type.replaceAll("_", " ")}</Badge>
                                {signal.confirmation_required && <Badge className="bg-amber-100 text-amber-800">Needs confirmation</Badge>}
                              </div>
                              <p className="mt-1 text-sm text-muted-foreground">{signal.rationale ?? signalMeta(entity, selected)}</p>
                            </div>
                          </label>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        ))}

        <div className="rounded-xl border bg-muted/20 p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="font-medium">Review state</p>
              <p className="mt-1 text-sm text-muted-foreground">
                Generated {formatDate(decomposition.created_at)} with {decomposition.provider ?? "an LLM provider"}.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button onClick={onGenerate} variant="outline">
                Regenerate
              </Button>
              <Button onClick={handleConfirm} disabled={saving || !dirty}>
                {saving ? "Saving..." : dirty ? "Save monitoring choices" : "Choices saved"}
              </Button>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
