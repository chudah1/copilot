"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { InfoTip } from "@/components/ui/info-tip";
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

const CLAIM_TYPE_LABELS: Record<string, string> = {
  must_remain_true: "Must hold",
  what_would_change_my_mind: "Exit trigger",
  why_own_it: "Bull case",
  thesis: "Core belief",
};

const MONITORABILITY_DOT: Record<string, string> = {
  high: "bg-emerald-500",
  medium: "bg-amber-400",
  low: "bg-red-500",
};

const MONITORABILITY_TEXT: Record<string, string> = {
  high: "text-emerald-700",
  medium: "text-amber-700",
  low: "text-red-600",
};

// ── Helpers ──────────────────────────────────────────────────────────────────

function collectInitialSelections(envelope: ThesisDecompositionEnvelope | null) {
  const next = new Set<string>();
  if (!envelope?.decomposition) return next;
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

function hasSelectionChanges(envelope: ThesisDecompositionEnvelope | null, selectedSignalIds: Set<string>) {
  if (!envelope?.decomposition) return false;
  for (const claim of envelope.decomposition.claims) {
    for (const entity of claim.entities) {
      for (const signal of entity.signals) {
        const initial = signal.active || signal.user_confirmed === true;
        const current = selectedSignalIds.has(signal.id);
        if (initial !== current) return true;
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
      entities.push({ id: entity.id, user_confirmed: entitySelectionState(entity, selectedSignalIds) });
      for (const signal of entity.signals) {
        const selected = selectedSignalIds.has(signal.id);
        signals.push({ id: signal.id, user_confirmed: selected, active: selected });
      }
    }
  }
  return { decomposition_id: decompositionId, entities, signals };
}

// ── Component ─────────────────────────────────────────────────────────────────

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
      if (next.has(signalId)) next.delete(signalId);
      else next.add(signalId);
      return next;
    });
  };

  const handleConfirm = async () => {
    if (!decomposition) return;
    await onConfirm(buildConfirmationPayload(decomposition.id, decomposition.claims, selectedSignalIds));
  };

  // ── Loading ─────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="product-panel p-5 sm:p-6">
        <div className="flex items-center gap-3">
          <span className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground animate-pulse">
            Building signal map…
          </span>
        </div>
      </div>
    );
  }

  // ── No decomposition yet ─────────────────────────────────────────────────

  if (!envelope) {
    return (
      <div className="product-panel p-5 sm:p-6 space-y-4">
        <div className="space-y-1">
          <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
            Signal setup
          </p>
          <p className="font-display italic text-xl leading-tight text-foreground">
            Turn the thesis into signals.
          </p>
        </div>
        <p className="font-sans text-sm text-muted-foreground leading-relaxed max-w-lg">
          We pull out what has to stay true and suggest what to watch.
        </p>
        <div className="flex items-center gap-4 pt-1">
          <button
            onClick={onGenerate}
            className="font-mono text-[10px] uppercase tracking-[0.15em] bg-primary text-primary-foreground px-5 py-2.5 hover:bg-primary/90 transition-colors"
          >
            Generate signals
          </button>
          <span className="font-mono text-[9px] text-muted-foreground/80 uppercase tracking-[0.15em]">
            About 30s
          </span>
        </div>
      </div>
    );
  }

  // ── Failed / pending without decomposition ───────────────────────────────

  if ((isPending || isFailed) && !isReviewable) {
    return (
      <div className="product-panel border border-red-200/60 bg-red-500/5 p-5 sm:p-6 space-y-3">
        <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-red-600">
          Signal setup failed
        </p>
        {envelope.message && (
          <p className="font-sans text-sm text-foreground/80 leading-relaxed">{envelope.message}</p>
        )}
        <p className="font-sans text-sm text-muted-foreground leading-relaxed">
          Add more specific conditions, then retry.
        </p>
        <button
          onClick={onGenerate}
          className="font-mono text-[10px] uppercase tracking-[0.15em] border border-border text-foreground/70 hover:text-foreground px-4 py-2 transition-colors"
        >
          Retry
        </button>
      </div>
    );
  }

  if (!decomposition) return null;

  // ── Main decomposition display ───────────────────────────────────────────

  const allSignals = decomposition.claims.flatMap((c) => c.entities.flatMap((e) => e.signals));
  const totalSignals = allSignals.length;
  const activeCount = allSignals.filter((s) => selectedSignalIds.has(s.id)).length;
  const mon = decomposition.monitorability ?? "";
  const confPct = decomposition.decomposition_confidence != null
    ? Math.round(decomposition.decomposition_confidence * 100)
    : null;
  const needsExplicitConfirmation =
    envelope.status === "draft" || envelope.status === "partially_confirmed";
  const showPrimaryConfirm = dirty || needsExplicitConfirmation;
  const primaryButtonLabel = saving
    ? "Saving…"
    : !dirty && envelope.status === "draft"
      ? "Use setup"
      : !dirty && envelope.status === "partially_confirmed"
        ? "Keep setup"
        : "Save setup";

  return (
    <div className="space-y-6">

      {/* Status strip */}
      <div className="product-panel p-5 sm:p-6">
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-1.5">
              <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                Signal setup
              </p>
              <InfoTip label="Signal setup">
                PenKeep turns the case into measurable checks. Keep only the signals that genuinely represent what you meant.
              </InfoTip>
            </div>
            <p className="font-sans text-sm leading-relaxed text-foreground/80">
              Keep what matches the case.
            </p>
          </div>
          <span className={`shrink-0 font-mono text-[9px] uppercase tracking-[0.15em] ${
            envelope.status === "confirmed" ? "text-emerald-700"
            : envelope.status === "partially_confirmed" ? "text-amber-700"
            : "text-muted-foreground/80"
          }`}>
            {envelope.status.replaceAll("_", " ")}
          </span>
        </div>

        <div className="mt-4 grid gap-3 sm:grid-cols-3">
          <div className="border border-border/60 bg-background/70 p-3">
            <div className="flex items-center gap-1.5">
              <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                Live
              </p>
              <InfoTip label="Live signals">
                The checks currently selected for monitoring out of all the signals PenKeep suggested.
              </InfoTip>
            </div>
            <p className="mt-2 font-display text-[1.15rem] italic leading-none text-foreground">
              {activeCount}/{totalSignals}
            </p>
          </div>
          {mon && (
            <div className="border border-border/60 bg-background/70 p-3">
              <div className="flex items-center gap-1.5">
                <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                  Watchability
                </p>
                <InfoTip label="Watchability">
                  How readily the case can be tested with public data. A low read usually means the conditions need to be more specific.
                </InfoTip>
              </div>
              <div className="mt-2 flex items-center gap-2">
                <span className={`h-1.5 w-1.5 rounded-full ${MONITORABILITY_DOT[mon] ?? "bg-border"}`} />
                <p className={`font-display text-[1.15rem] italic leading-none ${MONITORABILITY_TEXT[mon] ?? "text-muted-foreground"}`}>
                  {mon}
                </p>
              </div>
            </div>
          )}
          {confPct != null && (
            <div className="border border-border/60 bg-background/70 p-3">
              <div className="flex items-center gap-1.5">
                <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                  Confidence
                </p>
                <InfoTip label="Signal setup confidence">
                  How confident PenKeep is that it understood and translated the case correctly. It is not confidence in the stock.
                </InfoTip>
              </div>
              <p className="mt-2 font-display text-[1.15rem] italic leading-none text-foreground">
                {confPct}%
              </p>
            </div>
          )}
        </div>

        {!dirty && envelope.status === "draft" && activeCount > 0 && (
          <p className="mt-4 inline-block border border-primary/20 px-2 py-1 font-mono text-[9px] uppercase tracking-[0.12em] text-primary/80">
            Setup ready
          </p>
        )}
      </div>

      {/* Claims */}
      <div className="space-y-8">
        {decomposition.claims.map((claim, claimIndex) => {
          const claimActiveSignals = claim.entities
            .flatMap((e) => e.signals)
            .filter((s) => selectedSignalIds.has(s.id)).length;

          return (
            <motion.div
              key={claim.id}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.2, delay: claimIndex * 0.05 }}
              className="space-y-4"
            >
              {/* Claim header */}
              <div className="space-y-2">
                <div className="flex items-center gap-3">
                  {claim.claim_type && (
                    <span className="font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground border border-border/60 px-1.5 py-0.5">
                      {CLAIM_TYPE_LABELS[claim.claim_type] ?? claim.claim_type.replaceAll("_", " ")}
                    </span>
                  )}
                  <span className="font-mono text-[9px] text-muted-foreground/80 tabular-nums">
                    {claimActiveSignals} active
                  </span>
                </div>
                <blockquote className="product-panel border border-border/60 bg-background/72 px-4 py-3">
                  <p className="font-display italic text-[1.05rem] leading-snug text-foreground">
                    &ldquo;{claim.claim_text}&rdquo;
                  </p>
                </blockquote>
              </div>

              {/* Entities + Signals */}
              <div className="space-y-4 pl-1">
                {claim.entities.map((entity) => {
                  const entityActive = entitySelectionState(entity, selectedSignalIds);
                  return (
                    <div key={entity.id} className="space-y-2">
                      {/* Entity header */}
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className={`font-mono text-[10px] font-medium tracking-[0.12em] ${entityActive ? "text-foreground" : "text-muted-foreground"}`}>
                          {entity.entity_name}
                          {entity.entity_ticker ? ` (${entity.entity_ticker})` : ""}
                        </span>
                        {entity.entity_type && (
                          <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-muted-foreground/80 border border-border/50 px-1 py-px">
                            {entity.entity_type.replaceAll("_", " ")}
                          </span>
                        )}
                        {entity.confirmation_required && (
                          <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-amber-700 border border-amber-200 px-1 py-px">
                            check source
                          </span>
                        )}
                      </div>
                      {entity.rationale && (
                        <p className="font-sans text-xs text-foreground/70 leading-relaxed">
                          {entity.rationale}
                        </p>
                      )}

                      {/* Signal rows */}
                      <div className="space-y-1">
                        {entity.signals.map((signal) => {
                          const selected = selectedSignalIds.has(signal.id);
                          return (
                            <button
                              key={signal.id}
                              onClick={() => toggleSignal(signal.id)}
                              className={`product-panel w-full flex items-start gap-3 px-4 py-3 text-left transition-all duration-150 border ${
                                selected
                                  ? "border-emerald-500/30 bg-emerald-500/5 hover:bg-emerald-500/8"
                                  : "border-border/50 bg-background/72 hover:border-foreground/20"
                              }`}
                            >
                              {/* Toggle dot */}
                              <span className={`font-mono text-[12px] mt-[1px] shrink-0 transition-colors ${
                                selected ? "text-emerald-600" : "text-muted-foreground/80"
                              }`}>
                                {selected ? "●" : "○"}
                              </span>

                              {/* Signal content */}
                              <div className="min-w-0 flex-1 space-y-1">
                                <div className="flex items-center gap-2 flex-wrap">
                                  <p className={`font-sans text-[13px] leading-tight transition-colors ${
                                    selected ? "text-foreground" : "text-muted-foreground"
                                  }`}>
                                    {signal.signal_label ?? signal.signal_type.replaceAll("_", " ")}
                                  </p>
                                  <span className="font-mono text-[7px] uppercase tracking-[0.15em] text-muted-foreground/80 border border-border/40 px-1 py-px">
                                    {signal.signal_type.replaceAll("_", " ")}
                                  </span>
                                  {signal.confirmation_required && !signal.active && (
                                    <span className="font-mono text-[7px] uppercase tracking-[0.12em] text-amber-700/70 border border-amber-200/60 px-1 py-px">
                                      review first
                                    </span>
                                  )}
                                  {signal.confidence != null && (
                                    <span className="font-mono text-[7px] text-muted-foreground/80 tabular-nums">
                                      {Math.round(signal.confidence * 100)}%
                                    </span>
                                  )}
                                </div>
                                {signal.rationale && (
                                  <p className="font-sans text-xs text-foreground/70 leading-relaxed">
                                    {signal.rationale}
                                  </p>
                                )}
                              </div>
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Divider between claims */}
              {claimIndex < decomposition.claims.length - 1 && (
                <div className="h-px bg-border/30 mt-6" />
              )}
            </motion.div>
          );
        })}
      </div>

      {/* Footer: meta + actions */}
      <div className="border-t border-border/40 pt-4 flex items-center justify-between gap-4 flex-wrap">
        <div className="space-y-1">
          <div className="flex items-center gap-3 flex-wrap">
            <p className="font-mono text-[9px] text-muted-foreground/80">
              Generated {formatDate(decomposition.created_at)}
            </p>
          </div>
          {needsExplicitConfirmation && (
            <p className="font-sans text-xs text-muted-foreground leading-relaxed">
              {activeCount > 0
                ? "We pre-picked the best match. Keep it or tweak it."
                : "Pick at least one signal, then confirm."}
            </p>
          )}
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={onGenerate}
            className="border border-border/60 bg-background/72 px-3 py-1.5 font-mono text-[9px] uppercase tracking-[0.15em] text-muted-foreground transition-colors hover:border-border hover:text-foreground"
          >
            Regenerate
          </button>

          <AnimatePresence>
            {showPrimaryConfirm && (
              <motion.button
                initial={{ opacity: 0, x: 6 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 6 }}
                transition={{ duration: 0.15 }}
                onClick={handleConfirm}
                disabled={saving || activeCount === 0}
                className="font-mono text-[9px] uppercase tracking-[0.15em] bg-primary text-primary-foreground px-4 py-1.5 hover:bg-primary/90 transition-colors disabled:opacity-50"
              >
                {primaryButtonLabel}
              </motion.button>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}
