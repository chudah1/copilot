"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { getErrorMessage } from "@/lib/errors";
import { AppShell } from "@/components/layout/app-shell";
import { formatDate } from "@/lib/utils";
import type { Digest } from "@/types";

function statusDot(status: string) {
  if (status === "sent" || status === "ready") return "text-emerald-700";
  if (status === "draft") return "text-amber-700";
  return "text-muted-foreground";
}

function digestArchiveCopy(investorProfile: "thesis_driven" | "hearsay_driven" | null) {
  if (investorProfile === "thesis_driven") {
    return {
      title: "Digest archive",
      subtitle: "Weekly thesis review, in one place.",
      empty: "Your first digest lands once at least one position is written and monitoring is running.",
      fallbackHeadline: "Weekly thesis review",
    };
  }

  if (investorProfile === "hearsay_driven") {
    return {
      title: "Digest archive",
      subtitle: "Weekly reason review, in one place.",
      empty: "Your first digest lands once at least one position has a written reason and monitoring is running.",
      fallbackHeadline: "Weekly reason review",
    };
  }

  return {
    title: "Digest archive",
    subtitle: "Weekly review, in one place.",
    empty: "Your first digest lands once at least one holding has an active thesis and monitoring is running.",
    fallbackHeadline: "Weekly thesis review",
  };
}

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

function digestPreview(
  digest: Digest,
  investorProfile: "thesis_driven" | "hearsay_driven" | null,
) {
  const normalized = normalizeDigestText(digest.content.summary_points?.[0], investorProfile);
  if (!normalized) return "";

  const firstSentence = normalized.split(/(?<=[.!?])\s+/)[0]?.trim() ?? normalized;
  return firstSentence.length <= 150 ? firstSentence : `${firstSentence.slice(0, 147).trimEnd()}...`;
}

function dedupeDigests(digests: Digest[]) {
  const seen = new Set<string>();
  return digests.filter((digest) => {
    const investorProfile = digest.content.investor_profile ?? null;
    const headline = normalizeDigestText(digest.content.headline || "", investorProfile);
    const preview = digestPreview(digest, investorProfile);
    const stats = [
      `${digest.content.events_count ?? 0} events`,
      `${digest.content.holdings_count ?? 0} holdings`,
      `${digest.content.stale_theses_count ?? 0} stale`,
      `${digest.content.missing_theses_count ?? 0} missing`,
    ].join("|");
    const key = [
      formatDate(digest.period_start),
      formatDate(digest.period_end),
      headline,
      preview,
      stats,
      digest.status.toLowerCase(),
    ].join("|");
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

export default function DigestsPage() {
  const router = useRouter();
  const [digests, setDigests] = useState<Digest[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);

  useEffect(() => {
    api.get<Digest[]>("/api/digests").then(setDigests).finally(() => setLoading(false));
  }, []);

  const generateNow = async () => {
    setGenerating(true);
    try {
      const digest = await api.post<Digest>("/api/digests/generate");
      setDigests((prev) => [digest, ...prev]);
      toast.success("Digest ready");
      router.push(`/digests/${digest.id}`);
    } catch (err) {
      toast.error(getErrorMessage(err, "Couldn't generate a digest yet"));
    } finally {
      setGenerating(false);
    }
  };

  const investorProfile = digests[0]?.content.investor_profile ?? null;
  const copy = digestArchiveCopy(investorProfile);
  const visibleDigests = dedupeDigests(digests);
  const latestDigest = visibleDigests[0] ?? null;
  const totalEvents = visibleDigests.reduce((sum, digest) => sum + (digest.content.events_count || 0), 0);
  const hasDigests = visibleDigests.length > 0;

  return (
    <AppShell>
      <div className="max-w-5xl mx-auto px-4 sm:px-8 py-10 space-y-6">

        <div className="product-panel product-panel-muted overflow-hidden p-5 sm:p-6">
          <div className="flex items-end justify-between gap-4">
            <div className="space-y-2">
            <p className="font-mono text-[10px] uppercase tracking-[0.3em] text-muted-foreground mb-2">
              Archive
            </p>
            <h1 className="font-display italic text-4xl text-foreground leading-tight">
              {copy.title}
            </h1>
            <p className="font-sans text-sm text-muted-foreground mt-2 max-w-xl leading-relaxed">
              {copy.subtitle}
            </p>
            </div>
            <button
              onClick={generateNow}
              disabled={generating}
              className="shrink-0 font-mono text-[10px] uppercase tracking-[0.15em] text-primary border border-primary/30 px-4 py-2 hover:bg-primary/5 transition-colors disabled:opacity-50"
            >
              {generating ? "Building…" : "Generate"}
            </button>
          </div>

          <div className="mt-6 grid gap-3 sm:grid-cols-3">
            <div className="border border-border/60 bg-background/70 p-4">
                  <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                    {hasDigests ? "In archive" : "First run"}
                  </p>
              {hasDigests ? (
                <p className="mt-2 font-display text-[1.5rem] italic leading-none text-foreground">
                  {visibleDigests.length}
                </p>
              ) : (
                <p className="mt-2 font-sans text-sm leading-relaxed text-foreground">
                  Ready once monitoring is live.
                </p>
              )}
            </div>
            <div className="border border-border/60 bg-background/70 p-4">
              <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                {hasDigests ? "Events covered" : "Cadence"}
              </p>
              {hasDigests ? (
                <p className="mt-2 font-display text-[1.5rem] italic leading-none text-foreground">
                  {totalEvents}
                </p>
              ) : (
                <p className="mt-2 font-sans text-sm leading-relaxed text-foreground">
                  Weekly, built for a quick Sunday review.
                </p>
              )}
            </div>
            <div className="border border-border/60 bg-background/70 p-4">
              <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                {hasDigests ? "Latest" : "Reads like"}
              </p>
              <p className="mt-2 font-sans text-sm leading-relaxed text-foreground">
                {latestDigest ? formatDate(latestDigest.period_end) : "A weekly decision memo, not an alert dump."}
              </p>
            </div>
          </div>
        </div>

        {loading ? (
          <div className="animate-pulse space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="product-panel p-5 flex items-start justify-between gap-6">
                <div className="flex-1 space-y-2.5">
                  <div className="h-2.5 w-40 bg-muted rounded" />
                  <div className="h-4 w-3/4 bg-muted rounded" />
                  <div className="h-3 w-1/2 bg-muted/60 rounded" />
                  <div className="flex gap-4 pt-1">
                    <div className="h-2.5 w-14 bg-muted/50 rounded" />
                    <div className="h-2.5 w-16 bg-muted/50 rounded" />
                  </div>
                </div>
                <div className="shrink-0 space-y-1.5 text-right">
                  <div className="h-2.5 w-10 bg-muted rounded" />
                  <div className="h-2.5 w-16 bg-muted/60 rounded" />
                </div>
              </div>
            ))}
          </div>
        ) : digests.length === 0 ? (
          <div className="product-panel p-6 sm:p-8">
            <div className="grid gap-6 lg:grid-cols-[minmax(0,1.15fr)_minmax(16rem,20rem)]">
              <div className="space-y-4">
                <div className="space-y-2">
                  <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                    First digest
                  </p>
                  <p className="font-display italic text-[1.9rem] leading-tight text-foreground">
                    Nothing on file yet.
                  </p>
                  <p className="max-w-xl font-sans text-sm leading-relaxed text-muted-foreground">
                    {copy.empty}
                  </p>
                </div>

                <div className="grid gap-3 sm:grid-cols-3">
                  <div className="border border-border/60 bg-background/70 p-4">
                    <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
                      What it covers
                    </p>
                    <p className="mt-2 font-sans text-sm leading-relaxed text-foreground/85">
                      What moved, what stayed quiet, and where a decision may be needed.
                    </p>
                  </div>
                  <div className="border border-border/60 bg-background/70 p-4">
                    <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
                      Best used for
                    </p>
                    <p className="mt-2 font-sans text-sm leading-relaxed text-foreground/85">
                      A weekly portfolio pass without reopening every position one by one.
                    </p>
                  </div>
                  <div className="border border-border/60 bg-background/70 p-4">
                    <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
                      Right now
                    </p>
                    <p className="mt-2 font-sans text-sm leading-relaxed text-foreground/85">
                      Generate one now, or wait for the next scheduled run.
                    </p>
                  </div>
                </div>
              </div>

              <aside className="product-panel product-panel-muted p-5 sm:p-6">
                <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                  Start here
                </p>
                <div className="mt-4 space-y-3">
                  <div className="border-l-2 border-primary/20 pl-3">
                    <p className="font-sans text-sm leading-relaxed text-foreground/85">
                      Keep at least one position written and monitored.
                    </p>
                  </div>
                  <div className="border-l-2 border-primary/20 pl-3">
                    <p className="font-sans text-sm leading-relaxed text-foreground/85">
                      Let the digest pull the important changes into one review pass.
                    </p>
                  </div>
                  <div className="border-l-2 border-primary/20 pl-3">
                    <p className="font-sans text-sm leading-relaxed text-foreground/85">
                      Use it as a weekly memo, not a replacement for live alerts.
                    </p>
                  </div>
                </div>
                <button
                  onClick={generateNow}
                  disabled={generating}
                  className="mt-5 font-mono text-[10px] uppercase tracking-[0.15em] text-primary border border-primary/30 px-4 py-2 hover:bg-primary/5 transition-colors disabled:opacity-50"
                >
                  {generating ? "Building…" : "Generate"}
                </button>
              </aside>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            {visibleDigests.map((d) => (
              <Link
                key={d.id}
                href={`/digests/${d.id}`}
                className="group product-panel p-5 flex items-start justify-between gap-6 transition-colors hover:bg-card"
              >
                <div className="flex-1 min-w-0 space-y-2">
                  {/* Date range */}
                  <div className="flex items-baseline gap-3">
                    <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                      {formatDate(d.period_start)} — {formatDate(d.period_end)}
                    </span>
                    {d.content.digest_mode && (
                      <span className="font-mono text-[9px] uppercase tracking-[0.15em] text-primary/60">
                        {d.content.digest_mode.replace("_", " ")}
                      </span>
                    )}
                  </div>

                  {/* Headline */}
                  <p className="font-display italic text-[1.1rem] text-foreground leading-snug group-hover:text-primary transition-colors">
                    {normalizeDigestText(d.content.headline || copy.fallbackHeadline, d.content.investor_profile ?? null)}
                  </p>

                  {/* Summary points */}
                  {digestPreview(d, d.content.investor_profile ?? null) && (
                    <p className="whitespace-pre-line font-sans italic text-sm text-muted-foreground leading-relaxed line-clamp-3">
                      {digestPreview(d, d.content.investor_profile ?? null)}
                    </p>
                  )}

                  {/* Stats row */}
                  <div className="flex items-center gap-4 pt-1">
                    <span className="font-mono text-[10px] text-muted-foreground/60">
                      {d.content.events_count || 0} events
                    </span>
                    <span className="text-border/60">·</span>
                    <span className="font-mono text-[10px] text-muted-foreground/60">
                      {d.content.holdings_count || 0} holdings
                    </span>
                    {!!d.content.stale_theses_count && (
                      <>
                        <span className="text-border/60">·</span>
                        <span className="font-mono text-[10px] text-amber-700/80">
                          {d.content.stale_theses_count} stale
                        </span>
                      </>
                    )}
                    {!!d.content.missing_theses_count && (
                      <>
                        <span className="text-border/60">·</span>
                        <span className="font-mono text-[10px] text-red-600/80">
                          {d.content.missing_theses_count} missing {d.content.missing_theses_count === 1 ? "thesis" : "theses"}
                        </span>
                      </>
                    )}
                  </div>
                </div>

                {/* Right: status + date */}
                <div className="shrink-0 text-right space-y-1">
                  <p className={`font-mono text-[11px] uppercase tracking-[0.15em] ${statusDot(d.status)}`}>
                    ● {d.status}
                  </p>
                  {d.sent_at && (
                    <p className="font-mono text-[10px] text-muted-foreground/50">
                      {formatDate(d.sent_at)}
                    </p>
                  )}
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </AppShell>
  );
}
