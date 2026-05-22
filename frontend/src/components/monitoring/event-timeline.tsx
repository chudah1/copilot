"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
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

const verdictConfig: Record<string, { label: string; sentence: string; className: string }> = {
  supports: {
    label: "Supports",
    sentence: "This evidence supports your reason.",
    className: "bg-emerald-500/15 text-emerald-700",
  },
  threatens: {
    label: "Threatens",
    sentence: "This evidence threatens your reason.",
    className: "bg-red-500/15 text-red-600",
  },
  review: {
    label: "Review",
    sentence: "This evidence warrants a closer look at your reason.",
    className: "bg-amber-500/15 text-amber-700",
  },
  neutral: {
    label: "Neutral",
    sentence: "This evidence is neutral — it doesn't directly affect your reason.",
    className: "bg-muted text-muted-foreground",
  },
};

const reviewLabel: Record<string, string> = {
  reaffirmed: "Reaffirmed",
  ignored: "Ignored",
  lowered_confidence: "Lowered confidence",
  invalidated: "Invalidated",
  not_relevant: "Not relevant",
};

function reviewLanguage(investorProfile?: "thesis_driven" | "hearsay_driven" | null) {
  if (investorProfile === "thesis_driven") {
    return {
      empty: "Nothing new yet. We're still watching this position against your thesis.",
      title: "What does this do to your thesis?",
      description: "Log what you decided — it keeps your assumptions and alerts honest.",
      hold: "Thesis still holds",
      edit: "Update thesis",
      lower: "Assumption weaker",
      broken: "Thesis is broken",
      irrelevant: "Not relevant",
    };
  }

  if (investorProfile === "hearsay_driven") {
    return {
      empty: "Nothing new yet. We're still checking whether the reason you wrote still holds.",
      title: "What does this do to your reason?",
      description: "Log whether this changes the story, or whether you need to sharpen what you wrote.",
      hold: "Reason still holds",
      edit: "Rewrite the reason",
      lower: "Less sure now",
      broken: "Story is broken",
      irrelevant: "Not relevant",
    };
  }

  return {
    empty: "Nothing new yet. We're still watching this position against what you wrote.",
    title: "What do you want to do?",
    description: "Log what you decided — it keeps alerts from crying wolf.",
    hold: "Reason still holds",
    edit: "Update my reason",
    lower: "Lower confidence",
    broken: "Reason is broken",
    irrelevant: "Not relevant",
  };
}

function parseNarrative(text: string) {
  const parsed: Record<string, string> = {};
  for (const line of text.split("\n")) {
    const colonIdx = line.indexOf(":");
    if (colonIdx > 0 && colonIdx < 24) {
      const key = line.slice(0, colonIdx).trim();
      const value = line.slice(colonIdx + 1).trim();
      if (value) parsed[key] = value;
    }
  }
  return parsed;
}

function eventNarrativeFields(event: MonitoringEvent) {
  const narrative = event.evidence_summary ? parseNarrative(event.evidence_summary) : {};
  return {
    youSaid: narrative["Your thesis"] ?? narrative["You said"] ?? narrative["Your reason"] ?? null,
    weWatched: narrative["We were watching"] ?? narrative["What the app was checking"] ?? narrative["We watched"] ?? event.signal_label ?? null,
    whatChanged: narrative["What changed"] ?? narrative["What happened"] ?? event.summary,
    whyItMatters: narrative["Why it matters now"] ?? event.ai_analysis ?? null,
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
    return <p className="mt-2 text-sm text-foreground/80">{text}</p>;
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

  if (events.length === 0) {
    return (
      <Card>
        <CardHeader><CardTitle className="text-base">Monitoring Events</CardTitle></CardHeader>
        <CardContent>
          <p className="text-foreground/70">{copy.empty}</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader><CardTitle className="text-base">Monitoring Events</CardTitle></CardHeader>
      <CardContent className="space-y-4">
        {events.map((e) => {
          const verdict = e.verdict ? verdictConfig[e.verdict] : null;
          const narrative = eventNarrativeFields(e);
          const youSaid = narrative.youSaid;
          const weWatched = narrative.weWatched;

          return (
            <div key={e.id} className="rounded-xl border p-4">
              {/* Header row */}
              <div className="flex items-center gap-2 flex-wrap">
                <Badge className={severityColors[e.severity]}>{e.severity.replace("_", " ")}</Badge>
                {e.review_action && <Badge variant="outline">{reviewLabel[e.review_action]}</Badge>}
                <span className="text-xs text-muted-foreground ml-auto">{formatDate(e.created_at)}</span>
              </div>

              {/* Signal affected — shown prominently when available */}
              {(e.signal_label || weWatched) && (
                <p className="mt-2 text-sm font-medium text-muted-foreground">
                  Assumption being tested:{" "}
                  <span className="text-foreground">{e.signal_label ?? weWatched}</span>
                </p>
              )}

              {/* Your reason mentioned */}
              {youSaid && (
                <blockquote className="mt-2 border-l-2 border-muted pl-3 text-sm italic text-muted-foreground">
                  &quot;{youSaid}&quot;
                </blockquote>
              )}

              {/* Evidence details */}
              {e.evidence_summary ? (
                <EvidenceNarrative text={e.evidence_summary} />
              ) : (
                <div className="mt-2 space-y-1 text-sm">
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

              {/* Verdict as a sentence */}
              {verdict && (
                <p className={`mt-2 rounded-md px-2 py-1 text-sm font-medium inline-block ${verdict.className}`}>
                  {verdict.sentence}
                </p>
              )}

              {e.ai_analysis && !e.evidence_summary && (
                <p className="mt-2 text-sm italic text-foreground/75">{e.ai_analysis}</p>
              )}

              {e.review_notes && (
                <p className="mt-1 text-sm text-foreground/70">Your note: {e.review_notes}</p>
              )}

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
                  className="mt-2 inline-block text-sm text-primary underline-offset-4 hover:underline"
                >
                  Open source
                </a>
              )}
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}
