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
  unreviewedEvents: number;
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
  unreviewedEvents,
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
      <section className="product-panel product-panel-muted p-5 sm:p-6">
        <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-primary">
          Monitoring is off
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

  const noCurrentEvidence = unreviewedEvents === 0;
  const monitoringStatus = decompositionLoading
    ? "Monitoring checks are being updated."
    : hasSignals
      ? `${activeSignalCount} monitoring check${activeSignalCount === 1 ? " is" : "s are"} active.`
      : "The written case is saved, but its monitoring checks still need confirmation.";

  return (
    <div className="space-y-8">
      <section className="product-panel product-panel-muted p-5 sm:p-6">
        <div className="flex items-center gap-1.5">
          <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-primary">
            What changed
          </p>
          <InfoTip label="What changed">
            This page shows evidence that supports or challenges something in your written case. Evidence already reviewed stays in History.
          </InfoTip>
        </div>
        <h2 className="mt-2 font-display italic text-[1.6rem] leading-tight text-foreground sm:text-[1.85rem]">
          {noCurrentEvidence
            ? "No new evidence needs a decision."
            : `${unreviewedEvents} evidence item${unreviewedEvents === 1 ? "" : "s"} need your review.`}
        </h2>
        <p className="mt-2 max-w-2xl font-sans text-sm leading-relaxed text-foreground/80">
          {noCurrentEvidence
            ? calmState.body
            : "Each item below shows the part of your written case it affects. You decide whether the reason still holds."}
        </p>
        <div className="mt-4 border-t border-border/60 pt-3">
          <p className="font-sans text-xs leading-relaxed text-muted-foreground">
            {monitoringStatus}
            {noCurrentEvidence ? ` ${calmState.nextCheck}` : ""}
          </p>
        </div>
      </section>

      {unreviewedEvents > 0 && thesisId && (
        <ThesisCheckIn
          thesisId={thesisId}
          ticker={ticker}
          writtenCase={writtenCase}
          onFlagEvent={onFlagEvent}
          onAfterSubmit={onAfterCheckIn}
        />
      )}

      {/* While a check-in is open, supporting evidence already renders inside
          each claim card — repeating it here showed the same items twice. */}
      {unreviewedEvents === 0 && supportingItems.length > 0 && (
        <HeldUpThisWeek items={supportingItems} />
      )}

      {reviewedItems.length > 0 && <ReviewedThisWeek items={reviewedItems} />}

      {events.length === 0 &&
        !decompositionLoading &&
        supportingItems.length === 0 &&
        reviewedItems.length === 0 && (
          <div className="border border-border/50 bg-card/60 px-4 py-3">
            <p className="font-sans text-sm leading-relaxed text-muted-foreground">
              {investorProfile === "thesis_driven"
                ? "Monitoring is active. No public evidence has tested the written case yet."
                : "Monitoring is active. No public evidence has tested the written reason yet."}
            </p>
          </div>
        )}
    </div>
  );
}
