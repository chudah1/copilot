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

const EVENT_TYPE_LABELS: Record<string, string> = {
  price_move: "Price move",
  earnings_surprise: "Earnings surprise",
  earnings_call_transcript: "Earnings call",
  upcoming_earnings: "Upcoming earnings",
  metric_threshold: "Metric breach",
  edgar_8k: "SEC filing",
  insider_transaction: "Insider activity",
  gemini_news: "News",
  news_keyword_match: "News",
  news_or_earnings_candidate: "News",
};

function entryLabel(entryType: string) {
  return ENTRY_LABELS[entryType] ?? entryType.replaceAll("_", " ");
}

function parseEvidenceContent(content: string) {
  const structuredKeys = new Set([
    "Your thesis",
    "You said",
    "Your reason",
    "We were watching",
    "What changed",
    "What happened",
    "Why it matters now",
    "Why this matters now",
    "Next step",
  ]);

  const parsed: Record<string, string> = {};
  const body: string[] = [];

  for (const line of content.split("\n")) {
    const i = line.indexOf(":");
    if (i > 0 && i < 28) {
      const key = line.slice(0, i).trim();
      const value = line.slice(i + 1).trim().replace(/^"|"$/g, "");
      if (value && structuredKeys.has(key)) {
        parsed[key] = value;
        continue;
      }
    }
    if (line.trim()) body.push(line.trim());
  }

  const rawBody = body.join(" ").trim();
  const repeatedReasonMatch = rawBody.match(
    /^Your (?:reason|thesis):\s*"([^"]+)"\s*(.*)$/i,
  );

  const repeatedReason = repeatedReasonMatch?.[1]?.trim() ?? null;
  const remainder = repeatedReasonMatch?.[2]?.trim() ?? rawBody;

  return {
    reason:
      parsed["Your thesis"] ??
      parsed["Your reason"] ??
      parsed["You said"] ??
      repeatedReason,
    whatChanged:
      parsed["What changed"] ??
      parsed["What happened"] ??
      remainder,
    whyItMatters:
      parsed["Why it matters now"] ??
      parsed["Why this matters now"] ??
      null,
    nextStep: parsed["Next step"] ?? null,
  };
}

function SimpleEntry({ entry }: { entry: ConvictionLogEntry }) {
  const isDark =
    entry.entry_type === "reason_created" || entry.entry_type === "reason_updated";
  const isEvidence = entry.entry_type === "evidence_received";
  const parsedEvidence = isEvidence ? parseEvidenceContent(entry.content) : null;
  const meta = entry.metadata_json ?? {};
  const eventType =
    typeof meta.event_type === "string" ? EVENT_TYPE_LABELS[meta.event_type] ?? meta.event_type.replaceAll("_", " ") : null;
  const severity =
    typeof meta.severity === "string" ? meta.severity : null;

  return (
    <div className="border border-border/60 bg-background/70 px-4 py-4">
      <div className="flex items-start gap-4">
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
          {isEvidence && eventType && (
            <>
              <span className="text-border/40 text-xs">·</span>
              <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-foreground/60">
                {eventType}
              </span>
            </>
          )}
          {isEvidence && severity && (
            <span className={`font-mono text-[10px] uppercase tracking-[0.12em] ${SEVERITY_COLOR[severity] ?? "text-muted-foreground"}`}>
              {severity}
            </span>
          )}
        </div>
        {isEvidence && parsedEvidence ? (
          <div className="mt-1 space-y-2">
            <p className="font-sans text-[13px] text-foreground/90 leading-relaxed">
              {parsedEvidence.whatChanged}
            </p>
            {parsedEvidence.whyItMatters && (
              <p className="font-sans text-[13px] text-foreground/75 leading-relaxed">
                {parsedEvidence.whyItMatters}
              </p>
            )}
            {parsedEvidence.nextStep && (
              <p className="font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground/70">
                {parsedEvidence.nextStep}
              </p>
            )}
          </div>
        ) : (
          <p className="font-sans text-[13px] text-foreground/85 leading-relaxed mt-0.5">
            {entry.content}
          </p>
        )}
      </div>
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
    <div className="border border-border/60 bg-background/70 px-4 py-4">
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
        <p className="font-sans text-[13px] text-foreground/80 leading-relaxed mt-2.5 pl-1 border-l border-border/30">
          {notes}
        </p>
      )}

      {entry.resolution_read && (
        <div className="mt-3 border border-border/40 bg-muted/15 px-3 py-2.5">
          <p className="font-mono text-[9px] uppercase tracking-[0.15em] text-muted-foreground mb-1">
            Read back
          </p>
          <p className="font-sans text-[13px] text-foreground/85 leading-relaxed">
            {entry.resolution_read}
          </p>
        </div>
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
          title: "History",
          age: "Thesis age",
          placeholder:
            "Write a short note about what changed, which assumption moved, or how your view is evolving.",
          empty:
            "No history yet. Once you write a thesis, review evidence, or add notes, it will appear here.",
        }
      : investorProfile === "hearsay_driven"
        ? {
            title: "History",
            age: "Reason age",
            placeholder:
              "Write a short note about what changed or how your view of the story is evolving.",
            empty:
              "No history yet. Once you write a reason, review evidence, or add notes, it will appear here.",
          }
        : {
            title: "History",
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
      <div className="product-panel p-5 sm:p-6">
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-1">
            <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
              {copy.title}
            </p>
            <p className="font-sans text-sm leading-relaxed text-foreground/80">
              Notes, evidence, and decisions that changed the case over time.
            </p>
          </div>
        </div>
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <div className="border border-border/60 bg-background/70 p-3">
            <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
              {copy.age}
            </p>
            <p className="mt-2 font-display text-[1.15rem] italic leading-none text-foreground">
              {data?.reason_age_days != null ? `${data.reason_age_days}d` : "—"}
            </p>
          </div>
          <div className="border border-border/60 bg-background/70 p-3">
            <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
              Reviews
            </p>
            <p className="mt-2 font-display text-[1.15rem] italic leading-none text-foreground">
              {data?.review_count ?? 0}
            </p>
          </div>
        </div>
      </div>

      {onAddNote && (
        <div className="product-panel p-5 sm:p-6 space-y-3">
          <div className="space-y-1">
            <p className="font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground">
              Add note
            </p>
            <p className="font-sans text-sm leading-relaxed text-foreground/80">
              Capture a change in view before it gets lost.
            </p>
          </div>
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

      {loading ? (
        <div className="product-panel p-5 sm:p-6">
          <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground/40 animate-pulse">
            Loading history…
          </p>
        </div>
      ) : data && data.entries.length > 0 ? (
        <div className="space-y-3">
          {data.entries.map((entry) =>
            entry.event_title != null ? (
              <DecisionEntry key={entry.id} entry={entry} />
            ) : (
              <SimpleEntry key={entry.id} entry={entry} />
            ),
          )}
        </div>
      ) : (
        <div className="product-panel p-5 sm:p-6">
          <p className="font-sans text-sm text-muted-foreground">{copy.empty}</p>
        </div>
      )}
    </div>
  );
}
