"use client";

import { useState } from "react";
import { formatDate } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import type { ConvictionLogEntry, ConvictionLogResponse } from "@/types";

interface ConvictionLogProps {
  data: ConvictionLogResponse | null;
  loading?: boolean;
  saving?: boolean;
  onAddNote?: (content: string) => Promise<void>;
  investorProfile?: "thesis_driven" | "hearsay_driven" | null;
}

const ENTRY_LABELS: Record<string, string> = {
  reason_created: "Reason written",
  signals_generated: "Signals generated",
  signal_confirmed: "Signal confirmed",
  signal_removed: "Signal removed",
  evidence_received: "Evidence received",
  evidence_reviewed: "Decision made",
  reason_updated: "Reason updated",
  reason_invalidated: "Reason invalidated",
  post_earnings_review: "Post-earnings review",
  quarterly_review: "Quarterly review",
  manual_note: "Note",
};

const ACTION_LABELS: Record<string, string> = {
  reaffirmed: "Reaffirmed",
  ignored: "Ignored",
  not_relevant: "Not relevant",
  lowered_confidence: "Lowered confidence",
  invalidated: "Invalidated",
};

const ACTION_COLOR: Record<string, string> = {
  reaffirmed: "text-emerald-700",
  ignored: "text-muted-foreground",
  not_relevant: "text-muted-foreground",
  lowered_confidence: "text-amber-700",
  invalidated: "text-red-600",
};

const SEVERITY_COLOR: Record<string, string> = {
  critical: "text-red-600",
  high: "text-orange-600",
  medium: "text-amber-700",
  low: "text-muted-foreground",
};

function entryLabel(entryType: string) {
  return ENTRY_LABELS[entryType] ?? entryType.replaceAll("_", " ");
}

function SimpleEntry({ entry }: { entry: ConvictionLogEntry }) {
  const isDark =
    entry.entry_type === "reason_created" || entry.entry_type === "reason_updated";
  return (
    <div className="flex items-start gap-4 py-3 border-b border-border/20 last:border-b-0">
      <div className="shrink-0 mt-0.5">
        <span
          className={`h-1.5 w-1.5 rounded-full block mt-1 ${isDark ? "bg-primary/50" : "bg-border"}`}
        />
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground">
            {entryLabel(entry.entry_type)}
          </span>
          <span className="font-mono text-[10px] text-muted-foreground/40">
            {formatDate(entry.created_at)}
          </span>
        </div>
        <p className="font-sans text-[13px] text-foreground/70 leading-relaxed mt-0.5">
          {entry.content}
        </p>
      </div>
    </div>
  );
}

function DecisionEntry({ entry }: { entry: ConvictionLogEntry }) {
  const meta = entry.metadata_json ?? {};
  const action = typeof meta.action === "string" ? meta.action : null;
  const notes = typeof meta.notes === "string" && meta.notes ? meta.notes : null;

  const outcomeLabel =
    entry.outcome === "broke"
      ? "Thesis broke"
      : entry.outcome === "held"
        ? "Holding"
        : "Open";
  const outcomeCls =
    entry.outcome === "broke"
      ? "text-red-600 border-red-500/30"
      : entry.outcome === "held"
        ? "text-emerald-700 border-emerald-500/30"
        : "text-muted-foreground/50 border-border/40";

  return (
    <div className="py-4 border-b border-border/20 last:border-b-0">
      {/* Header row */}
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground">
            Decision
          </span>
          <span className="font-mono text-[10px] text-muted-foreground/40">
            {formatDate(entry.created_at)}
          </span>
          {action && (
            <>
              <span className="text-border/40 text-xs">·</span>
              <span
                className={`font-mono text-[10px] uppercase tracking-[0.12em] ${ACTION_COLOR[action] ?? "text-muted-foreground"}`}
              >
                {ACTION_LABELS[action] ?? action}
              </span>
            </>
          )}
        </div>
        <span
          className={`font-mono text-[9px] uppercase tracking-[0.15em] border px-1.5 py-0.5 shrink-0 ${outcomeCls}`}
        >
          {outcomeLabel}
        </span>
      </div>

      <div className="grid md:grid-cols-2 gap-3">
        {entry.event_title && (
          <div className="border border-border/40 bg-muted/20 px-3 py-2.5">
            <p className="font-mono text-[9px] uppercase tracking-[0.15em] text-muted-foreground mb-1">
              Event
              {entry.event_severity && (
                <span className={`ml-2 ${SEVERITY_COLOR[entry.event_severity] ?? "text-muted-foreground"}`}>
                  {entry.event_severity}
                </span>
              )}
            </p>
            <p className="font-sans text-[13px] text-foreground/80 leading-snug">
              {entry.event_title}
            </p>
          </div>
        )}

        {entry.what_would_change_my_mind && (
          <div className="border border-border/40 bg-muted/20 px-3 py-2.5">
            <p className="font-mono text-[9px] uppercase tracking-[0.15em] text-muted-foreground mb-1">
              Your exit condition
            </p>
            <p className="font-sans text-[13px] text-foreground/80 leading-snug italic">
              {entry.what_would_change_my_mind}
            </p>
          </div>
        )}
      </div>

      {notes && (
        <p className="font-sans text-[13px] text-foreground/60 leading-relaxed mt-2.5 pl-1 border-l border-border/30">
          {notes}
        </p>
      )}
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

  const copy =
    investorProfile === "thesis_driven"
      ? {
          age: "Thesis age",
          placeholder:
            "Write a short note about what changed, which assumption moved, or how your view is evolving.",
          empty:
            "No history yet. Once you write a thesis, review evidence, or add notes, it will appear here.",
        }
      : investorProfile === "hearsay_driven"
        ? {
            age: "Reason age",
            placeholder:
              "Write a short note about what changed or how your view of the story is evolving.",
            empty:
              "No history yet. Once you write a reason, review evidence, or add notes, it will appear here.",
          }
        : {
            age: "Reason age",
            placeholder: "Write a short note about what changed or how your view is evolving.",
            empty: "Nothing logged yet. Reviews, notes, and reason changes show up here.",
          };

  const handleSubmit = async () => {
    const trimmed = note.trim();
    if (!trimmed || !onAddNote) return;
    await onAddNote(trimmed);
    setNote("");
  };

  return (
    <div className="space-y-5">
      {/* Stats strip */}
      <div className="flex items-center gap-4 border-b border-border/30 pb-4">
        <div>
          <p className="font-mono text-[9px] uppercase tracking-[0.15em] text-muted-foreground">
            {copy.age}
          </p>
          <p className="font-mono text-[13px] text-foreground mt-0.5">
            {data?.reason_age_days != null ? `${data.reason_age_days}d` : "—"}
          </p>
        </div>
        <div className="w-px h-6 bg-border/30" />
        <div>
          <p className="font-mono text-[9px] uppercase tracking-[0.15em] text-muted-foreground">
            Reviews
          </p>
          <p className="font-mono text-[13px] text-foreground mt-0.5">
            {data?.review_count ?? 0}
          </p>
        </div>
      </div>

      {/* Add note */}
      {onAddNote && (
        <div className="border border-border/40 bg-muted/20 px-4 py-3 space-y-3">
          <p className="font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground">
            Add a note
          </p>
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder={copy.placeholder}
            rows={3}
            className="w-full bg-transparent font-sans text-sm text-foreground placeholder:text-muted-foreground/40 focus:outline-none resize-none"
          />
          <div className="flex justify-end">
            <Button
              onClick={() => void handleSubmit()}
              disabled={saving || note.trim().length === 0}
            >
              <span className="font-mono text-[11px] uppercase tracking-[0.15em]">
                {saving ? "Saving…" : "Save note"}
              </span>
            </Button>
          </div>
        </div>
      )}

      {/* Timeline */}
      {loading ? (
        <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground/40 animate-pulse">
          Loading…
        </p>
      ) : data && data.entries.length > 0 ? (
        <div>
          {data.entries.map((entry) =>
            entry.entry_type === "evidence_reviewed" ? (
              <DecisionEntry key={entry.id} entry={entry} />
            ) : (
              <SimpleEntry key={entry.id} entry={entry} />
            ),
          )}
        </div>
      ) : (
        <p className="font-sans text-sm text-muted-foreground/60">{copy.empty}</p>
      )}
    </div>
  );
}
