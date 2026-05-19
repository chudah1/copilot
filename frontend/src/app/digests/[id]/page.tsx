"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import { AppShell } from "@/components/layout/app-shell";
import { formatDate } from "@/lib/utils";
import type { Digest } from "@/types";

export default function DigestDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [digest, setDigest] = useState<Digest | null>(null);

  useEffect(() => {
    api.get<Digest>(`/api/digests/${id}`).then(setDigest);
  }, [id]);

  if (!digest) {
    return (
      <AppShell>
        <div className="flex items-center justify-center min-h-[calc(100vh-52px)]">
          <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground animate-pulse">
            Loading…
          </p>
        </div>
      </AppShell>
    );
  }

  const hasStats = digest.content.summary_points?.length ||
    digest.content.missing_theses_count ||
    digest.content.stale_theses_count ||
    digest.content.concentration_warning;

  return (
    <AppShell>
      <div className="max-w-4xl mx-auto px-8 py-10">

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
            {digest.content.headline || `Digest: ${formatDate(digest.period_start)} — ${formatDate(digest.period_end)}`}
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
                Key takeaways
              </p>
              <div className="space-y-2">
                {(digest.content.summary_points || []).map((point) => (
                  <p key={point} className="font-sans text-sm text-foreground/80 leading-relaxed">
                    {point}
                  </p>
                ))}
                {digest.content.next_earnings && (
                  <p className="font-sans text-sm text-foreground/80 leading-relaxed">
                    Next earnings: {digest.content.next_earnings.ticker} reports {formatDate(digest.content.next_earnings.report_date)}.
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
                Digest stats
              </p>
              <div className="grid grid-cols-2 gap-4">
                {[
                  { label: "Stable", value: String(digest.content.stable_holdings_count || 0) },
                  { label: "Missing thesis", value: String(digest.content.missing_theses_count || 0), warn: (digest.content.missing_theses_count ?? 0) > 0 },
                  { label: "Stale thesis", value: String(digest.content.stale_theses_count || 0), warn: (digest.content.stale_theses_count ?? 0) > 0 },
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
              className="prose prose-invert prose-sm max-w-none prose-headings:font-display prose-headings:italic prose-headings:font-normal prose-a:text-primary prose-strong:text-foreground/90"
              dangerouslySetInnerHTML={{ __html: digest.content.html }}
            />
          ) : (
            <p className="font-sans italic text-muted-foreground">Digest content unavailable.</p>
          )}
        </div>
      </div>
    </AppShell>
  );
}
