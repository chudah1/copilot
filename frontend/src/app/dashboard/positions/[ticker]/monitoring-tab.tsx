"use client";

import { HeldUpThisWeek } from "@/components/monitoring/held-up-this-week";
import { ReviewedThisWeek } from "@/components/monitoring/reviewed-this-week";
import { ThesisCheckIn } from "@/components/thesis/thesis-check-in";
import { InfoTip } from "@/components/ui/info-tip";
import type {
  MonitoringEvent,
  ReviewedItem,
  SubmitClaimReviewsResponse,
  SupportingItem,
} from "@/types";
import type { getMonitoringCalmState } from "./position-helpers";

interface MonitoringTabProps {
  hasThesis: boolean;
  thesisId: string | null;
  ticker: string;
  writtenCase: {
    whyOwnIt: string;
    stillTrueIf: string | null;
    breaksIf: string | null;
  };
  investorProfile: "thesis_driven" | "hearsay_driven" | null;
  events: MonitoringEvent[];
  pendingDecisionCount: number;
  activeSignalCount: number;
  hasSignals: boolean;
  calmState: ReturnType<typeof getMonitoringCalmState>;
  decompositionLoading: boolean;
  emptyCopy: { title: string; body: string; cta: string };
  reviewedItems: ReviewedItem[];
  supportingItems: SupportingItem[];
  onFlagEvent: (eventId: string) => Promise<void>;
  onAfterCheckIn: (
    result: SubmitClaimReviewsResponse,
    thesisAction: "keep_lowered" | "rewrite" | "invalidate" | null,
  ) => Promise<void> | void;
  onWriteThesis: () => void;
}

export function MonitoringTab({
  hasThesis,
  thesisId,
  ticker,
  writtenCase,
  investorProfile,
  events,
  pendingDecisionCount,
  activeSignalCount,
  hasSignals,
  calmState,
  decompositionLoading,
  emptyCopy,
  reviewedItems,
  supportingItems,
  onFlagEvent,
  onAfterCheckIn,
  onWriteThesis,
}: MonitoringTabProps) {
  if (!hasThesis) {
    return (
      <section className="product-panel border border-border/70 bg-[linear-gradient(180deg,rgba(163,126,79,0.05),rgba(255,255,255,0.96))] p-5 sm:p-6">
        <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-primary">
          Set up monitoring
        </p>
        <h2 className="mt-2 font-display italic text-[1.6rem] leading-tight text-foreground sm:text-[1.85rem]">
          {emptyCopy.title}
        </h2>
        <p className="mt-2 max-w-2xl font-sans text-sm leading-relaxed text-foreground/80">
          {emptyCopy.body}
        </p>
        <button
          onClick={onWriteThesis}
          className="mt-5 bg-primary px-5 py-2.5 font-mono text-[10px] uppercase tracking-[0.18em] text-primary-foreground transition-colors hover:bg-primary/90"
        >
          {emptyCopy.cta}
        </button>
      </section>
    );
  }

  const noDecisionPending = pendingDecisionCount === 0;
  const monitoringStatus = decompositionLoading
    ? "Monitoring checks are updating."
    : hasSignals
      ? `${activeSignalCount} monitoring check${activeSignalCount === 1 ? " is" : "s are"} active.`
      : investorProfile === "thesis_driven"
        ? "The thesis is saved. Confirm the suggested checks to finish setup."
        : investorProfile === "hearsay_driven"
          ? "The reason is saved. Confirm the suggested checks to finish setup."
          : "Your notes are saved. Confirm the suggested checks to finish setup.";

  return (
    <div className="space-y-8">
      {noDecisionPending && <section className="product-panel border border-border/70 bg-[linear-gradient(180deg,rgba(163,126,79,0.05),rgba(255,255,255,0.96))] p-5 sm:p-6">
        <div className="flex items-center gap-1.5">
          <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-primary">
            What changed
          </p>
          <InfoTip label="What changed">
            {investorProfile === "thesis_driven"
              ? "This page shows evidence that supports or challenges something in your thesis. Reviewed items move to the review trail."
              : investorProfile === "hearsay_driven"
                ? "This page shows evidence that supports or challenges something in your reason. Reviewed items move to the review trail."
                : "This page shows evidence that supports or challenges something in your reason. Reviewed items move to the review trail."}
          </InfoTip>
        </div>
        <h2 className="mt-2 font-display italic text-[1.6rem] leading-tight text-foreground sm:text-[1.85rem]">
          Nothing new needs your decision.
        </h2>
        <p className="mt-2 max-w-2xl font-sans text-sm leading-relaxed text-foreground/80">
          {calmState.body}
        </p>
        <div className="mt-4 border-t border-border/60 pt-3">
          <p className="font-sans text-xs leading-relaxed text-muted-foreground">
            {monitoringStatus}
            {` ${calmState.nextCheck}`}
          </p>
        </div>
      </section>}

      {pendingDecisionCount > 0 && thesisId && (
        <ThesisCheckIn
          key={thesisId}
          thesisId={thesisId}
          ticker={ticker}
          investorProfile={investorProfile}
          writtenCase={writtenCase}
          onFlagEvent={onFlagEvent}
          onAfterSubmit={onAfterCheckIn}
          presentation="guided"
        />
      )}

      {/* While a check-in is open, supporting evidence already renders inside
          each claim card — repeating it here showed the same items twice. */}
      {noDecisionPending && supportingItems.length > 0 && (
        <HeldUpThisWeek items={supportingItems} />
      )}

      {noDecisionPending && reviewedItems.length > 0 && (
        <ReviewedThisWeek items={reviewedItems} />
      )}

      {events.length === 0 &&
        !decompositionLoading &&
        supportingItems.length === 0 &&
        reviewedItems.length === 0 && (
          <div className="product-panel border border-border/60 bg-background/72 px-4 py-4">
            <p className="font-sans text-sm leading-relaxed text-muted-foreground">
              {investorProfile === "thesis_driven"
                ? "Nothing public is asking you to revisit this thesis yet."
                : investorProfile === "hearsay_driven"
                  ? "Nothing public is asking you to revisit this reason yet."
                  : "Nothing public is asking you to revisit this reason yet."}
            </p>
          </div>
        )}
    </div>
  );
}
