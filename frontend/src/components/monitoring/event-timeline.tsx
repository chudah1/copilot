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
}

const severityColors: Record<string, string> = {
  info: "bg-blue-100 text-blue-800",
  warning: "bg-orange-100 text-orange-800",
  thesis_breaking: "bg-red-100 text-red-800",
};

const verdictConfig: Record<string, { label: string; sentence: string; className: string }> = {
  supports: {
    label: "Supports",
    sentence: "This evidence supports your reason.",
    className: "bg-emerald-100 text-emerald-800",
  },
  threatens: {
    label: "Threatens",
    sentence: "This evidence threatens your reason.",
    className: "bg-red-100 text-red-800",
  },
  review: {
    label: "Review",
    sentence: "This evidence warrants a closer look at your reason.",
    className: "bg-amber-100 text-amber-800",
  },
  neutral: {
    label: "Neutral",
    sentence: "This evidence is neutral — it doesn't directly affect your reason.",
    className: "bg-stone-100 text-stone-700",
  },
};

const reviewLabel: Record<string, string> = {
  reaffirmed: "Reaffirmed",
  ignored: "Ignored",
  lowered_confidence: "Lowered confidence",
  invalidated: "Invalidated",
  not_relevant: "Not relevant",
};

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

function EvidenceNarrative({ text }: { text: string }) {
  const narrative = parseNarrative(text);
  // "You said" and "We watched" are shown in the card header, skip them here
  const items = [
    ["What happened", narrative["What happened"]],
    ["Verdict", narrative["Verdict"]],
  ].filter((item): item is [string, string] => Boolean(item[1]));

  if (items.length === 0) {
    return <p className="mt-2 text-sm text-muted-foreground">{text}</p>;
  }

  return (
    <div className="mt-2 space-y-1 text-sm">
      {items.map(([label, value]) => (
        <p key={label}>
          <span className="font-medium text-muted-foreground">{label}:</span>{" "}
          {value}
        </p>
      ))}
    </div>
  );
}

export function EventTimeline({ events, onReview, onEditReason, reviewingEventId }: Props) {
  const [notesByEvent, setNotesByEvent] = useState<Record<string, string>>({});

  if (events.length === 0) {
    return (
      <Card>
        <CardHeader><CardTitle className="text-base">Monitoring Events</CardTitle></CardHeader>
        <CardContent>
          <p className="text-muted-foreground">No material changes yet. The app is still watching this position against your thesis.</p>
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
          const narrative = e.evidence_summary ? parseNarrative(e.evidence_summary) : {};
          const youSaid = narrative["You said"];
          const weWatched = narrative["We watched"];

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
                  Signal affected:{" "}
                  <span className="text-foreground">{e.signal_label ?? weWatched}</span>
                </p>
              )}

              {/* Your reason mentioned */}
              {youSaid && (
                <blockquote className="mt-2 border-l-2 border-muted pl-3 text-sm italic text-muted-foreground">
                  "{youSaid}"
                </blockquote>
              )}

              {/* Evidence details */}
              {e.evidence_summary ? (
                <EvidenceNarrative text={e.evidence_summary} />
              ) : (
                <p className="mt-2 text-sm text-muted-foreground">{e.summary}</p>
              )}

              {/* Verdict as a sentence */}
              {verdict && (
                <p className={`mt-2 rounded-md px-2 py-1 text-sm font-medium inline-block ${verdict.className}`}>
                  {verdict.sentence}
                </p>
              )}

              {e.ai_analysis && (
                <p className="mt-2 text-sm italic text-muted-foreground">{e.ai_analysis}</p>
              )}

              {e.review_notes && (
                <p className="mt-1 text-sm text-muted-foreground">Your note: {e.review_notes}</p>
              )}

              {/* Review actions — only for unreviewed events */}
              {onReview && !e.review_action && (
                <div className="mt-4 rounded-lg border bg-muted/20 p-3">
                  <p className="text-sm font-medium">What do you want to do?</p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    Log the decision so the app can keep the signal quality honest.
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
                      Reason still holds
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={reviewingEventId === e.id}
                      onClick={() => onEditReason?.(e)}
                    >
                      Update my reason
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={reviewingEventId === e.id}
                      onClick={() => void onReview(e, "lowered_confidence", notesByEvent[e.id])}
                    >
                      Lower confidence
                    </Button>
                    <Button
                      size="sm"
                      variant="destructive"
                      disabled={reviewingEventId === e.id}
                      onClick={() => void onReview(e, "invalidated", notesByEvent[e.id])}
                    >
                      Reason is broken
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={reviewingEventId === e.id}
                      onClick={() => void onReview(e, "not_relevant", notesByEvent[e.id])}
                    >
                      Not relevant
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
