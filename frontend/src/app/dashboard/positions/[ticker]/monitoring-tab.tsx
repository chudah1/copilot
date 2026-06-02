"use client";

import { EventReviewStack } from "@/components/monitoring/event-review-stack";
import { EventTimeline } from "@/components/monitoring/event-timeline";
import type { MonitoringEvent } from "@/types";
import type { getMonitoringCalmState } from "./position-helpers";

type ReviewAction = "reaffirmed" | "ignored" | "lowered_confidence" | "invalidated" | "not_relevant";

interface MonitoringTabProps {
  hasThesis: boolean;
  investorProfile: "thesis_driven" | "hearsay_driven" | null;
  events: MonitoringEvent[];
  unreviewedEvents: number;
  firstPendingEvent: MonitoringEvent | null;
  firstPendingAssumptionLabel: string | null;
  isFirstLiveEvidenceMoment: boolean;
  calmState: ReturnType<typeof getMonitoringCalmState>;
  reviewingEventId: string | null;
  decompositionLoading: boolean;
  emptyCopy: { title: string; body: string; cta: string };
  onReview: (event: MonitoringEvent, action: ReviewAction, notes?: string) => Promise<void>;
  onWriteThesis: () => void;
}

export function MonitoringTab({
  hasThesis, investorProfile, events, unreviewedEvents, firstPendingEvent,
  firstPendingAssumptionLabel, isFirstLiveEvidenceMoment, calmState, reviewingEventId,
  decompositionLoading, emptyCopy, onReview, onWriteThesis,
}: MonitoringTabProps) {
  return (
              <div className="space-y-10">

                {/* No thesis guard */}
                {!hasThesis ? (
                  <div className="py-16 text-center space-y-4">
                    <p className="font-display italic text-2xl text-foreground/50">
                      {emptyCopy.title}
                    </p>
                    <p className="font-sans text-sm text-muted-foreground max-w-xs mx-auto leading-relaxed">
                      {emptyCopy.body}
                    </p>
                    <button
                      onClick={onWriteThesis}
                      className="font-mono text-[10px] uppercase tracking-[0.2em] border border-primary/40 text-primary px-5 py-2.5 hover:border-primary transition-colors"
                    >
                      {emptyCopy.cta}
                    </button>
                  </div>
                ) : (
                  <>
                    {/* ── DECISION SECTION ────────────────────────────── */}
                    <section>
                      {unreviewedEvents > 0 ? (
                        <div className="space-y-5">
                          {isFirstLiveEvidenceMoment && firstPendingEvent && (
                            <div className="border border-primary/20 bg-primary/5 px-5 py-4 space-y-3">
                              <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-primary">
                                ● First live evidence
                              </p>
                              {firstPendingAssumptionLabel && (
                                <div className="space-y-1">
                                  <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-foreground/55">
                                    Assumption under test
                                  </p>
                                  <p className="font-sans text-sm text-foreground">
                                    {firstPendingAssumptionLabel}
                                  </p>
                                </div>
                              )}
                              <div className="space-y-1.5">
                                <p className="font-display italic text-[1.35rem] leading-tight text-foreground">
                                  {investorProfile === "hearsay_driven"
                                    ? "This is the first real test of the reason you wrote down."
                                    : "This is the first real test of the thesis you wrote down."}
                                </p>
                                <p className="font-sans text-sm text-foreground/80 leading-relaxed">
                                  {firstPendingEvent.ai_analysis ||
                                    firstPendingEvent.evidence_summary ||
                                    firstPendingEvent.summary ||
                                    (investorProfile === "hearsay_driven"
                                      ? "First alert that may matter for the story. Decide what it means before you move on."
                                      : "First alert that may matter for the thesis. Decide what it means before you move on.")}
                                </p>
                              </div>
                            </div>
                          )}

                          {/* Decisions pending header */}
                          <div className="flex items-baseline justify-between gap-4">
                            <div>
                              <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground mb-1">
                                Decisions pending
                              </p>
                              <p className="font-display italic text-[1.6rem] leading-tight text-foreground">
                                {investorProfile === "thesis_driven"
                                  ? (unreviewedEvents === 1
                                      ? "One thesis signal needs your verdict."
                                      : `${unreviewedEvents} thesis signals need your verdict.`)
                                  : investorProfile === "hearsay_driven"
                                    ? (unreviewedEvents === 1
                                        ? "One change to your reason needs a decision."
                                        : `${unreviewedEvents} changes to your reason need decisions.`)
                                    : (unreviewedEvents === 1
                                        ? "One signal needs your verdict."
                                        : `${unreviewedEvents} signals need your verdict.`)}
                              </p>
                            </div>
                            <span className="font-mono text-[10px] text-muted-foreground/70 shrink-0 self-end pb-0.5">
                              drag to decide
                            </span>
                          </div>

                          {/* Card stack */}
                          <EventReviewStack
                            events={events.filter((e) => !e.review_action)}
                            onReview={onReview}
                            reviewingEventId={reviewingEventId}
                            investorProfile={investorProfile ?? null}
                          />
                        </div>
                      ) : (
                        /* Position clear */
                        <div className="space-y-4 py-6 border-l-[3px] border-emerald-500/40 pl-6">
                          <div className="space-y-1">
                            <p className="font-display italic text-[1.6rem] leading-tight text-foreground">
                              {calmState.title}
                            </p>
                            <p className="font-sans text-sm text-muted-foreground leading-relaxed">
                              {calmState.body}
                            </p>
                            <p className="font-sans text-sm text-foreground/85 leading-relaxed">
                              {calmState.nextCheck}
                            </p>
                          </div>

                          {calmState.previewItems.length > 0 && (
                            <div className="grid gap-2 sm:grid-cols-2 max-w-3xl">
                              {calmState.previewItems.map((item) => (
                                <div key={item.key} className="border border-emerald-600/10 bg-card px-3 py-2.5">
                                  <p className="font-sans text-sm text-foreground">{item.label}</p>
                                  <p className="font-sans text-xs text-muted-foreground mt-1 leading-relaxed">{item.detail}</p>
                                </div>
                              ))}
                            </div>
                          )}

                          {calmState.previewItems.length === 0 && calmState.fallbackHints.length > 0 && (
                            <div className="flex flex-wrap gap-2">
                              {calmState.fallbackHints.map((hint) => (
                                <span key={hint} className="font-sans text-xs text-foreground/70 border border-border/60 bg-card px-3 py-1">
                                  {hint}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                      )}
                    </section>

                    {/* ── EVIDENCE SECTION ────────────────────────────── */}
                    {events.some((e) => e.review_action) && (
                      <section className="border-t border-border/40 pt-8 space-y-4">
                        <div>
                          <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground mb-0.5">
                            Evidence on file
                          </p>
                          <p className="font-sans text-xs text-muted-foreground/70">
                            Reviewed events and your verdicts
                          </p>
                        </div>
                        <EventTimeline
                          events={events.filter((e) => e.review_action)}
                          reviewingEventId={reviewingEventId}
                          investorProfile={investorProfile ?? null}
                        />
                      </section>
                    )}

                    {/* No events at all */}
                    {events.length === 0 && !decompositionLoading && (
                      <div className="border border-border/50 bg-card/60 px-4 py-3 space-y-2">
                        <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                          Quiet state
                        </p>
                        <p className="font-sans text-sm text-muted-foreground/80 leading-relaxed">
                          {investorProfile === "thesis_driven"
                            ? "Monitoring is active. No thesis-level change is worth a decision yet."
                            : investorProfile === "hearsay_driven"
                              ? "Monitoring is active. Nothing has tested the reason strongly enough to force a decision yet."
                              : "Monitoring is active. Nothing meaningful has changed yet."}
                        </p>
                        <p className="font-sans text-xs text-foreground/80">
                          {calmState.nextCheck}
                        </p>
                      </div>
                    )}
                  </>
                )}
              </div>
  );
}
