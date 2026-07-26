"use client";

import { useState } from "react";
import type { HistoricalAuditResultItem, HistoricalAuditResponse } from "@/types";
import { formatDate } from "@/lib/utils";
import { InfoTip } from "@/components/ui/info-tip";

const BADGE_STYLE: Record<string, string> = {
  supports: "bg-emerald-100 text-emerald-700 border border-emerald-200",
  threatens: "bg-red-100 text-red-700 border border-red-200",
  review: "bg-amber-100 text-amber-700 border border-amber-200",
  neutral: "bg-muted text-muted-foreground border border-border",
  thesis_breaking: "bg-red-100 text-red-700 border border-red-200",
  warning: "bg-amber-100 text-amber-700 border border-amber-200",
  info: "bg-blue-100 text-blue-700 border border-blue-200",
};

const BADGE_LABEL: Record<string, string> = {
  supports: "Held up",
  threatens: "Against",
  review: "Needs review",
  neutral: "Background",
  thesis_breaking: "Thesis breaking",
  warning: "Warning",
  info: "Info",
};

function AuditResultItem({ item }: { item: HistoricalAuditResultItem }) {
  const badgeKey = item.verdict ?? item.severity;
  const url =
    item.evidence &&
    typeof item.evidence === "object" &&
    typeof item.evidence.url === "string"
      ? item.evidence.url
      : null;

  return (
    <div className="flex items-start gap-3 py-3 border-b border-border/40 last:border-0">
      <span
        className={`mt-0.5 shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide ${BADGE_STYLE[badgeKey] ?? BADGE_STYLE.info}`}
      >
        {BADGE_LABEL[badgeKey] ?? badgeKey}
      </span>
      <div className="flex-1 min-w-0">
        {item.signal_label && (
          <p className="mb-1 font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
            Signal: {item.signal_label}
          </p>
        )}
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
        {item.analysis && item.analysis !== item.description && (
          <p className="mt-2 whitespace-pre-line text-xs leading-relaxed text-muted-foreground">
            {item.analysis}
          </p>
        )}
        {item.claim_text && (
          <p className="mt-2 text-xs italic text-muted-foreground">
            Part of your case: {item.claim_text}
          </p>
        )}
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
  const [showAll, setShowAll] = useState(false);
  if (audit?.status === "failed") {
    return (
      <div className="rounded-lg border border-border/60 bg-muted/30 p-4 mt-4">
        <p className="text-sm text-muted-foreground">
          We couldn&apos;t complete the 90-day evidence check.
        </p>
      </div>
    );
  }

  if (!audit || audit.status === "pending") {
    return (
      <div className="rounded-lg border border-border/60 bg-muted/30 p-4 mt-4">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <span className="h-3 w-3 rounded-full border-2 border-muted-foreground/40 border-t-foreground animate-spin" />
          Checking evidence from the past 90 days…
        </div>
      </div>
    );
  }

  if (audit.status === "empty") {
    return (
      <div className="rounded-lg border border-border/60 bg-muted/30 p-4 mt-4">
        <p className="text-sm text-muted-foreground">
          We didn&apos;t find evidence that directly tested this case in the past 90 days.
        </p>
      </div>
    );
  }

  const results = audit.results ?? [];
  const coverageOnly =
    results.length > 0 && results.every((item) => item.event_type === "coverage_gap");
  const visibleResults = showAll ? results : results.slice(0, 3);

  return (
    <div className="rounded-lg border border-border/60 bg-card p-4 mt-4">
      <div className="mb-3 flex items-center gap-1.5">
        <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
          Evidence from the past 90 days
        </p>
        <InfoTip label="90-day evidence check" align="end">
          A one-off look back when the case is created. Held up supports it, Against weakens it, Background is context, and Needs review calls for a closer look.
        </InfoTip>
      </div>
      <p className="text-sm font-medium text-foreground mb-3">
        {coverageOnly
          ? "The evidence check was incomplete, so do not treat a quiet result as proof that the case held up."
          : "Here is how recent evidence relates to the case you just wrote."}
      </p>
      <div>
        {visibleResults.map((item) => (
          <AuditResultItem
            key={`${item.event_type}-${item.event_date ?? "nodate"}-${item.verdict ?? item.severity}-${item.description.slice(0, 20)}`}
            item={item}
          />
        ))}
      </div>
      {results.length > 3 && (
        <button
          onClick={() => setShowAll((current) => !current)}
          className="mt-3 font-mono text-[10px] uppercase tracking-[0.15em] text-primary hover:text-primary/75"
        >
          {showAll ? "Show less" : `See all ${results.length} evidence items`}
        </button>
      )}
    </div>
  );
}
