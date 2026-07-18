"use client";

import { useRef, useState } from "react";
import useSWR from "swr";
import { toast } from "sonner";

import { api, fetcher } from "@/lib/api";
import { Textarea } from "@/components/ui/textarea";
import { formatDate } from "@/lib/utils";
import type {
  ClaimCheckInState,
  ClaimEvidenceItem,
  SubmitClaimReviewsResponse,
  ThesisCheckIn as ThesisCheckInData,
} from "@/types";

type ClaimStatus = "holds" | "weakened" | "broken";
type ThesisAction = "keep_lowered" | "rewrite" | "invalidate";

interface Props {
  thesisId: string;
  ticker: string;
  writtenCase: {
    whyOwnIt: string;
    stillTrueIf: string | null;
    breaksIf: string | null;
  };
  onFlagEvent: (eventId: string) => Promise<void>;
  onAfterSubmit: (result: SubmitClaimReviewsResponse, thesisAction: ThesisAction | null) => Promise<void> | void;
}

const STATUS_CHIP: Record<ClaimStatus, string> = {
  holds: "border-emerald-500/25 bg-emerald-500/8 text-emerald-700",
  weakened: "border-amber-500/25 bg-amber-500/8 text-amber-700",
  broken: "border-red-500/25 bg-red-500/8 text-red-700",
};

const SEVERITY_TEXT: Record<string, string> = {
  thesis_breaking: "text-red-600",
  warning: "text-amber-700",
  info: "text-sky-700",
};

const CASE_SECTION_LABEL: Record<NonNullable<ClaimCheckInState["case_section"]>, string> = {
  why_own_it: "Why I own it",
  must_remain_true: "Still true if",
  what_would_change_my_mind: "Breaks if",
};

function claimKey(claim: ClaimCheckInState): string {
  return claim.claim_id ?? "general";
}

function EvidenceRow({
  item,
  onFlag,
  flagging,
}: {
  item: ClaimEvidenceItem;
  onFlag: (eventId: string) => Promise<void>;
  flagging: boolean;
}) {
  return (
    <div className="border border-border/60 bg-background/70 px-3 py-2.5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className={`font-mono text-[10px] uppercase tracking-[0.14em] ${SEVERITY_TEXT[item.severity] ?? "text-muted-foreground"}`}>
              {item.event_type.replace(/_/g, " ")}
            </span>
            <span className="font-mono text-[10px] text-muted-foreground/70">{formatDate(item.created_at)}</span>
          </div>
          <p className="mt-1.5 font-sans text-sm leading-relaxed text-foreground/90">{item.summary || item.title}</p>
          {item.ai_analysis && (
            <p className="mt-1 font-sans text-xs leading-relaxed text-muted-foreground">{item.ai_analysis}</p>
          )}
          {item.source_url && (
            <a
              href={item.source_url}
              target="_blank"
              rel="noreferrer"
              className="mt-1.5 inline-block font-mono text-[10px] uppercase tracking-[0.12em] text-primary/60 underline underline-offset-2 transition-colors hover:text-primary"
            >
              Source ↗
            </a>
          )}
        </div>
        <button
          type="button"
          disabled={flagging}
          onClick={() => void onFlag(item.id)}
          className="shrink-0 border border-border/70 bg-background px-2.5 py-1.5 font-sans text-xs text-muted-foreground transition-colors hover:border-foreground/30 hover:text-foreground disabled:cursor-not-allowed disabled:opacity-40"
        >
          {flagging ? "Removing…" : "Remove from this case"}
        </button>
      </div>
    </div>
  );
}

export function ThesisCheckIn({ thesisId, ticker, writtenCase, onFlagEvent, onAfterSubmit }: Props) {
  const { data, mutate, isLoading } = useSWR<ThesisCheckInData>(`/api/theses/${thesisId}/check-in`, fetcher);
  const [decisions, setDecisions] = useState<Record<string, ClaimStatus>>({});
  const [notes, setNotes] = useState("");
  const [thesisAction, setThesisAction] = useState<ThesisAction | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const submittingRef = useRef(false);
  const [flaggingId, setFlaggingId] = useState<string | null>(null);

  if (isLoading || !data) {
    return (
      <div className="product-panel p-5 sm:p-6">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-amber-400" />
          Loading the evidence…
        </div>
      </div>
    );
  }

  // What changed should only show parts of the case that have new evidence or
  // need a decision. Empty claims belong on the Original case tab.
  const claims = data.claims.filter(
    (claim) =>
      claim.needs_review ||
      claim.supports.length + claim.threatens.length + claim.neutral.length > 0,
  );
  const hasEvidence = claims.some(
    (claim) => claim.supports.length + claim.threatens.length + claim.neutral.length > 0,
  );
  const pendingClaims = claims.filter((claim) => claim.needs_review);
  const undecided = pendingClaims.filter((claim) => !decisions[claimKey(claim)]);
  const anyBroken = Object.values(decisions).includes("broken");
  const canSubmit =
    Object.keys(decisions).length > 0 &&
    undecided.length === 0 &&
    (!anyBroken || thesisAction !== null) &&
    !submitting;

  const handleFlag = async (eventId: string) => {
    try {
      setFlaggingId(eventId);
      await onFlagEvent(eventId);
      await mutate();
    } finally {
      setFlaggingId(null);
    }
  };

  const handleSubmit = async () => {
    if (!canSubmit || submittingRef.current) return;
    try {
      submittingRef.current = true;
      setSubmitting(true);
      const result = await api.post<SubmitClaimReviewsResponse>(`/api/theses/${thesisId}/claim-reviews`, {
        decisions: Object.entries(decisions).map(([key, status]) => ({
          claim_id: key === "general" ? null : key,
          status,
        })),
        thesis_action: anyBroken ? thesisAction : null,
        notes: notes.trim() ? notes.trim() : null,
      });
      toast.success("Decision recorded.");
      setDecisions({});
      setNotes("");
      setThesisAction(null);
      await mutate();
      await onAfterSubmit(result, anyBroken ? thesisAction : null);
    } catch (error) {
      console.error(error);
      toast.error("Failed to record the decision");
    } finally {
      submittingRef.current = false;
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="space-y-3">
        <div>
          <p className="mb-1 font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
            {pendingClaims.length > 0 ? "Decision needed" : "Evidence reviewed"}
          </p>
          <p className="font-display italic text-[1.6rem] leading-tight text-foreground">
            {pendingClaims.length > 0
              ? `Does this change your written case for ${ticker}?`
              : hasEvidence
                ? "No decision needed."
                : "Nothing is testing your written case right now."}
          </p>
          <p className="mt-2 max-w-2xl font-sans text-sm leading-relaxed text-foreground/75">
            {pendingClaims.length > 0
              ? "Read the evidence, then say whether the part of your case below still holds."
              : "PenKeep checked the new evidence. It does not currently test your case strongly enough to require a decision."}
          </p>
        </div>

        <div className="border-l-2 border-primary/25 bg-background/55 px-4 py-3">
          <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">Your written case</p>
          <div className="mt-3 grid gap-4 lg:grid-cols-3">
            <div>
              <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground/80">Why I own it</p>
              <p className="mt-1.5 font-sans text-sm leading-relaxed text-foreground/85">{writtenCase.whyOwnIt}</p>
            </div>
            {writtenCase.stillTrueIf && (
              <div>
                <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground/80">Still true if</p>
                <p className="mt-1.5 font-sans text-sm leading-relaxed text-foreground/85">{writtenCase.stillTrueIf}</p>
              </div>
            )}
            {writtenCase.breaksIf && (
              <div>
                <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground/80">Breaks if</p>
                <p className="mt-1.5 font-sans text-sm leading-relaxed text-foreground/85">{writtenCase.breaksIf}</p>
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="space-y-3">
        {claims.map((claim) => {
          const key = claimKey(claim);
          const decision = decisions[key];
          const evidenceCount = claim.threatens.length + claim.supports.length + claim.neutral.length;
          return (
            <div
              key={key}
              className={`product-panel p-4 sm:p-5 ${claim.needs_review ? "border-amber-500/30" : ""}`}
            >
              {(claim.needs_review || claim.last_reviewed_at) && <div className="flex flex-wrap items-center gap-2">
                {claim.needs_review && <span className="inline-flex items-center border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 font-mono text-[10px] uppercase tracking-[0.12em] text-amber-700">
                  Needs your decision
                </span>}
                {claim.last_reviewed_at && !claim.needs_review && (
                  <span className="font-mono text-[10px] text-muted-foreground/70">
                    Reviewed {formatDate(claim.last_reviewed_at)}
                  </span>
                )}
              </div>}
              {claim.case_section && (
                <p className="mt-2 font-mono text-[10px] uppercase tracking-[0.14em] text-primary/70">
                  Tests · {CASE_SECTION_LABEL[claim.case_section]}
                </p>
              )}
              <p className="mt-2 font-sans text-sm leading-relaxed text-foreground">
                {claim.claim_id ? `“${claim.label}”` : "Not tied to a specific part of your written case"}
              </p>
              {claim.needs_review_reason && (
                <p className="mt-1 font-sans text-xs leading-relaxed text-amber-700/90">{claim.needs_review_reason}</p>
              )}

              {evidenceCount > 0 && (
                <div className="mt-3 space-y-2">
                  {claim.threatens.length > 0 && (
                    <div className="space-y-2">
                      <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground/80">
                        {claim.needs_review ? "Against" : "Early pressure"} · {claim.threatens.length}
                      </p>
                      {claim.threatens.map((item) => (
                        <EvidenceRow key={item.id} item={item} onFlag={handleFlag} flagging={flaggingId === item.id} />
                      ))}
                    </div>
                  )}
                  {claim.supports.length > 0 && (
                    <div className="space-y-2">
                      <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-emerald-700/80">
                        Held up · {claim.supports.length}
                      </p>
                      {claim.supports.map((item) => (
                        <EvidenceRow key={item.id} item={item} onFlag={handleFlag} flagging={flaggingId === item.id} />
                      ))}
                    </div>
                  )}
                  {claim.neutral.length > 0 && (
                    <div className="space-y-2">
                      <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground/80">
                        Background · {claim.neutral.length}
                      </p>
                      {claim.neutral.map((item) => (
                        <EvidenceRow key={item.id} item={item} onFlag={handleFlag} flagging={flaggingId === item.id} />
                      ))}
                    </div>
                  )}
                </div>
              )}

              {claim.needs_review ? (
                <div className="mt-4 space-y-2">
                  <p className="font-sans text-xs font-medium text-foreground/80">Does this part of your case still hold?</p>
                  <div className="grid gap-2 sm:grid-cols-3">
                    {(
                      [
                        { status: "holds", label: "Yes, it still holds" },
                        { status: "weakened", label: "It makes me less sure" },
                        { status: "broken", label: "No, this breaks it" },
                      ] as const
                    ).map((option) => (
                      <button
                        key={option.status}
                        type="button"
                        onClick={() =>
                          setDecisions((current) => {
                            if (current[key] === option.status) {
                              const next = { ...current };
                              delete next[key];
                              return next;
                            }
                            return { ...current, [key]: option.status };
                          })
                        }
                        className={`border px-3 py-2.5 text-left font-sans text-sm transition-colors ${
                          decision === option.status
                            ? STATUS_CHIP[option.status]
                            : "border-border/70 bg-background/70 text-foreground/80 hover:bg-background"
                        }`}
                      >
                        {option.label}
                      </button>
                    ))}
                  </div>
                </div>
              ) : evidenceCount > 0 ? (
                <p className="mt-3 font-sans text-xs text-muted-foreground">No response needed. This stays in the evidence trail.</p>
              ) : null}
            </div>
          );
        })}
      </div>

      {pendingClaims.length > 0 && <div className="product-panel space-y-4 p-4 sm:p-5">
        {anyBroken && (
          <div className="space-y-2">
            <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-red-700">
              Part of your case broke — what happens now?
            </p>
            <div className="grid gap-2 sm:grid-cols-3">
              {(
                [
                  { value: "keep_lowered", label: "Keep, less sure", detail: "Conviction steps down; monitoring continues." },
                  { value: "rewrite", label: "Rewrite the case", detail: "Update what must be true before monitoring continues." },
                  { value: "invalidate", label: "Mark the case broken", detail: "Close this written case and record why." },
                ] as const
              ).map((option) => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => setThesisAction(option.value)}
                  className={`border p-3 text-left transition-colors ${
                    thesisAction === option.value
                      ? "border-red-500/40 bg-red-500/8"
                      : "border-border/70 bg-background/70 hover:bg-background"
                  }`}
                >
                  <p className="font-sans text-sm text-foreground">{option.label}</p>
                  <p className="mt-1 font-sans text-xs leading-relaxed text-foreground/70">{option.detail}</p>
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="space-y-2">
          <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">Note</p>
          <Textarea
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
            placeholder="Optional. Saved to the decision log."
            className="min-h-20 bg-background/85"
          />
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="font-sans text-xs text-muted-foreground">
            {undecided.length > 0
              ? `${undecided.length} claim${undecided.length === 1 ? "" : "s"} still need${undecided.length === 1 ? "s" : ""} a call.`
              : Object.keys(decisions).length === 0
                ? "Pick a verdict on at least one claim to save a check-in."
                : "Ready to save."}
          </p>
          <button
            type="button"
            onClick={() => void handleSubmit()}
            disabled={!canSubmit}
            className="bg-primary px-5 py-2.5 font-mono text-[10px] uppercase tracking-[0.18em] text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-40"
          >
            {submitting ? "Recording…" : "Record decision"}
          </button>
        </div>
      </div>}
    </div>
  );
}
