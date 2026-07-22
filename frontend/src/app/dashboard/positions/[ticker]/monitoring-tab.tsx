"use client";

import { EventTimeline } from "@/components/monitoring/event-timeline";
import { HeldUpThisWeek } from "@/components/monitoring/held-up-this-week";
import { ReviewedThisWeek } from "@/components/monitoring/reviewed-this-week";
import { ThesisCheckIn } from "@/components/thesis/thesis-check-in";
import { InfoTip } from "@/components/ui/info-tip";
import type { MonitoringEvent, ReviewedItem, SubmitClaimReviewsResponse, SupportingItem } from "@/types";
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
  onAfterCheckIn: (result: SubmitClaimReviewsResponse, thesisAction: "keep_lowered" | "rewrite" | "invalidate" | null) => Promise<void> | void;
  onWriteThesis: () => void;
}

export function MonitoringTab({
  hasThesis, thesisId, ticker, writtenCase, investorProfile, events, unreviewedEvents, activeSignalCount, hasSignals, calmState,
  decompositionLoading, emptyCopy, reviewedItems, supportingItems, onFlagEvent, onAfterCheckIn, onWriteThesis,
}: MonitoringTabProps) {
  const reviewedEventsCount = events.filter((event) => Boolean(event.review_action)).length;
  const monitoringCopy = investorProfile === "hearsay_driven"
    ? {
        title: "Write the reason first.",
        body:
          "Monitoring turns on once this position has a written reason.",
        unlocks: [
          "Tie signals to the story.",
          "Queue evidence for a verdict.",
          "Ignore noise when nothing changed.",
        ],
        controlTitle: "Monitoring",
        controlBody: "New evidence gets matched to the written reason here.",
      }
    : {
        title: "Write the thesis first.",
        body:
          "Monitoring turns on once this position has a written thesis.",
        unlocks: [
          "Tie signals to assumptions.",
          "Keep a verdict trail.",
          "Stay quiet until the thesis moves.",
        ],
        controlTitle: "Monitoring",
        controlBody: "Live evidence gets mapped back to the written thesis here.",
      };

  return (
    <div className="space-y-10">
      {!hasThesis ? (
        <div className="grid gap-5 lg:grid-cols-[minmax(0,1.2fr)_minmax(16rem,20rem)]">
          <section className="product-panel product-panel-muted overflow-hidden p-5 sm:p-6">
            <div className="space-y-5">
              <div className="space-y-2">
                <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-primary">
                  Locked
                </p>
                <div className="space-y-2">
                  <p className="font-display italic text-[1.6rem] leading-tight text-foreground sm:text-[1.85rem]">
                    {monitoringCopy.title}
                  </p>
                  <p className="max-w-2xl font-sans text-sm leading-relaxed text-foreground/80">
                    {monitoringCopy.body}
                  </p>
                </div>
              </div>

              <div className="grid gap-3 sm:grid-cols-3">
                {monitoringCopy.unlocks.map((item) => (
                  <div key={item} className="border border-border/70 bg-background/75 p-4">
                    <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                      Use
                    </p>
                    <p className="mt-2 font-sans text-sm leading-relaxed text-foreground/85">
                      {item}
                    </p>
                  </div>
                ))}
              </div>

              <div className="flex flex-wrap items-center gap-3">
                <button
                  onClick={onWriteThesis}
                  className="bg-primary px-5 py-2.5 font-mono text-[10px] uppercase tracking-[0.18em] text-primary-foreground transition-colors hover:bg-primary/90"
                >
                  {emptyCopy.cta}
                </button>
                <p className="font-sans text-xs leading-relaxed text-muted-foreground">
                  A short draft is enough.
                </p>
              </div>
            </div>
          </section>

          <aside className="product-panel p-5 sm:p-6">
            <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
              What you get
            </p>
            <div className="mt-4 space-y-3">
              {monitoringCopy.unlocks.map((item) => (
                <div key={item} className="border-l-2 border-primary/20 pl-3">
                  <p className="font-sans text-sm leading-relaxed text-foreground/80">
                    {item}
                  </p>
                </div>
              ))}
            </div>
          </aside>
        </div>
      ) : (
        <>
          <section className="grid gap-4 lg:grid-cols-[minmax(0,1.2fr)_minmax(16rem,20rem)]">
            <div className="product-panel product-panel-muted self-start p-5 sm:p-6">
              <div className="space-y-2">
                <div className="flex items-center gap-1.5">
                  <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-primary">
                    {monitoringCopy.controlTitle}
                  </p>
                  <InfoTip label="Monitoring">
                    PenKeep checks new evidence against why you own the position, what must remain true, and what would break the case.
                  </InfoTip>
                </div>
                <p className="font-display italic text-[1.55rem] leading-tight text-foreground sm:text-[1.75rem]">
                  {unreviewedEvents > 0
                    ? "New evidence has been checked."
                    : calmState.title}
                </p>
                <p className="font-sans text-sm leading-relaxed text-foreground/80">
                  {unreviewedEvents > 0
                    ? "Only evidence that puts real pressure on your written case will ask for a decision."
                    : calmState.body}
                </p>
              </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-1">
              <div className="product-panel p-4">
                <div className="flex items-center gap-1.5">
                  <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                    New evidence
                  </p>
                  <InfoTip label="New evidence">
                    Items checked since your last recorded decision. This count can be higher than the number of decisions needed.
                  </InfoTip>
                </div>
                <p className="mt-2 font-display text-[1.55rem] italic leading-none text-foreground">
                  {unreviewedEvents}
                </p>
                <p className="mt-2 font-sans text-xs leading-relaxed text-muted-foreground">
                  {unreviewedEvents === 1 ? "1 item checked since your last decision" : `${unreviewedEvents} items checked since your last decision`}
                </p>
              </div>

              <div className="product-panel p-4">
                <div className="flex items-center gap-1.5">
                  <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                    Reviewed
                  </p>
                  <InfoTip label="Reviewed">
                    Evidence you have already ruled on. The verdict and your response remain in the position history.
                  </InfoTip>
                </div>
                <p className="mt-2 font-display text-[1.55rem] italic leading-none text-foreground">
                  {reviewedEventsCount}
                </p>
                <p className="mt-2 font-sans text-xs leading-relaxed text-muted-foreground">
                  Verdicts on file
                </p>
              </div>

              <div className="product-panel p-4">
                <div className="flex items-center gap-1.5">
                  <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                    Signal map
                  </p>
                  <InfoTip label="Signal map">
                    The measurable checks tied to your written case, such as revenue growth, guidance, customer demand, or a price move. A signal is not a recommendation.
                  </InfoTip>
                </div>
                <p className="mt-2 font-display text-[1.55rem] italic leading-none text-foreground">
                  {decompositionLoading ? "..." : hasSignals ? activeSignalCount : "0"}
                </p>
                <p className="mt-2 font-sans text-xs leading-relaxed text-muted-foreground">
                  {decompositionLoading
                    ? "Updating signal map"
                    : hasSignals
                      ? "Signals live"
                      : "No live signals yet"}
                </p>
              </div>
            </div>
          </section>

          {/* ── DECISION SECTION ────────────────────────────── */}
          <section>
            {unreviewedEvents > 0 ? (
              <div className="space-y-5">
                {thesisId && (
                  <ThesisCheckIn
                    thesisId={thesisId}
                    ticker={ticker}
                    writtenCase={writtenCase}
                    onFlagEvent={onFlagEvent}
                    onAfterSubmit={onAfterCheckIn}
                  />
                )}
              </div>
            ) : (
              <div className="grid gap-5 lg:grid-cols-[minmax(0,1.2fr)_minmax(16rem,20rem)]">
                <section className="product-panel product-panel-muted p-5 sm:p-6">
                  <div className="space-y-4">
                    <div className="space-y-2">
                      <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-emerald-700">
                        Active
                      </p>
                      <p className="font-display italic text-[1.6rem] leading-tight text-foreground">
                        {calmState.title}
                      </p>
                      <p className="font-sans text-sm leading-relaxed text-foreground/80">
                        {calmState.body}
                      </p>
                    </div>

                    <div className="border border-emerald-600/15 bg-background/70 px-4 py-3">
                      <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                        Next check
                      </p>
                      <p className="mt-2 font-sans text-sm leading-relaxed text-foreground/85">
                        {calmState.nextCheck}
                      </p>
                    </div>

                    {calmState.previewItems.length > 0 && (
                      <div className="grid gap-2 sm:grid-cols-2">
                        {calmState.previewItems.map((item) => (
                          <div key={item.key} className="border border-emerald-600/10 bg-background/75 px-3 py-2.5">
                            <p className="font-sans text-sm text-foreground">{item.label}</p>
                            <p className="mt-1 font-sans text-xs leading-relaxed text-muted-foreground">{item.detail}</p>
                          </div>
                        ))}
                      </div>
                    )}

                    {calmState.previewItems.length === 0 && calmState.fallbackHints.length > 0 && (
                      <div className="flex flex-wrap gap-2">
                        {calmState.fallbackHints.map((hint) => (
                          <span key={hint} className="border border-border/60 bg-background/70 px-3 py-1 font-sans text-xs text-foreground/70">
                            {hint}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </section>

                <aside className="product-panel p-5 sm:p-6">
                  <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                    Status
                  </p>
                  <div className="mt-4 space-y-3">
                    <div className="border-l-2 border-primary/20 pl-3">
                      <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                        Queue
                      </p>
                      <p className="mt-1 font-sans text-sm leading-relaxed text-foreground/80">
                        Nothing waiting.
                      </p>
                    </div>
                    <div className="border-l-2 border-primary/20 pl-3">
                      <div className="flex items-center gap-1.5">
                        <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                          Signals live
                        </p>
                        <InfoTip label="Signals live">
                          Active checks currently being monitored against this position&apos;s written case.
                        </InfoTip>
                      </div>
                      <p className="mt-1 font-sans text-sm leading-relaxed text-foreground/80">
                        {decompositionLoading
                          ? "Still building the map."
                          : hasSignals
                            ? `${activeSignalCount} active signal${activeSignalCount === 1 ? "" : "s"}.`
                            : "The thesis is written, but the map still needs confirmation."}
                      </p>
                    </div>
                    <div className="border-l-2 border-primary/20 pl-3">
                      <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                        Reviewed
                      </p>
                      <p className="mt-1 font-sans text-sm leading-relaxed text-foreground/80">
                        {reviewedEventsCount > 0
                          ? `${reviewedEventsCount} verdict${reviewedEventsCount === 1 ? "" : "s"} on file.`
                          : "No verdicts yet."}
                      </p>
                    </div>
                  </div>
                </aside>
              </div>
            )}
          </section>

          {events.some((e) => e.review_action) && (
            <section className="border-t border-border/40 pt-8 space-y-4">
              <div>
                <p className="mb-0.5 font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                  History
                </p>
                <p className="font-sans text-xs text-muted-foreground/70">
                  Reviewed events on file
                </p>
              </div>
              <EventTimeline
                events={events.filter((e) => e.review_action)}
                investorProfile={investorProfile ?? null}
              />
            </section>
          )}

          {events.length === 0 && !decompositionLoading && unreviewedEvents === 0 && (
            <div className="border border-border/50 bg-card/60 px-4 py-3 space-y-2">
              <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                Quiet state
              </p>
              <p className="font-sans text-sm text-muted-foreground/80 leading-relaxed">
                {investorProfile === "thesis_driven"
                  ? "Monitoring is live. Nothing has forced a decision yet."
                  : investorProfile === "hearsay_driven"
                    ? "Monitoring is live. Nothing has tested the reason enough to force a decision yet."
                    : "Monitoring is live. Nothing meaningful has changed yet."}
              </p>
              <p className="font-sans text-xs text-foreground/80">
                {calmState.nextCheck}
              </p>
            </div>
          )}

          {/* Supporting evidence — signals the pipeline judged as validating
              the thesis rather than threatening it. Rendered above the
              adjacency block so a positive read lands first when both are
              present; users should sometimes feel "my thesis was
              validated" rather than only "my thesis is under attack." */}
          {supportingItems.length > 0 && <HeldUpThisWeek items={supportingItems} />}

          {/* Adjacency evidence — the "we looked at these edge cases for you"
              receipt. Quiet state is where users most want proof of
              watchfulness, but the block reads as reassurance under alerts
              too, so we show it whenever items exist. */}
          {reviewedItems.length > 0 && <ReviewedThisWeek items={reviewedItems} />}
        </>
      )}
    </div>
  );
}
