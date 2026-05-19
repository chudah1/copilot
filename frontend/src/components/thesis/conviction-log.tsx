"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { formatDate } from "@/lib/utils";
import type { ConvictionLogEntry, ConvictionLogResponse } from "@/types";

interface ConvictionLogProps {
  data: ConvictionLogResponse | null;
  loading?: boolean;
  saving?: boolean;
  onAddNote?: (content: string) => Promise<void>;
}

const entryLabels: Record<string, string> = {
  reason_created: "Reason created",
  signals_generated: "Signals generated",
  signal_confirmed: "Signal confirmed",
  signal_removed: "Signal removed",
  evidence_received: "Evidence received",
  evidence_reviewed: "Reviewed after evidence",
  reason_updated: "Reason updated",
  reason_invalidated: "Reason invalidated",
  post_earnings_review: "Post-earnings review",
  quarterly_review: "Quarterly review",
  manual_note: "Manual note",
};

function entryLabel(entryType: string) {
  return entryLabels[entryType] ?? entryType.replaceAll("_", " ");
}

function entryTone(entryType: string) {
  if (entryType === "reason_invalidated") return "bg-red-500/15 text-red-600";
  if (entryType === "evidence_reviewed") return "bg-sky-500/15 text-sky-700";
  if (entryType === "manual_note") return "bg-muted text-muted-foreground";
  return "bg-emerald-500/15 text-emerald-700";
}

function EntryRow({ entry }: { entry: ConvictionLogEntry }) {
  return (
    <div className="border-l-2 border-muted pl-4 py-3">
      <div className="flex flex-wrap items-center gap-2">
        <Badge className={entryTone(entry.entry_type)}>{entryLabel(entry.entry_type)}</Badge>
        <span className="text-xs text-muted-foreground">{formatDate(entry.created_at)}</span>
      </div>
      <p className="mt-2 text-sm leading-6">{entry.content}</p>
    </div>
  );
}

export function ConvictionLog({ data, loading = false, saving = false, onAddNote }: ConvictionLogProps) {
  const [note, setNote] = useState("");

  const handleSubmit = async () => {
    const trimmed = note.trim();
    if (!trimmed || !onAddNote) return;
    await onAddNote(trimmed);
    setNote("");
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <CardTitle className="text-base">Conviction log</CardTitle>
            <CardDescription>
              A permanent record of what changed, what you decided, and how long this reason has held up.
            </CardDescription>
          </div>
          <div className="flex flex-wrap gap-2">
            <Badge variant="outline">
              Reason age: {data?.reason_age_days != null ? `${data.reason_age_days} days` : "Not started"}
            </Badge>
            <Badge variant="outline">
              Reviews: {data?.review_count ?? 0}
            </Badge>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {onAddNote && (
          <div className="rounded-xl border bg-muted/30 p-3">
            <p className="text-sm font-medium">Add a note</p>
            <p className="mt-1 text-xs text-muted-foreground">
              Capture what you are noticing now so the future version of you has the context.
            </p>
            <Textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Write a short note about what changed or how your view is evolving."
              className="mt-3 min-h-24"
            />
            <div className="mt-3 flex justify-end">
              <Button onClick={() => void handleSubmit()} disabled={saving || note.trim().length === 0}>
                {saving ? "Saving..." : "Add note"}
              </Button>
            </div>
          </div>
        )}

        {loading ? (
          <p className="text-sm text-muted-foreground">Loading conviction history...</p>
        ) : data && data.entries.length > 0 ? (
          <div className="space-y-1">
            {data.entries.map((entry) => (
              <EntryRow key={entry.id} entry={entry} />
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">
            No conviction history yet. Once you write a reason, review evidence, or add notes, it will appear here.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
