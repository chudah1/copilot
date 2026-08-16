"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import { AppShell } from "@/components/layout/app-shell";
import { digestStatusLabel, digestStatusTone } from "@/lib/digest-status";
import { formatDate } from "@/lib/utils";
import type { Digest } from "@/types";

function digestDetailCopy(investorProfile: "thesis_driven" | "hearsay_driven" | null) {
  if (investorProfile === "thesis_driven") {
    return {
      keyTakeaways: "Thesis takeaways",
      stats: "Thesis stats",
      stable: "Assumptions intact",
      missing: "Missing thesis",
      stale: "Refresh due",
      openLoops: "Open follow-ups",
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
      stale: "Refresh due",
      openLoops: "Open follow-ups",
      nextEarnings: "Next earnings",
      unavailable: "Digest content unavailable.",
      fallbackHeadlinePrefix: "Reason digest",
    };
  }

  return {
    keyTakeaways: "Key takeaways",
    stats: "Review stats",
    stable: "Holding steady",
    missing: "Missing reason",
    stale: "Refresh due",
    openLoops: "Open follow-ups",
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
    .replace(/Stale reasons:/g, "Theses due for refresh:")
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
    api.get<Digest>(`/api/digests/${id}`).then((nextDigest) => {
      setDigest(nextDigest);
      void api.post(`/api/digests/${id}/review`).catch(() => undefined);
    });
  }, [id]);

  if (!digest) {
    return (
      <AppShell>
        <div className="mx-auto max-w-5xl px-4 py-10 sm:px-8 animate-pulse space-y-5">
          <div className="h-2.5 w-16 bg-muted rounded" />
          <div className="product-panel border border-border/70 bg-[linear-gradient(180deg,rgba(163,126,79,0.07),rgba(255,255,255,0.96))] p-6 sm:p-7 space-y-4">
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
    digest.content.open_loops_count ||
    digest.content.concentration_warning;
  const copy = digestDetailCopy(digest.content.investor_profile ?? null);
  const actionQueue = digest.content.action_queue ?? (digest.content.next_action ? [digest.content.next_action] : []);

  return (
    <AppShell>
      <div className="mx-auto max-w-5xl px-4 py-10 sm:px-8 space-y-5">

        <Link
          href="/digests"
          className="mb-8 inline-block font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground transition-colors hover:text-primary"
        >
          Digest archive
        </Link>

        <div className="product-panel border border-border/70 bg-[linear-gradient(180deg,rgba(163,126,79,0.07),rgba(255,255,255,0.96))] p-6 sm:p-7">
          <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_16rem]">
            <div className="space-y-3">
              <div className="flex flex-wrap items-center gap-3">
                <span className={`font-mono text-[10px] uppercase tracking-[0.2em] ${digestStatusTone(digest)}`}>
                  ● {digestStatusLabel(digest)}
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
                {digest.sent_at ? `Emailed ${formatDate(digest.sent_at)}` : "Saved in your archive"}
                {" · "}Review window {formatDate(digest.period_start)} — {formatDate(digest.period_end)}
              </p>
            </div>

            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1">
                <div className="product-panel border border-border/60 bg-background/72 p-4">
                  <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                    Coverage
                  </p>
                  <p className="mt-2 font-display text-[1.35rem] italic leading-tight text-foreground">
                    {digest.content.holdings_count || 0} holdings tracked
                  </p>
                </div>
                <div className="product-panel border border-border/60 bg-background/72 p-4">
                  <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                    Activity
                  </p>
                  <p className="mt-2 font-display text-[1.35rem] italic leading-tight text-foreground">
                    {digest.content.events_count || 0} events covered
                  </p>
                </div>
              </div>
            </div>
        </div>

        {actionQueue.length > 0 && (
          <section className="product-panel border border-primary/30 bg-[linear-gradient(180deg,rgba(163,126,79,0.1),rgba(255,255,255,0.96))] p-5 sm:p-6">
            <div className="flex flex-col gap-1.5 sm:flex-row sm:items-end sm:justify-between">
              <div>
                <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-primary">
                  Your next move
                </p>
                <h2 className="mt-2 font-display text-[1.7rem] italic leading-tight text-foreground">
                  Start here, then close the rest if they still need you.
                </h2>
              </div>
              <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground/65">
                {actionQueue.length} {actionQueue.length === 1 ? "action" : "actions"}
              </p>
            </div>
            <div className="mt-5 grid gap-3 lg:grid-cols-3">
              {actionQueue.map((action, index) => (
                <div
                  key={action.action_key}
                  className={`flex flex-col justify-between gap-4 border p-4 ${index === 0 ? "border-primary/45 bg-background/90" : "border-border/70 bg-background/65"}`}
                >
                  <div className="space-y-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-primary">
                        {action.ticker}
                      </span>
                      {action.carried_forward && (
                        <span className="border border-amber-600/25 bg-amber-600/10 px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-[0.12em] text-amber-800">
                          Carried forward
                        </span>
                      )}
                    </div>
                    <h3 className="font-sans text-sm font-medium leading-snug text-foreground">
                      {action.title}
                    </h3>
                    <p className="font-sans text-xs leading-relaxed text-foreground/70">
                      {action.detail}
                    </p>
                  </div>
                  <Link
                    href={action.cta_href}
                    className="inline-flex w-fit items-center border border-primary/30 px-3 py-2 font-mono text-[10px] uppercase tracking-[0.14em] text-primary transition-colors hover:border-primary/60"
                  >
                    {action.cta_label}
                  </Link>
                </div>
              ))}
            </div>
          </section>
        )}

        <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_18rem]">
          <div className="space-y-5">
            {hasStats && (
              <div className="grid gap-5 md:grid-cols-[1.2fr_0.8fr]">
                <div className="product-panel p-5 space-y-3">
                  <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-muted-foreground/70">
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
                        className="inline-flex items-center border border-border/60 bg-background/72 px-3 py-2 font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground transition-colors hover:border-border hover:text-foreground"
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

                <div className="product-panel border border-border/60 bg-background/82 p-5 space-y-4">
                  <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-muted-foreground/70">
                    {copy.stats}
                  </p>
                  <div className="grid grid-cols-2 gap-4">
                    {[
                      { label: copy.stable, value: String(digest.content.stable_holdings_count || 0) },
                      { label: copy.missing, value: String(digest.content.missing_theses_count || 0), warn: (digest.content.missing_theses_count ?? 0) > 0 },
                      { label: copy.stale, value: String(digest.content.stale_theses_count || 0), warn: (digest.content.stale_theses_count ?? 0) > 0 },
                      { label: copy.openLoops, value: String(digest.content.open_loops_count || 0), warn: (digest.content.open_loops_count ?? 0) > 0 },
                    ].map(({ label, value, warn }) => (
                      <div key={label}>
                        <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground/55">{label}</p>
                        <p className={`font-mono text-xl tabular-nums mt-1 ${warn ? "text-amber-700" : "text-foreground/80"}`}>{value}</p>
                      </div>
                    ))}
                  </div>
                  {(digest.content.open_loops?.length ?? 0) > 0 && (
                    <div className="border-t border-border/60 pt-3 space-y-2">
                      {digest.content.open_loops?.slice(0, 2).map((loop) => (
                        <div key={loop.loop_key} className="product-panel border border-border/60 bg-background/72 px-3 py-3 space-y-1">
                          <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground/65">
                            {loop.ticker} · {loop.loop_type.replaceAll("_", " ")}
                          </p>
                          <p className="font-sans text-xs leading-relaxed text-foreground/80">
                            {loop.title}
                          </p>
                        </div>
                      ))}
                    </div>
                  )}
                  {digest.content.concentration_warning && (
                    <div className="border-t border-border/60 pt-3">
                      <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-amber-800">
                        Concentration note
                      </p>
                      <p className="mt-1 whitespace-pre-line font-sans text-xs leading-relaxed text-foreground/78">
                        {normalizeDigestText(digest.content.concentration_warning, digest.content.investor_profile ?? null)}
                      </p>
                    </div>
                  )}
                  {digest.content.monitoring_receipt && (
                    <div className="border-t border-border/60 pt-3">
                      <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground/65">
                        Monitoring receipt
                      </p>
                      <p className="mt-1 whitespace-pre-line font-mono text-[9px] leading-relaxed text-muted-foreground/55">
                        {normalizeDigestText(digest.content.monitoring_receipt, digest.content.investor_profile ?? null)}
                      </p>
                    </div>
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
                This digest reflects the evidence and decision state captured across that period.
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
                The point is not market narration. It is what changed, what stayed intact, and what deserves your next read.
              </p>
            </div>
          </aside>
        </div>
      </div>
    </AppShell>
  );
}
