"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { InfoTip } from "@/components/ui/info-tip";
import { formatDate } from "@/lib/utils";
import type { MonitoringEvent } from "@/types";

type ReviewAction = "reaffirmed" | "ignored" | "lowered_confidence" | "invalidated" | "not_relevant";

interface Props {
  events: MonitoringEvent[];
  onReview?: (event: MonitoringEvent, action: ReviewAction, notes?: string) => Promise<void>;
  onEditReason?: (event: MonitoringEvent) => void;
  reviewingEventId?: string | null;
  investorProfile?: "thesis_driven" | "hearsay_driven" | null;
}

const severityColors: Record<string, string> = {
  info: "bg-blue-500/15 text-blue-700",
  warning: "bg-orange-500/15 text-orange-600",
  thesis_breaking: "bg-red-500/15 text-red-600",
};

function verdictConfig(
  verdict: string,
  investorProfile?: "thesis_driven" | "hearsay_driven" | null,
): { label: string; sentence: string; className: string } | null {
  const subject = investorProfile === "thesis_driven"
    ? "thesis"
    : investorProfile === "hearsay_driven"
      ? "reason"
      : "reason";

  const configs: Record<string, { label: string; sentence: string; className: string }> = {
    supports: {
      label: "Supports",
      sentence: `This evidence supports your ${subject}.`,
      className: "bg-emerald-500/15 text-emerald-700",
    },
    threatens: {
      label: "Threatens",
      sentence: `This evidence threatens your ${subject}.`,
      className: "bg-red-500/15 text-red-600",
    },
    review: {
      label: "Review",
      sentence: `This evidence warrants a closer look at your ${subject}.`,
      className: "bg-amber-500/15 text-amber-700",
    },
    neutral: {
      label: "Neutral",
      sentence: `This evidence is neutral. It does not directly affect your ${subject}.`,
      className: "bg-muted text-muted-foreground",
    },
  };

  return configs[verdict] ?? null;
}

const reviewLabel: Record<string, string> = {
  reaffirmed: "Reaffirmed",
  ignored: "Ignored",
  lowered_confidence: "Lowered confidence",
  invalidated: "Invalidated",
  not_relevant: "Not relevant",
};

function reviewDecisionConfig(
  action: ReviewAction,
  investorProfile?: "thesis_driven" | "hearsay_driven" | null,
): { label: string; sentence: string; className: string } {
  const subject = investorProfile === "thesis_driven"
    ? "thesis"
    : investorProfile === "hearsay_driven"
      ? "reason"
      : "reason";

  switch (action) {
    case "reaffirmed":
      return {
        label: "Reaffirmed",
        sentence: `You said this does not break the ${subject}.`,
        className: "bg-emerald-500/15 text-emerald-700",
      };
    case "lowered_confidence":
      return {
        label: "Less sure",
        sentence: `You marked this as weakening the ${subject}, but not breaking it.`,
        className: "bg-amber-500/15 text-amber-700",
      };
    case "invalidated":
      return {
        label: "Broken",
        sentence: `You marked this as breaking the ${subject}.`,
        className: "bg-red-500/15 text-red-600",
      };
    case "ignored":
      return {
        label: "Ignored",
        sentence: "You chose to ignore this signal for now.",
        className: "bg-muted text-muted-foreground",
      };
    case "not_relevant":
      return {
        label: "Not relevant",
        sentence: `You marked this as not relevant to your ${subject}.`,
        className: "bg-muted text-muted-foreground",
      };
  }
}

function reviewLanguage(investorProfile?: "thesis_driven" | "hearsay_driven" | null) {
  if (investorProfile === "thesis_driven") {
    return {
      empty: "Nothing has tested this position yet. We're still watching it against your thesis.",
      title: "What does this do to your thesis?",
      description: "Save what you decided so the decision trail stays clear.",
      hold: "Thesis still holds",
      edit: "Update thesis",
      lower: "Assumption weaker",
      broken: "Thesis is broken",
      irrelevant: "Not relevant",
    };
  }

  if (investorProfile === "hearsay_driven") {
    return {
      empty: "Nothing has tested this position yet. We're still checking whether your reason still holds.",
      title: "What does this do to your reason?",
      description: "Save whether this changes the reason or simply clarifies it.",
      hold: "Reason still holds",
      edit: "Rewrite the reason",
      lower: "Less sure now",
      broken: "Reason is broken",
      irrelevant: "Not relevant",
    };
  }

  return {
    empty: "Nothing has tested this position yet. We're still watching it against your reason.",
    title: "What do you want to do?",
    description: "Save what you decided so future alerts stay useful.",
    hold: "Reason still holds",
    edit: "Update my reason",
    lower: "Lower confidence",
    broken: "Reason is broken",
    irrelevant: "Not relevant",
  };
}

function parseNarrative(text: string) {
  const normalizedText = text.replace(/\\n/g, "\n");
  const structuredKeys = new Set([
    "Your thesis",
    "You said",
    "Your reason",
    "We were watching",
    "What the app was checking",
    "We watched",
    "What changed",
    "What happened",
    "Why this matters now",
    "Why it matters now",
    "Next step",
    "Verdict",
  ]);
  const parsed: Record<string, string> = {};
  const body: string[] = [];
  for (const line of normalizedText.split("\n")) {
    const colonIdx = line.indexOf(":");
    if (colonIdx > 0 && colonIdx < 24) {
      const key = line.slice(0, colonIdx).trim();
      const value = line.slice(colonIdx + 1).trim();
      if (value && structuredKeys.has(key)) {
        parsed[key] = value;
        continue;
      }
    }
    if (line.trim()) body.push(line.trim());
  }
  if (body[0]) parsed._body0 = body[0];
  if (body[1]) parsed._body1 = body[1];
  return parsed;
}

function eventNarrativeFields(event: MonitoringEvent) {
  const narrative = event.evidence_summary ? parseNarrative(event.evidence_summary) : {};
  return {
    youSaid: narrative["Your thesis"] ?? narrative["You said"] ?? narrative["Your reason"] ?? null,
    weWatched: narrative["We were watching"] ?? narrative["What the app was checking"] ?? narrative["We watched"] ?? event.signal_label ?? null,
    whatChanged: narrative["What changed"] ?? narrative["What happened"] ?? narrative._body0 ?? event.summary,
    whyItMatters: narrative["Why it matters now"] ?? narrative["Why this matters now"] ?? narrative._body1 ?? event.ai_analysis ?? null,
    rawNarrative: narrative,
  };
}

function EvidenceNarrative({ text }: { text: string }) {
  const narrative = parseNarrative(text);
  // "You said" and "We watched" are shown in the card header, skip them here
  const items = [
    ["What happened", narrative["What changed"] ?? narrative["What happened"]],
    ["Why it matters", narrative["Why it matters now"]],
    ["Verdict", narrative["Verdict"]],
  ].filter((item): item is [string, string] => Boolean(item[1]));

  if (items.length === 0) {
    return <p className="mt-2 whitespace-pre-line text-sm text-foreground/80">{text.replace(/\\n/g, "\n")}</p>;
  }

  return (
    <div className="mt-2 space-y-1 text-sm">
      {items.map(([label, value]) => (
        <p key={label}>
          <span className="font-medium text-muted-foreground">{label}:</span>{" "}
          <span className="text-foreground/90">{value}</span>
        </p>
      ))}
    </div>
  );
}

export function EventTimeline({ events, onReview, onEditReason, reviewingEventId, investorProfile }: Props) {
  const [notesByEvent, setNotesByEvent] = useState<Record<string, string>>({});
  const copy = reviewLanguage(investorProfile);
  const reviewedCount = events.filter((event) => Boolean(event.review_action)).length;

  if (events.length === 0) {
    return (
      <div className="product-panel p-5 sm:p-6">
        <div className="space-y-2">
          <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
            Review trail
          </p>
          <p className="font-display italic text-[1.35rem] leading-tight text-foreground">
            Nothing reviewed yet.
          </p>
          <p className="text-foreground/85">{copy.empty}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="product-panel overflow-hidden">
      <div className="grid gap-0 border-b border-border/50 lg:grid-cols-[minmax(0,1.2fr)_minmax(16rem,20rem)]">
        <div className="p-5 sm:p-6">
          <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
            Review trail
          </p>
          <p className="mt-2 font-display italic text-[1.55rem] leading-tight text-foreground">
            What has been tested so far
          </p>
          <p className="mt-2 max-w-2xl font-sans text-sm leading-relaxed text-foreground/80">
            See what was tested, how you ruled, and what changed.
          </p>
        </div>
        <aside className="border-t border-border/50 bg-background/82 p-5 sm:p-6 lg:border-t-0">
          <div className="product-panel border border-border/60 bg-background/72 px-4 py-4">
            <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
              Reviewed so far
            </p>
            <p className="mt-2 font-display text-[1.7rem] italic leading-none text-foreground">
              {reviewedCount}
            </p>
            <p className="mt-2 font-sans text-xs leading-relaxed text-muted-foreground">
              Reviewed event{reviewedCount === 1 ? "" : "s"} saved in the trail for this position.
            </p>
          </div>
        </aside>
      </div>

      <div className="space-y-4 p-5 sm:p-6">
        {events.map((e) => {
          const verdict = e.verdict ? verdictConfig(e.verdict, investorProfile) : null;
          const reviewDecision = e.review_action ? reviewDecisionConfig(e.review_action, investorProfile) : null;
          const narrative = eventNarrativeFields(e);
          const youSaid = narrative.youSaid;
          const weWatched = narrative.weWatched;

          return (
            <div key={e.id} className="border border-border/70 bg-background/75 p-4 sm:p-5">
              {/* Header row */}
              <div className="flex items-center gap-2 flex-wrap">
                <Badge className={severityColors[e.severity]}>{e.severity.replace("_", " ")}</Badge>
                {e.review_action && <Badge variant="outline">{reviewLabel[e.review_action]}</Badge>}
                <span className="text-xs text-muted-foreground ml-auto">{formatDate(e.created_at)}</span>
              </div>

              <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1.2fr)_minmax(15rem,18rem)]">
                <div className="space-y-4">
                  {(e.signal_label || weWatched) && (
                    <div className="space-y-1">
                      <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                        Assumption under test
                      </p>
                      <p className="font-sans text-sm leading-relaxed text-foreground">
                        {e.signal_label ?? weWatched}
                      </p>
                    </div>
                  )}

                  {youSaid && (
                    <div className="product-panel border border-border/60 bg-background/72 px-4 py-3">
                      <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                        What you wrote
                      </p>
                      <p className="mt-2 text-sm italic text-foreground/75">
                        &quot;{youSaid}&quot;
                      </p>
                    </div>
                  )}

                  <div className="space-y-2">
                    <div className="flex items-center gap-1.5">
                      <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                        Evidence read
                      </p>
                      <InfoTip label="Evidence read">
                        {investorProfile === "thesis_driven"
                          ? "A summary of the public information PenKeep checked against the relevant part of your thesis."
                          : investorProfile === "hearsay_driven"
                            ? "A summary of the public information PenKeep checked against the relevant part of your reason."
                            : "A summary of the public information PenKeep checked against the relevant part of your reason."}
                      </InfoTip>
                    </div>
                    {e.evidence_summary ? (
                      <EvidenceNarrative text={e.evidence_summary} />
                    ) : (
                      <div className="space-y-1 text-sm">
                        <p>
                          <span className="font-medium text-muted-foreground">What happened:</span>{" "}
                          <span className="text-foreground/90">{narrative.whatChanged}</span>
                        </p>
                        {narrative.whyItMatters && (
                          <p>
                            <span className="font-medium text-muted-foreground">Why it matters:</span>{" "}
                            <span className="text-foreground/90">{narrative.whyItMatters}</span>
                          </p>
                        )}
                      </div>
                    )}
                  </div>

                  {e.ai_analysis && !e.evidence_summary && (
                    <p className="text-sm italic text-foreground/85">{e.ai_analysis}</p>
                  )}
                </div>

                <aside className="space-y-3 border-t border-border/50 pt-4 lg:border-t-0 lg:pt-0">
                  <div className="product-panel border border-border/60 bg-background/72 px-3 py-3 space-y-1">
                    <div className="flex items-center gap-1.5">
                      <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                        {reviewDecision ? "Your ruling" : "Verdict"}
                      </p>
                      <InfoTip label={reviewDecision ? "Your ruling" : "Verdict"}>
                        {reviewDecision
                          ? "The decision you saved after reading the evidence. Your ruling stays separate from the model read."
                          : investorProfile === "thesis_driven"
                            ? "PenKeep's read of how the evidence relates to your thesis. You still decide whether the thesis holds."
                            : investorProfile === "hearsay_driven"
                              ? "PenKeep's read of how the evidence relates to your reason. You still decide whether the reason holds."
                              : "PenKeep's read of how the evidence relates to your reason. You still decide whether it still holds."}
                      </InfoTip>
                    </div>
                    {reviewDecision ? (
                      <p className={`inline-block rounded-md px-2 py-1 text-sm font-medium ${reviewDecision.className}`}>
                        {reviewDecision.sentence}
                      </p>
                    ) : verdict ? (
                      <p className={`inline-block rounded-md px-2 py-1 text-sm font-medium ${verdict.className}`}>
                        {verdict.sentence}
                      </p>
                    ) : (
                      <p className="text-sm text-muted-foreground">No model verdict yet.</p>
                    )}
                  </div>

                  {reviewDecision && verdict && (
                    <div className="product-panel border border-border/60 bg-background/72 px-3 py-3 space-y-1">
                      <div className="flex items-center gap-1.5">
                        <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                          Model read
                        </p>
                        <InfoTip label="Model read">
                          PenKeep&apos;s classification before your ruling. It is kept so you can compare the system&apos;s read with the decision you made.
                        </InfoTip>
                      </div>
                      <p className="text-sm text-muted-foreground">
                        {verdict.sentence}
                      </p>
                    </div>
                  )}

                  {e.review_notes && (
                    <div className="product-panel border border-border/60 bg-background/72 px-3 py-3 space-y-1">
                      <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                        Why you ruled that way
                      </p>
                      <p className="text-sm leading-relaxed text-foreground/85">
                        {e.review_notes}
                      </p>
                    </div>
                  )}
                </aside>
              </div>

              {/* Review actions — only for unreviewed events */}
              {onReview && !e.review_action && (
                <div className="mt-4 rounded-lg border bg-muted/20 p-3">
                  <p className="text-sm font-medium">{copy.title}</p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {copy.description}
                  </p>
                  <Textarea
                    value={notesByEvent[e.id] ?? ""}
                    onChange={(event) =>
                      setNotesByEvent((current) => ({
                        ...current,
                        [e.id]: event.target.value,
                      }))
                    }
                    placeholder="Optional note about why this still matters, why it doesn't, or what changed."
                    className="mt-3 min-h-20"
                  />
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Button
                      size="sm"
                      disabled={reviewingEventId === e.id}
                      onClick={() => void onReview(e, "reaffirmed", notesByEvent[e.id])}
                    >
                      {copy.hold}
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={reviewingEventId === e.id}
                      onClick={() => onEditReason?.(e)}
                    >
                      {copy.edit}
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={reviewingEventId === e.id}
                      onClick={() => void onReview(e, "lowered_confidence", notesByEvent[e.id])}
                    >
                      {copy.lower}
                    </Button>
                    <Button
                      size="sm"
                      variant="destructive"
                      disabled={reviewingEventId === e.id}
                      onClick={() => void onReview(e, "invalidated", notesByEvent[e.id])}
                    >
                      {copy.broken}
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={reviewingEventId === e.id}
                      onClick={() => void onReview(e, "not_relevant", notesByEvent[e.id])}
                    >
                      {copy.irrelevant}
                    </Button>
                  </div>
                </div>
              )}

              {e.source_url && (
                <a
                  href={e.source_url}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-4 inline-block text-sm text-primary underline-offset-4 hover:underline"
                >
                  Source
                </a>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
