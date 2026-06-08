"use client";

import type { HistoricalAuditResultItem, HistoricalAuditResponse } from "@/types";
import { formatDate } from "@/lib/utils";

const SEVERITY_BADGE: Record<string, string> = {
  thesis_breaking: "bg-red-100 text-red-700 border border-red-200",
  warning: "bg-amber-100 text-amber-700 border border-amber-200",
  info: "bg-blue-100 text-blue-700 border border-blue-200",
};

const SEVERITY_LABEL: Record<string, string> = {
  thesis_breaking: "Thesis breaking",
  warning: "Warning",
  info: "Info",
};

function AuditResultItem({ item }: { item: HistoricalAuditResultItem }) {
  const url =
    item.evidence &&
    typeof item.evidence === "object" &&
    typeof item.evidence.url === "string"
      ? item.evidence.url
      : null;

  return (
    <div className="flex items-start gap-3 py-3 border-b border-border/40 last:border-0">
      <span
        className={`mt-0.5 shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide ${SEVERITY_BADGE[item.severity] ?? SEVERITY_BADGE.info}`}
      >
        {SEVERITY_LABEL[item.severity] ?? item.severity}
      </span>
      <div className="flex-1 min-w-0">
        <p className="text-sm text-foreground leading-snug">
          {url ? (
            <a
              href={url}
              target="_blank"
              rel="noopener noreferrer"
              className="hover:underline"
            >
              {item.description}
            </a>
          ) : (
            item.description
          )}
        </p>
        {item.event_date && (
          <p className="mt-0.5 text-xs text-muted-foreground">{formatDate(item.event_date)}</p>
        )}
      </div>
    </div>
  );
}

interface Props {
  audit: HistoricalAuditResponse | null;
}

export function HistoricalAuditCard({ audit }: Props) {
  if (!audit || audit.status === "failed") return null;

  if (audit.status === "pending") {
    return (
      <div className="rounded-lg border border-border/60 bg-muted/30 p-4 mt-4">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <span className="h-3 w-3 rounded-full border-2 border-muted-foreground/40 border-t-foreground animate-spin" />
          Running 90-day audit…
        </div>
      </div>
    );
  }

  if (audit.status === "empty") {
    return (
      <div className="rounded-lg border border-border/60 bg-muted/30 p-4 mt-4">
        <p className="text-sm text-muted-foreground">
          No major events in the last 90 days — your thesis has been steady.
        </p>
      </div>
    );
  }

  const results = audit.results ?? [];

  return (
    <div className="rounded-lg border border-border/60 bg-card p-4 mt-4">
      <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground mb-3">
        90-day lookback
      </p>
      <p className="text-sm font-medium text-foreground mb-3">
        If you&apos;d held this thesis for the last 90 days, here&apos;s what would have fired:
      </p>
      <div>
        {results.map((item) => (
          <AuditResultItem
            key={`${item.event_type}-${item.event_date ?? "nodate"}-${item.severity}`}
            item={item}
          />
        ))}
      </div>
    </div>
  );
}
