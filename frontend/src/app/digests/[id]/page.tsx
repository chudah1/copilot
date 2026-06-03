"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import { AppShell } from "@/components/layout/app-shell";
import { formatDate } from "@/lib/utils";
import type { Digest } from "@/types";

function digestDetailCopy(investorProfile: "thesis_driven" | "hearsay_driven" | null) {
  if (investorProfile === "thesis_driven") {
    return {
      keyTakeaways: "Thesis takeaways",
      stats: "Thesis stats",
      stable: "Assumptions intact",
      missing: "Missing thesis",
      stale: "Stale thesis",
      nextEarnings: "Next earnings",
      unavailable: "Digest content unavailable.",
      fallbackHeadlinePrefix: "Thesis digest",
    };
  }

  if (investorProfile === "hearsay_driven") {
    return {
      keyTakeaways: "Reason takeaways",
      stats: "Reason stats",
      stable: "Reasons intact",
      missing: "Missing reason",
      stale: "Stale reason",
      nextEarnings: "Next earnings",
      unavailable: "Digest content unavailable.",
      fallbackHeadlinePrefix: "Reason digest",
    };
  }

  return {
    keyTakeaways: "Key takeaways",
    stats: "Digest stats",
    stable: "Stable",
    missing: "Missing thesis",
    stale: "Stale thesis",
    nextEarnings: "Next earnings",
    unavailable: "Digest content unavailable.",
    fallbackHeadlinePrefix: "Digest",
  };
}

const POINTS_INITIAL = 5;

export default function DigestDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [digest, setDigest] = useState<Digest | null>(null);
  const [showAllPoints, setShowAllPoints] = useState(false);

  useEffect(() => {
    api.get<Digest>(`/api/digests/${id}`).then(setDigest);
  }, [id]);

  if (!digest) {
    return (
      <AppShell>
        <div className="max-w-4xl mx-auto px-4 sm:px-8 py-10 animate-pulse">
          <div className="h-2.5 w-16 bg-muted rounded mb-8" />
          <div className="border-b border-border pb-7 mb-8 space-y-3">
            <div className="flex gap-3">
              <div className="h-2.5 w-10 bg-muted rounded" />
              <div className="h-2.5 w-20 bg-muted/60 rounded" />
            </div>
            <div className="h-10 w-3/4 bg-muted rounded" />
            <div className="h-2.5 w-48 bg-muted/60 rounded" />
          </div>
          <div className="grid gap-5 md:grid-cols-[1.2fr_0.8fr] mb-10">
            <div className="border border-border/60 bg-card p-5 space-y-3">
              <div className="h-2 w-20 bg-muted rounded" />
              {[1, 2, 3].map(i => <div key={i} className="h-3.5 w-full bg-muted/60 rounded" />)}
            </div>
            <div className="border border-border/60 bg-card p-5 space-y-4">
              <div className="h-2 w-16 bg-muted rounded" />
              <div className="grid grid-cols-2 gap-4">
                {[1, 2, 3].map(i => (
                  <div key={i}>
                    <div className="h-2 w-14 bg-muted/60 rounded" />
                    <div className="h-6 w-8 bg-muted rounded mt-1" />
                  </div>
                ))}
              </div>
            </div>
          </div>
          <div className="border-t border-border/60 pt-8 space-y-3">
            {[1, 2, 3, 4].map(i => <div key={i} className="h-3 bg-muted/40 rounded" style={{ width: `${85 - i * 5}%` }} />)}
          </div>
        </div>
      </AppShell>
    );
  }

  const hasStats = digest.content.summary_points?.length ||
    digest.content.missing_theses_count ||
    digest.content.stale_theses_count ||
    digest.content.concentration_warning;
  const copy = digestDetailCopy(digest.content.investor_profile ?? null);

  return (
    <AppShell>
      <div className="max-w-4xl mx-auto px-4 sm:px-8 py-10">

        {/* Back link */}
        <Link
          href="/digests"
          className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground hover:text-primary transition-colors mb-8 block"
        >
          ← Digests
        </Link>

        {/* Header */}
        <div className="border-b border-border pb-7 mb-8 space-y-3">
          {/* Badges row */}
          <div className="flex flex-wrap items-center gap-3">
            <span className={`font-mono text-[10px] uppercase tracking-[0.2em] ${digest.status === "sent" ? "text-emerald-700" : "text-amber-700"}`}>
              ● {digest.status}
            </span>
            {digest.content.digest_mode && (
              <span className="font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground/60">
                {digest.content.digest_mode.replace("_", " ")}
              </span>
            )}
            <span className="font-mono text-[10px] text-muted-foreground/60">
              {digest.content.events_count || 0} events · {digest.content.holdings_count || 0} holdings
            </span>
          </div>

          {/* Headline */}
          <h1 className="font-display italic text-[2.25rem] leading-tight text-foreground">
            {digest.content.headline || `${copy.fallbackHeadlinePrefix}: ${formatDate(digest.period_start)} — ${formatDate(digest.period_end)}`}
          </h1>

          {/* Meta */}
          <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground/60">
            {digest.sent_at ? `Sent ${formatDate(digest.sent_at)}` : "Not yet sent"}
            {" · "}Review window {formatDate(digest.period_start)} — {formatDate(digest.period_end)}
          </p>
        </div>

        {/* Summary stats */}
        {hasStats && (
          <div className="grid gap-5 md:grid-cols-[1.2fr_0.8fr] mb-10">
            {/* Key takeaways */}
            <div className="border border-border/60 bg-card p-5 space-y-3">
              <p className="font-mono text-[9px] uppercase tracking-[0.25em] text-muted-foreground/60">
                {copy.keyTakeaways}
              </p>
              <div className="space-y-2">
                {(showAllPoints
                  ? (digest.content.summary_points || [])
                  : (digest.content.summary_points || []).slice(0, POINTS_INITIAL)
                ).map((point) => (
                  <p key={point} className="font-sans text-sm text-foreground/80 leading-relaxed">
                    {point}
                  </p>
                ))}
                {(digest.content.summary_points?.length ?? 0) > POINTS_INITIAL && !showAllPoints && (
                  <button
                    onClick={() => setShowAllPoints(true)}
                    className="font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground hover:text-foreground transition-colors"
                  >
                    Show {(digest.content.summary_points?.length ?? 0) - POINTS_INITIAL} more →
                  </button>
                )}
                {digest.content.next_earnings && (
                  <p className="font-sans text-sm text-foreground/80 leading-relaxed">
                    {copy.nextEarnings}: {digest.content.next_earnings.ticker} reports {formatDate(digest.content.next_earnings.report_date)}.
                  </p>
                )}
                {digest.content.quiet_nudge && (
                  <p className="font-sans italic text-sm text-muted-foreground leading-relaxed">
                    {digest.content.quiet_nudge}
                  </p>
                )}
              </div>
            </div>

            {/* Stats */}
            <div className="border border-border/60 bg-card p-5 space-y-4">
              <p className="font-mono text-[9px] uppercase tracking-[0.25em] text-muted-foreground/60">
                {copy.stats}
              </p>
              <div className="grid grid-cols-2 gap-4">
                {[
                  { label: copy.stable, value: String(digest.content.stable_holdings_count || 0) },
                  { label: copy.missing, value: String(digest.content.missing_theses_count || 0), warn: (digest.content.missing_theses_count ?? 0) > 0 },
                  { label: copy.stale, value: String(digest.content.stale_theses_count || 0), warn: (digest.content.stale_theses_count ?? 0) > 0 },
                ].map(({ label, value, warn }) => (
                  <div key={label}>
                    <p className="font-mono text-[9px] uppercase tracking-[0.2em] text-muted-foreground/50">{label}</p>
                    <p className={`font-mono text-xl tabular-nums mt-1 ${warn ? "text-amber-700" : "text-foreground/80"}`}>{value}</p>
                  </div>
                ))}
              </div>
              {digest.content.concentration_warning && (
                <p className="font-sans text-xs text-amber-700/80 border-t border-border/60 pt-3 leading-relaxed">
                  {digest.content.concentration_warning}
                </p>
              )}
              {digest.content.monitoring_receipt && (
                <p className="font-mono text-[9px] text-muted-foreground/50 leading-relaxed">
                  {digest.content.monitoring_receipt}
                </p>
              )}
            </div>
          </div>
        )}

        {/* Digest HTML content */}
        <div className="border-t border-border/60 pt-8">
          {digest.content.html ? (
            <div
              className="prose prose-sm max-w-none prose-headings:font-display prose-headings:italic prose-headings:font-normal prose-p:text-foreground/80 prose-a:text-primary prose-strong:text-foreground/90"
              dangerouslySetInnerHTML={{ __html: digest.content.html }}
            />
          ) : (
            <p className="font-sans italic text-muted-foreground">{copy.unavailable}</p>
          )}
        </div>
      </div>
    </AppShell>
  );
}
