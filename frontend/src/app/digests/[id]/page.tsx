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

function normalizeDigestTerminology(
  value: string,
  investorProfile: "thesis_driven" | "hearsay_driven" | null,
) {
  if (investorProfile !== "thesis_driven") {
    return value;
  }

  return value
    .replace(/Missing reasons:/g, "Missing theses:")
    .replace(/Stale reasons:/g, "Stale theses:")
    .replace(/Your reason:/g, "Your thesis:")
    .replace(/Threatens this reason/g, "Threatens this thesis")
    .replace(/Review this reason/g, "Review this thesis")
    .replace(/worth a look against your reason\./g, "worth a look against your thesis.")
    .replace(/The reason still holds,/g, "The thesis still holds,")
    .replace(/(\d+) of your reasons need review this week\./g, "$1 of your theses need review this week.");
}

function normalizeDigestText(
  value: string | null | undefined,
  investorProfile: "thesis_driven" | "hearsay_driven" | null,
) {
  if (!value) return "";
  return normalizeDigestTerminology(
    value.replace(/\\n/g, "\n").replace(/\n{3,}/g, "\n\n").trim(),
    investorProfile,
  );
}

function normalizeDigestHtml(
  value: string | null | undefined,
  investorProfile: "thesis_driven" | "hearsay_driven" | null,
) {
  if (!value) return "";
  return normalizeDigestTerminology(value.replace(/\\n/g, "<br />"), investorProfile);
}

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
        <div className="mx-auto max-w-5xl px-4 py-10 sm:px-8 animate-pulse space-y-5">
          <div className="h-2.5 w-16 bg-muted rounded" />
          <div className="product-panel product-panel-muted p-6 sm:p-7 space-y-4">
            <div className="flex gap-3">
              <div className="h-2.5 w-10 bg-muted rounded" />
              <div className="h-2.5 w-20 bg-muted/60 rounded" />
            </div>
            <div className="h-10 w-3/4 bg-muted rounded" />
            <div className="h-2.5 w-48 bg-muted/60 rounded" />
          </div>
          <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_18rem]">
            <div className="space-y-5">
              <div className="grid gap-5 md:grid-cols-[1.2fr_0.8fr]">
                <div className="product-panel p-5 space-y-3">
                  <div className="h-2 w-20 bg-muted rounded" />
                  {[1, 2, 3].map(i => <div key={i} className="h-3.5 w-full bg-muted/60 rounded" />)}
                </div>
                <div className="product-panel p-5 space-y-4">
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
              <div className="product-panel p-6 space-y-3">
                {[1, 2, 3, 4].map(i => <div key={i} className="h-3 bg-muted/40 rounded" style={{ width: `${85 - i * 5}%` }} />)}
              </div>
            </div>
            <div className="space-y-4">
              <div className="product-panel h-28" />
              <div className="product-panel h-36" />
            </div>
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
      <div className="mx-auto max-w-5xl px-4 py-10 sm:px-8 space-y-5">

        <Link
          href="/digests"
          className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground hover:text-primary transition-colors mb-8 block"
        >
          ← Digests
        </Link>

        <div className="product-panel product-panel-muted p-6 sm:p-7">
          <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_16rem]">
            <div className="space-y-3">
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

              <h1 className="font-display italic text-[2.25rem] leading-tight text-foreground">
                {normalizeDigestText(
                  digest.content.headline || `${copy.fallbackHeadlinePrefix}: ${formatDate(digest.period_start)} — ${formatDate(digest.period_end)}`,
                  digest.content.investor_profile ?? null,
                )}
              </h1>

              <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground/60">
                {digest.sent_at ? `Sent ${formatDate(digest.sent_at)}` : "Not yet sent"}
                {" · "}Review window {formatDate(digest.period_start)} — {formatDate(digest.period_end)}
              </p>
            </div>

            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1">
              <div className="border border-border/60 bg-background/70 p-4">
                <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                  Coverage
                </p>
                <p className="mt-2 font-display text-[1.35rem] italic leading-tight text-foreground">
                  {digest.content.holdings_count || 0} holdings tracked
                </p>
              </div>
              <div className="border border-border/60 bg-background/70 p-4">
                <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                  Activity
                </p>
                <p className="mt-2 font-display text-[1.35rem] italic leading-tight text-foreground">
                  {digest.content.events_count || 0} events reviewed
                </p>
              </div>
            </div>
          </div>
        </div>

        <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_18rem]">
          <div className="space-y-5">
            {hasStats && (
              <div className="grid gap-5 md:grid-cols-[1.2fr_0.8fr]">
                <div className="product-panel p-5 space-y-3">
                  <p className="font-mono text-[9px] uppercase tracking-[0.25em] text-muted-foreground/60">
                    {copy.keyTakeaways}
                  </p>
                  <div className="space-y-2">
                    {(showAllPoints
                      ? (digest.content.summary_points || [])
                      : (digest.content.summary_points || []).slice(0, POINTS_INITIAL)
                    ).map((point) => (
                      <p key={point} className="whitespace-pre-line font-sans text-sm text-foreground/80 leading-relaxed">
                        {normalizeDigestText(point, digest.content.investor_profile ?? null)}
                      </p>
                    ))}
                    {(digest.content.summary_points?.length ?? 0) > POINTS_INITIAL && !showAllPoints && (
                      <button
                        onClick={() => setShowAllPoints(true)}
                        className="font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground hover:text-foreground transition-colors"
                      >
                        Show {(digest.content.summary_points?.length ?? 0) - POINTS_INITIAL} more
                      </button>
                    )}
                    {digest.content.next_earnings && (
                      <p className="font-sans text-sm text-foreground/80 leading-relaxed">
                        {copy.nextEarnings}: {digest.content.next_earnings.ticker} reports {formatDate(digest.content.next_earnings.report_date)}.
                      </p>
                    )}
                    {digest.content.quiet_nudge && (
                      <p className="whitespace-pre-line font-sans italic text-sm text-muted-foreground leading-relaxed">
                        {normalizeDigestText(digest.content.quiet_nudge, digest.content.investor_profile ?? null)}
                      </p>
                    )}
                  </div>
                </div>

                <div className="product-panel p-5 space-y-4">
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
                    <p className="whitespace-pre-line font-sans text-xs text-amber-700/80 border-t border-border/60 pt-3 leading-relaxed">
                      {normalizeDigestText(digest.content.concentration_warning, digest.content.investor_profile ?? null)}
                    </p>
                  )}
                  {digest.content.monitoring_receipt && (
                    <p className="whitespace-pre-line font-mono text-[9px] text-muted-foreground/50 leading-relaxed">
                      {normalizeDigestText(digest.content.monitoring_receipt, digest.content.investor_profile ?? null)}
                    </p>
                  )}
                </div>
              </div>
            )}

            <div className="product-panel p-6 sm:p-7">
              {digest.content.html ? (
                <div
                  className="prose prose-sm max-w-none prose-headings:font-display prose-headings:italic prose-headings:font-normal prose-a:text-primary prose-p:text-foreground/80 prose-li:text-foreground/80 prose-strong:text-foreground/90"
                  dangerouslySetInnerHTML={{ __html: normalizeDigestHtml(digest.content.html, digest.content.investor_profile ?? null) }}
                />
              ) : (
                <p className="font-sans italic text-muted-foreground">{copy.unavailable}</p>
              )}
            </div>
          </div>

          <aside className="space-y-4">
            <div className="product-panel p-5">
              <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                Review window
              </p>
              <p className="mt-2 font-display text-[1.35rem] italic leading-tight text-foreground">
                {formatDate(digest.period_start)} to {formatDate(digest.period_end)}
              </p>
              <p className="mt-2 font-sans text-sm leading-relaxed text-muted-foreground">
                This digest reflects the evidence and thesis state captured across that period.
              </p>
            </div>
            <div className="product-panel p-5">
              <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                Read this as
              </p>
              <p className="mt-2 font-display text-[1.35rem] italic leading-tight text-foreground">
                A portfolio decision memo.
              </p>
              <p className="mt-2 font-sans text-sm leading-relaxed text-muted-foreground">
                The point is not market narration. It is what changed, what stayed intact, and what deserves attention next.
              </p>
            </div>
          </aside>
        </div>
      </div>
    </AppShell>
  );
}
