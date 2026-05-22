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
  investorProfile?: "thesis_driven" | "hearsay_driven" | null;
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

export function ConvictionLog({
  data,
  loading = false,
  saving = false,
  onAddNote,
  investorProfile,
}: ConvictionLogProps) {
  const [note, setNote] = useState("");
  const copy = investorProfile === "thesis_driven"
    ? {
        title: "Thesis log",
        description: "A permanent record of what changed, what you decided, and how long the thesis has stood up.",
        age: "Thesis age",
        add: "Add a thesis note",
        noteHelp: "Capture what you are noticing now so the future version of you can see how the thesis evolved.",
        notePlaceholder: "Write a short note about what changed, which assumption moved, or how your underwriting view is evolving.",
        empty: "No thesis history yet. Once you write a thesis, review evidence, or add notes, it will appear here.",
      }
    : investorProfile === "hearsay_driven"
      ? {
          title: "Reason log",
          description: "A permanent record of what changed, what you decided, and how the original story held up over time.",
          age: "Reason age",
          add: "Add a reason note",
          noteHelp: "Capture what you are noticing now so the future version of you can see whether the story got stronger or weaker.",
          notePlaceholder: "Write a short note about what changed or how your view of the story is evolving.",
          empty: "No reason history yet. Once you write a reason, review evidence, or add notes, it will appear here.",
        }
      : {
          title: "Conviction log",
          description: "A permanent record of what changed, what you decided, and how long this reason has held up.",
          age: "Reason age",
          add: "Add a note",
          noteHelp: "Capture what you are noticing now so the future version of you has the context.",
          notePlaceholder: "Write a short note about what changed or how your view is evolving.",
          empty: "Nothing logged yet. Reviews, notes, and reason changes show up here.",
        };

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
            <CardTitle className="text-base">{copy.title}</CardTitle>
            <CardDescription>
              {copy.description}
            </CardDescription>
          </div>
          <div className="flex flex-wrap gap-2">
            <Badge variant="outline">
              {copy.age}: {data?.reason_age_days != null ? `${data.reason_age_days} days` : "Not started"}
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
            <p className="text-sm font-medium">{copy.add}</p>
            <p className="mt-1 text-xs text-muted-foreground">
              {copy.noteHelp}
            </p>
            <Textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder={copy.notePlaceholder}
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
            {copy.empty}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
