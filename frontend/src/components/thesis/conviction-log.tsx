"use client";

import { useState } from "react";
import { formatDate } from "@/lib/utils";
import { InfoTip } from "@/components/ui/info-tip";
import type { ConvictionLogEntry, ConvictionLogResponse } from "@/types";

interface ConvictionLogProps {
  data: ConvictionLogResponse | null;
  loading?: boolean;
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
  // received_at is only set when the arrival was folded into this card, so the
  // content is the evidence description rather than a duplicate of the title.
  const isMergedEvidence = Boolean(entry.received_at);

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
            {isMergedEvidence ? "Evidence & decision" : "Decision"}
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

      {entry.event_title && (
        <div className="mb-3">
          <p className="font-sans text-sm text-foreground leading-snug">
            {entry.event_title}
          </p>
          <p className="font-mono text-[10px] text-muted-foreground/60 mt-1">
            {entry.event_severity && (
              <span className={`uppercase tracking-[0.12em] ${SEVERITY_COLOR[entry.event_severity] ?? "text-muted-foreground"}`}>
                {entry.event_severity}
              </span>
            )}
            {entry.received_at && (
              <span className="ml-2">arrived {formatDate(entry.received_at)}</span>
            )}
          </p>
        </div>
      )}

      {isMergedEvidence && entry.content && (
        <p className="font-sans text-[13px] text-foreground/80 leading-relaxed mb-3">
          {entry.content}
        </p>
      )}

      <div className="grid md:grid-cols-2 gap-3 empty:hidden">
        {entry.bet_text && (
          <div className="border border-border/40 bg-muted/20 px-3 py-2.5">
            <p className="font-mono text-[9px] uppercase tracking-[0.15em] text-muted-foreground mb-1">
              What you were relying on
            </p>
            <p className="font-sans text-[13px] text-foreground/80 leading-snug">
              {entry.bet_text}
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

      {entry.resolution_read ? (
        <div className="mt-3 border border-border/40 bg-muted/15 px-3 py-2.5">
          <p className="font-mono text-[9px] uppercase tracking-[0.15em] text-muted-foreground mb-1">
            What happened next
          </p>
          <p className="font-sans text-[13px] text-foreground/85 leading-relaxed">
            {entry.resolution_read}
          </p>
        </div>
      ) : entry.follow_up_at ? (
        <p className="mt-3 font-mono text-[10px] text-primary/70">
          Outcome check {formatDate(entry.follow_up_at)}
        </p>
      ) : null}
    </div>
  );
}

type LogFilter = "all" | "decisions" | "notes";

export function ConvictionLog({
  data,
  loading = false,
  investorProfile,
}: ConvictionLogProps) {
  const [showAll, setShowAll] = useState(false);
  const [filter, setFilter] = useState<LogFilter>("all");

  const copy =
    investorProfile === "thesis_driven"
      ? {
          title: "History",
          age: "Thesis age",
          empty:
            "No history yet. Once you write a thesis, review evidence, or add notes, it will appear here.",
        }
      : investorProfile === "hearsay_driven"
        ? {
          title: "History",
          age: "Reason age",
          empty:
              "No history yet. Once you write a reason, review evidence, or add notes, it will appear here.",
          }
        : {
            title: "History",
            age: "Reason age",
            empty: "Nothing logged yet. Reviews, notes, and reason changes show up here.",
          };

  const entries = data?.entries ?? [];
  // Only reviewed evidence is a decision — received entries also carry an
  // event_title now, but they are still waiting for a call.
  const isDecision = (e: ConvictionLogEntry) =>
    e.entry_type === "evidence_reviewed" && e.event_title != null;
  const decisionCount = entries.filter(isDecision).length;
  const noteCount = entries.filter((e) => e.entry_type === "manual_note").length;
  const filteredEntries =
    filter === "decisions"
      ? entries.filter(isDecision)
      : filter === "notes"
        ? entries.filter((e) => e.entry_type === "manual_note")
        : entries;
  const visibleEntries = showAll ? filteredEntries : filteredEntries.slice(0, 2);
  const filterChips: { id: LogFilter; label: string; count: number }[] = [
    { id: "all", label: "All", count: entries.length },
    { id: "decisions", label: "Decisions", count: decisionCount },
    { id: "notes", label: "Notes", count: noteCount },
  ];

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
            <div className="flex items-center gap-1">
              <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                {copy.age}
              </p>
              <InfoTip label={copy.age}>
                The number of days since this written reason was first recorded.
              </InfoTip>
            </div>
            <p className="mt-2 font-display text-[1.15rem] italic leading-none text-foreground">
              {data?.reason_age_days != null
                ? `${data.reason_age_days} day${data.reason_age_days === 1 ? "" : "s"}`
                : "—"}
            </p>
          </div>
          <div className="border border-border/60 bg-background/70 p-3">
            <div className="flex items-center gap-1">
              <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                Reviews recorded
              </p>
              <InfoTip label="Reviews recorded">
                The number of times you responded to evidence or formally revisited this written reason.
              </InfoTip>
            </div>
            <p className="mt-2 font-display text-[1.15rem] italic leading-none text-foreground">
              {data?.review_count ?? 0}
            </p>
          </div>
        </div>
      </div>

      {loading ? (
        <div className="product-panel p-5 sm:p-6">
          <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground/40 animate-pulse">
            Loading history…
          </p>
        </div>
      ) : data && data.entries.length > 0 ? (
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            {filterChips.map((chip) => (
              <button
                key={chip.id}
                onClick={() => {
                  setFilter(chip.id);
                  setShowAll(false);
                }}
                className={`border px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.14em] transition-colors ${
                  filter === chip.id
                    ? "border-primary/40 bg-primary/5 text-primary"
                    : "border-border/60 text-muted-foreground hover:text-foreground"
                }`}
              >
                {chip.label}
                <span className="ml-1.5 tabular-nums opacity-60">{chip.count}</span>
              </button>
            ))}
          </div>
          {filter === "decisions" && (
            <p className="font-sans text-xs leading-relaxed text-muted-foreground">
              What you decided, and what happened next. A good decision can still lose
              money; a bad one can still get lucky.
            </p>
          )}
          {filteredEntries.length === 0 ? (
            <div className="product-panel p-5 sm:p-6">
              <p className="font-sans text-sm text-muted-foreground">
                {filter === "decisions"
                  ? "No decisions recorded yet. Your first call will appear here after you review a change."
                  : "No notes yet. Use + Note to record what you're thinking."}
              </p>
            </div>
          ) : (
            <>
              {visibleEntries.map((entry) =>
                isDecision(entry) ? (
                  <DecisionEntry key={entry.id} entry={entry} />
                ) : (
                  <SimpleEntry key={entry.id} entry={entry} />
                ),
              )}
              {filteredEntries.length > 2 && (
                <button
                  onClick={() => setShowAll((current) => !current)}
                  className="w-full border border-border/60 bg-background/60 px-4 py-3 font-mono text-[10px] uppercase tracking-[0.16em] text-primary transition-colors hover:border-primary/35"
                >
                  {showAll ? "Show less" : `See all ${filteredEntries.length} history items`}
                </button>
              )}
            </>
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
