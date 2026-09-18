"use client";

import { useRef, useState } from "react";
import useSWR from "swr";
import { toast } from "sonner";

import { api, fetcher } from "@/lib/api";
import { Textarea } from "@/components/ui/textarea";
import { InfoTip } from "@/components/ui/info-tip";
import { formatDate } from "@/lib/utils";
import { cleanRichText } from "@/lib/text";
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
  investorProfile: "thesis_driven" | "hearsay_driven" | null;
  writtenCase: {
    whyOwnIt: string;
    stillTrueIf: string | null;
    breaksIf: string | null;
  };
  onFlagEvent: (eventId: string) => Promise<void>;
  onAfterSubmit: (result: SubmitClaimReviewsResponse, thesisAction: ThesisAction | null) => Promise<void> | void;
  presentation?: "standard" | "guided";
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

function decisionCoachCopy(args: {
  investorProfile: "thesis_driven" | "hearsay_driven" | null;
  ticker: string;
  pendingClaims: number;
  anyBroken: boolean;
}) {
  const { investorProfile, ticker, pendingClaims, anyBroken } = args;

  if (anyBroken) {
    if (investorProfile === "hearsay_driven") {
      return {
        eyebrow: "Decision coach",
        body: `The original reason for ${ticker} just lost support. Decide whether you still have a real reason for owning it.`,
      };
    }
    if (investorProfile === "thesis_driven") {
      return {
        eyebrow: "Decision coach",
        body: `Part of the thesis for ${ticker} broke. Choose whether confidence steps down, the thesis gets rewritten, or the position is closed.`,
      };
    }
    return {
      eyebrow: "Decision coach",
      body: `Part of your reason for ${ticker} broke. Decide what changes now while the evidence is still clear.`,
    };
  }

  if (investorProfile === "hearsay_driven") {
    return {
      eyebrow: "Decision coach",
      body: `${pendingClaims === 1 ? "This item is" : "These items are"} where the original idea either becomes a durable reason or starts to break. Answer with what the evidence changed, not with a cleaner narrative.`,
    };
  }
  if (investorProfile === "thesis_driven") {
    return {
      eyebrow: "Decision coach",
      body: `${pendingClaims === 1 ? "This item is" : "These items are"} where the thesis meets fresh evidence. Make the call while the read is fresh so the next decision starts from clarity, not drift.`,
    };
  }
  return {
    eyebrow: "Decision coach",
    body: `${pendingClaims === 1 ? "This item is" : "These items are"} where your reason meets new evidence. Decide now while the facts are clearer than the price reaction.`,
  };
}

function writtenCaseLabel(investorProfile: "thesis_driven" | "hearsay_driven" | null) {
  if (investorProfile === "hearsay_driven") {
    return {
      heading: "Your reason",
      fallback: "Your core reason",
    };
  }
  if (investorProfile === "thesis_driven") {
    return {
      heading: "Your thesis",
      fallback: "Your core thesis",
    };
  }
  return {
    heading: "Your reason",
    fallback: "Your core reason",
  };
}

function EvidenceRow({
  item,
  onFlag,
  flagging,
  removalLabel,
}: {
  item: ClaimEvidenceItem;
  onFlag: (eventId: string) => Promise<void>;
  flagging: boolean;
  removalLabel: string;
}) {
  return (
    <div className="border border-border/60 bg-background/70 px-3 py-2.5">
      {/* Stacks on phones so the evidence text keeps full width */}
      <div className="flex flex-col gap-2.5 sm:flex-row sm:items-start sm:justify-between sm:gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className={`font-mono text-[10px] uppercase tracking-[0.14em] ${SEVERITY_TEXT[item.severity] ?? "text-muted-foreground"}`}>
              {item.event_type.replace(/_/g, " ")}
            </span>
            <span className="font-mono text-[10px] text-muted-foreground/70">{formatDate(item.created_at)}</span>
          </div>
          <p className="mt-1.5 whitespace-pre-line font-sans text-sm leading-relaxed text-foreground/90">
            {cleanRichText(item.summary || item.title)}
          </p>
          {item.ai_analysis && (
            <div className="product-panel mt-2.5 border border-emerald-600/20 bg-emerald-600/[0.05] px-3 py-2">
              <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-emerald-700/80">
                penKeep&apos;s read
              </p>
              <p className="mt-1 whitespace-pre-line font-sans text-xs leading-relaxed text-foreground/75">
                {cleanRichText(item.ai_analysis)}
              </p>
            </div>
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
          className="self-start shrink-0 border border-border/70 bg-background px-2.5 py-1.5 font-sans text-xs text-muted-foreground transition-colors hover:border-foreground/30 hover:text-foreground disabled:cursor-not-allowed disabled:opacity-40"
        >
          {flagging ? "Removing…" : removalLabel}
        </button>
      </div>
    </div>
  );
}

export function ThesisCheckIn({
  thesisId,
  ticker,
  investorProfile,
  writtenCase,
  onFlagEvent,
  onAfterSubmit,
  presentation = "standard",
}: Props) {
  const { data, mutate, isLoading } = useSWR<ThesisCheckInData>(`/api/theses/${thesisId}/check-in`, fetcher);
  const [decisions, setDecisions] = useState<Record<string, ClaimStatus>>({});
  const [notes, setNotes] = useState("");
  const [thesisAction, setThesisAction] = useState<ThesisAction | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const submittingRef = useRef(false);
  const [flaggingId, setFlaggingId] = useState<string | null>(null);
  const [guidedStep, setGuidedStep] = useState<"brief" | "evidence" | "decision">("brief");

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
  const writtenCaseCopy = writtenCaseLabel(investorProfile);
  const coach = decisionCoachCopy({
    investorProfile,
    ticker,
    pendingClaims: pendingClaims.length,
    anyBroken,
  });
  const subjectWord =
    investorProfile === "thesis_driven"
      ? "thesis"
      : investorProfile === "hearsay_driven"
        ? "reason"
        : "reason";
  const possessiveSubject =
    investorProfile === "thesis_driven"
      ? "your thesis"
      : investorProfile === "hearsay_driven"
        ? "your reason"
        : "your reason";
  const removalLabel = "Not relevant";
  const subjectReference = `your ${subjectWord}`;
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
      toast.success("Decision saved.");
      setDecisions({});
      setNotes("");
      setThesisAction(null);
      await mutate();
      setGuidedStep("brief");
      try {
        await onAfterSubmit(result, anyBroken ? thesisAction : null);
      } catch (refreshError) {
        console.error("Decision saved but follow-up refresh failed", refreshError);
        toast.warning("Decision saved. Refresh the page to see the latest status.");
      }
    } catch (error) {
      console.error(error);
      toast.error("Failed to save the decision");
    } finally {
      submittingRef.current = false;
      setSubmitting(false);
    }
  };

  const guided = presentation === "guided";
  const guidedReviewActive = guided && pendingClaims.length > 0;
  const evidenceCount = claims.reduce(
    (total, claim) => total + claim.supports.length + claim.threatens.length + claim.neutral.length,
    0,
  );
  const threateningCount = claims.reduce((total, claim) => total + claim.threatens.length, 0);

  return (
    <div className="space-y-4">
      {guidedReviewActive && (
        <div className="grid grid-cols-3 border border-border/70 bg-card">
          {(
            [
              { id: "brief", number: "1", label: "What needs you" },
              { id: "evidence", number: "2", label: "Review evidence" },
              { id: "decision", number: "3", label: "Make the call" },
            ] as const
          ).map((step) => {
            const active = guidedStep === step.id;
            const unavailable =
              step.id === "decision" &&
              (undecided.length > 0 || Object.keys(decisions).length === 0);
            return (
              <button
                key={step.id}
                type="button"
                onClick={() => setGuidedStep(step.id)}
                disabled={unavailable}
                aria-current={active ? "step" : undefined}
                className={`border-r border-border/70 px-3 py-3 text-left last:border-r-0 disabled:cursor-not-allowed disabled:opacity-45 ${active ? "bg-primary/[0.06]" : "bg-background"}`}
              >
                <span className={`font-mono text-[9px] ${active ? "text-primary" : "text-muted-foreground"}`}>{step.number}</span>
                <span className={`ml-2 font-mono text-[9px] uppercase tracking-[0.12em] ${active ? "text-primary" : "text-muted-foreground"}`}>
                  {step.label}
                </span>
              </button>
            );
          })}
        </div>
      )}

      {guidedReviewActive && guidedStep === "brief" && (
        <section className="border border-amber-500/30 bg-[linear-gradient(145deg,rgba(217,119,6,0.08),rgba(255,255,255,0.9))] p-6 sm:p-9">
          <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-amber-800">Decision needed</p>
          <h2 className="mt-4 max-w-2xl font-display text-3xl italic leading-tight text-foreground sm:text-4xl">
            Does {possessiveSubject} for {ticker} still hold?
          </h2>
          <p className="mt-4 max-w-2xl font-sans text-base leading-relaxed text-foreground/75">
            {threateningCount > 0
              ? `${threateningCount} warning ${threateningCount === 1 ? "update has" : "updates have"} challenged what you asked PenKeep to watch.`
              : `${evidenceCount} new evidence ${evidenceCount === 1 ? "item is" : "items are"} ready for a quick review.`}
            {` ${pendingClaims.length} part${pendingClaims.length === 1 ? "" : "s"} of ${possessiveSubject} ${pendingClaims.length === 1 ? "needs" : "need"} your judgment.`}
          </p>
          <button
            type="button"
            onClick={() => setGuidedStep("evidence")}
            className="mt-7 bg-primary px-5 py-3 font-mono text-[10px] uppercase tracking-[0.18em] text-primary-foreground transition-colors hover:bg-primary/90"
          >
            Review what changed →
          </button>
        </section>
      )}

      {(!guidedReviewActive || guidedStep === "brief") && (
        <div className="space-y-3">
          {!guidedReviewActive && (
            <div>
              <p className="mb-1 font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                {pendingClaims.length > 0 ? "Decision needed" : "Evidence reviewed"}
              </p>
              <p className="font-display italic text-[1.6rem] leading-tight text-foreground">
                {pendingClaims.length > 0
                  ? `Does this change ${possessiveSubject} for ${ticker}?`
                  : hasEvidence
                    ? "No decision needed."
                    : `Nothing is testing ${possessiveSubject} right now.`}
              </p>
              <p className="mt-2 max-w-2xl font-sans text-sm leading-relaxed text-foreground/75">
                {pendingClaims.length > 0
                  ? `Read the evidence, then say whether the part of ${possessiveSubject} below still holds.`
                  : `PenKeep checked the new evidence. It does not currently test ${possessiveSubject} strongly enough to need a decision.`}
              </p>
            </div>
          )}

        <div className={`product-panel border border-border/60 bg-background/72 px-4 py-3 ${guidedReviewActive ? "mt-4" : ""}`}>
          <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">{writtenCaseCopy.heading}</p>
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
      )}

      {(!guidedReviewActive || guidedStep === "evidence") && (
        <div className="space-y-3">
          {pendingClaims.length > 0 && (
            <div className="product-panel border border-primary/15 bg-primary/[0.04] px-4 py-3">
              <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-primary/75">
                {coach.eyebrow}
              </p>
              <p className="mt-2 font-sans text-sm leading-relaxed text-foreground/82">
                {coach.body}
              </p>
            </div>
          )}
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
                {claim.claim_id ? `“${claim.label}”` : writtenCaseCopy.fallback}
              </p>
              {claim.needs_review_reason && (
                <p className="mt-1 font-sans text-xs leading-relaxed text-amber-700/90">{claim.needs_review_reason}</p>
              )}

              {evidenceCount > 0 && (
                <div className="mt-3 space-y-2">
                  {claim.threatens.length > 0 && (
                    <div className="space-y-2">
                      <div className="flex items-center gap-1.5">
                        <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground/80">
                          {claim.needs_review ? "Against" : "Early pressure"} · {claim.threatens.length}
                        </p>
                        <InfoTip label={claim.needs_review ? "Against" : "Early pressure"}>
                          {`Evidence that weakens this part of ${subjectReference}. It only asks for a decision when the pressure is strong enough.`}
                        </InfoTip>
                      </div>
                      {claim.threatens.slice(0, 2).map((item) => (
                        <EvidenceRow key={item.id} item={item} onFlag={handleFlag} flagging={flaggingId === item.id} removalLabel={removalLabel} />
                      ))}
                      {claim.threatens.length > 2 && (
                        <details className="group border border-border/60 bg-background/45 px-3 py-2">
                          <summary className="flex cursor-pointer list-none items-center justify-between gap-3">
                            <span className="font-sans text-xs text-foreground/70">
                              {claim.threatens.length - 2} more challenging update{claim.threatens.length - 2 === 1 ? "" : "s"}
                            </span>
                            <span className="font-mono text-[9px] uppercase tracking-[0.13em] text-muted-foreground group-open:hidden">Show</span>
                            <span className="hidden font-mono text-[9px] uppercase tracking-[0.13em] text-muted-foreground group-open:inline">Hide</span>
                          </summary>
                          <div className="mt-2 space-y-2">
                            {claim.threatens.slice(2).map((item) => (
                              <EvidenceRow key={item.id} item={item} onFlag={handleFlag} flagging={flaggingId === item.id} removalLabel={removalLabel} />
                            ))}
                          </div>
                        </details>
                      )}
                    </div>
                  )}
                  {claim.supports.length > 0 && (
                    <details className="group border-t border-border/50 pt-2">
                      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 py-1">
                        <span className="flex items-center gap-1.5">
                          <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-emerald-700/80">
                            Held up · {claim.supports.length}
                          </span>
                        <InfoTip label="Held up">
                          {`Evidence that supports this part of ${subjectReference}. It stays in the trail but does not require a response.`}
                        </InfoTip>
                        </span>
                        <span className="font-mono text-[9px] uppercase tracking-[0.13em] text-muted-foreground group-open:hidden">Show</span>
                        <span className="hidden font-mono text-[9px] uppercase tracking-[0.13em] text-muted-foreground group-open:inline">Hide</span>
                      </summary>
                      <div className="mt-2 space-y-2">
                        {claim.supports.map((item) => (
                          <EvidenceRow key={item.id} item={item} onFlag={handleFlag} flagging={flaggingId === item.id} removalLabel={removalLabel} />
                        ))}
                      </div>
                    </details>
                  )}
                  {claim.neutral.length > 0 && (
                    <details className="group border-t border-border/50 pt-2">
                      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 py-1">
                        <span className="flex items-center gap-1.5">
                          <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground/80">
                            Background · {claim.neutral.length}
                          </span>
                        <InfoTip label="Background">
                          {`Related evidence that neither supports nor weakens this part of ${subjectReference}. It is kept for context and needs no response.`}
                        </InfoTip>
                        </span>
                        <span className="font-mono text-[9px] uppercase tracking-[0.13em] text-muted-foreground group-open:hidden">Show</span>
                        <span className="hidden font-mono text-[9px] uppercase tracking-[0.13em] text-muted-foreground group-open:inline">Hide</span>
                      </summary>
                      <div className="mt-2 space-y-2">
                        {claim.neutral.map((item) => (
                          <EvidenceRow key={item.id} item={item} onFlag={handleFlag} flagging={flaggingId === item.id} removalLabel={removalLabel} />
                        ))}
                      </div>
                    </details>
                  )}
                </div>
              )}

              {claim.needs_review ? (
                <div className="mt-4 space-y-2">
                  <p className="font-sans text-xs font-medium text-foreground/80">Does this part of {possessiveSubject} still hold?</p>
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
                <p className="mt-3 font-sans text-xs text-muted-foreground">No response needed. This stays in the trail.</p>
              ) : null}
            </div>
          );
        })}
        {guidedReviewActive && (
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border/70 pt-4">
            <button
              type="button"
              onClick={() => setGuidedStep("brief")}
              className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground transition-colors hover:text-foreground"
            >
              ← Back
            </button>
            <div className="flex flex-wrap items-center gap-3">
              {undecided.length > 0 && (
                <p className="font-sans text-xs text-muted-foreground">
                  {undecided.length} part{undecided.length === 1 ? "" : "s"} still need{undecided.length === 1 ? "s" : ""} your answer.
                </p>
              )}
              <button
                type="button"
                onClick={() => setGuidedStep("decision")}
                disabled={undecided.length > 0 || Object.keys(decisions).length === 0}
                className="bg-primary px-5 py-3 font-mono text-[10px] uppercase tracking-[0.18em] text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-40"
              >
                Make the call →
              </button>
            </div>
          </div>
        )}
        </div>
      )}

      {pendingClaims.length > 0 && (!guidedReviewActive || guidedStep === "decision") && <div className="product-panel space-y-4 p-4 sm:p-5">
        {guidedReviewActive && (
          <div className="border-b border-border/60 pb-4">
            <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-primary">Your decision</p>
            <p className="mt-2 font-display text-2xl italic leading-tight text-foreground">
              Record what the evidence changed.
            </p>
            <p className="mt-2 font-sans text-sm leading-relaxed text-foreground/70">
              You reviewed {pendingClaims.length} part{pendingClaims.length === 1 ? "" : "s"} of {possessiveSubject}. This decision will be saved to the history for {ticker}.
            </p>
          </div>
        )}
        {anyBroken && (
          <div className="space-y-2">
            <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-red-700">
              Part of {possessiveSubject} broke — what happens now?
            </p>
            <p className="font-sans text-sm leading-relaxed text-foreground/78">
              {investorProfile === "hearsay_driven"
                ? "Choose the outcome that matches reality, not the one that preserves the original idea."
                : investorProfile === "thesis_driven"
                  ? "Choose the outcome that matches the evidence, even if it means rewriting or closing the thesis."
                  : "Choose the outcome that matches the evidence, not the hope you had before it arrived."}
            </p>
            <div className="grid gap-2 sm:grid-cols-3">
              {(
                [
                  { value: "keep_lowered", label: "Keep, less sure", detail: "Conviction steps down; monitoring continues." },
                  { value: "rewrite", label: `Rewrite the ${subjectWord}`, detail: "Update what must be true before monitoring continues." },
                  { value: "invalidate", label: `Mark the ${subjectWord} broken`, detail: "Close it and save why." },
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
            placeholder="Optional. Saved to the decision trail."
            className="min-h-20 bg-background/85"
          />
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3">
          {guidedReviewActive && (
            <button
              type="button"
              onClick={() => setGuidedStep("evidence")}
              className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground transition-colors hover:text-foreground"
            >
              ← Back to evidence
            </button>
          )}
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
            {submitting ? "Recording…" : "Save decision"}
          </button>
        </div>
      </div>}
    </div>
  );
}
