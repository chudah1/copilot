"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatDate } from "@/lib/utils";
import type { MonitoringEvent } from "@/types";

interface Props {
  events: MonitoringEvent[];
  onReview?: (event: MonitoringEvent, action: "reaffirmed" | "ignored" | "lowered_confidence" | "invalidated") => Promise<void>;
  reviewingEventId?: string | null;
}

const severityColors: Record<string, string> = {
  info: "bg-blue-100 text-blue-800",
  warning: "bg-orange-100 text-orange-800",
  thesis_breaking: "bg-red-100 text-red-800",
};

const verdictConfig: Record<string, { label: string; className: string }> = {
  supports: { label: "Supports", className: "bg-emerald-100 text-emerald-800" },
  threatens: { label: "Threatens", className: "bg-red-100 text-red-800" },
  review: { label: "Review", className: "bg-amber-100 text-amber-800" },
  neutral: { label: "Neutral", className: "bg-stone-100 text-stone-700" },
};

const reviewLabel: Record<string, string> = {
  reaffirmed: "Reaffirmed",
  ignored: "Ignored",
  lowered_confidence: "Lowered confidence",
  invalidated: "Invalidated",
};

function EvidenceNarrative({ text }: { text: string }) {
  const lines = text.split("\n");
  return (
    <div className="mt-2 space-y-1 rounded-lg bg-muted/50 p-3 text-sm">
      {lines.map((line, i) => {
        const colonIdx = line.indexOf(":");
        if (colonIdx > 0 && colonIdx < 20) {
          const label = line.slice(0, colonIdx);
          const value = line.slice(colonIdx + 1).trim();
          return (
            <p key={i}>
              <span className="font-medium text-muted-foreground">{label}:</span>{" "}
              {value}
            </p>
          );
        }
        return <p key={i}>{line}</p>;
      })}
    </div>
  );
}

export function EventTimeline({ events, onReview, reviewingEventId }: Props) {
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
        {events.map((e) => (
          <div key={e.id} className="border-l-2 border-muted pl-4">
            <div className="flex items-center gap-2">
              <Badge className={severityColors[e.severity]}>{e.severity.replace("_", " ")}</Badge>
              {e.verdict && verdictConfig[e.verdict] && (
                <Badge className={verdictConfig[e.verdict].className}>
                  {verdictConfig[e.verdict].label}
                </Badge>
              )}
              {e.review_action && <Badge variant="outline">{reviewLabel[e.review_action]}</Badge>}
              <span className="text-xs text-muted-foreground">{formatDate(e.created_at)}</span>
            </div>
            <h4 className="mt-1 font-medium">{e.title}</h4>
            {e.evidence_summary ? (
              <EvidenceNarrative text={e.evidence_summary} />
            ) : (
              <p className="text-sm text-muted-foreground">{e.summary}</p>
            )}
            {e.ai_analysis && <p className="mt-1 text-sm italic">{e.ai_analysis}</p>}
            {e.review_notes && <p className="mt-1 text-sm text-muted-foreground">Review note: {e.review_notes}</p>}
            {onReview && (
              <div className="mt-3 flex flex-wrap gap-2">
                <Button size="sm" variant="outline" disabled={reviewingEventId === e.id} onClick={() => void onReview(e, "reaffirmed")}>
                  Reaffirm
                </Button>
                <Button size="sm" variant="outline" disabled={reviewingEventId === e.id} onClick={() => void onReview(e, "ignored")}>
                  Ignore
                </Button>
                <Button size="sm" variant="outline" disabled={reviewingEventId === e.id} onClick={() => void onReview(e, "lowered_confidence")}>
                  Lower confidence
                </Button>
                <Button size="sm" variant="destructive" disabled={reviewingEventId === e.id} onClick={() => void onReview(e, "invalidated")}>
                  Invalidate
                </Button>
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
        ))}
      </CardContent>
    </Card>
  );
}
