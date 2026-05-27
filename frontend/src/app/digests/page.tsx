"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { AppShell } from "@/components/layout/app-shell";
import { formatDate } from "@/lib/utils";
import type { Digest } from "@/types";

function statusDot(status: string) {
  if (status === "sent") return "text-emerald-700";
  if (status === "draft") return "text-amber-700";
  return "text-muted-foreground";
}

function digestArchiveCopy(investorProfile: "thesis_driven" | "hearsay_driven" | null) {
  if (investorProfile === "thesis_driven") {
    return {
      title: "Weekly thesis reviews",
      subtitle: "What moved, what held, and which assumptions need another look.",
      empty: "Your first digest will arrive after at least one position has an active thesis and monitoring is running.",
      fallbackHeadline: "Weekly thesis review",
    };
  }

  if (investorProfile === "hearsay_driven") {
    return {
      title: "Weekly reason reviews",
      subtitle: "What moved, what held, and where the story you wrote may need a decision.",
      empty: "Your first digest will arrive after at least one position has a written reason and monitoring is running.",
      fallbackHeadline: "Weekly reason review",
    };
  }

  return {
    title: "Weekly reviews",
    subtitle: "What moved, what stayed quiet, and where your thesis needs a decision.",
    empty: "Your first digest will arrive on Sunday after at least one holding has an active thesis and monitoring is running.",
    fallbackHeadline: "Weekly thesis review",
  };
}

export default function DigestsPage() {
  const [digests, setDigests] = useState<Digest[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get<Digest[]>("/api/digests").then(setDigests).finally(() => setLoading(false));
  }, []);

  const investorProfile = digests[0]?.content.investor_profile ?? null;
  const copy = digestArchiveCopy(investorProfile);

  return (
    <AppShell>
      <div className="max-w-4xl mx-auto px-4 sm:px-8 py-10">

        {/* Page header */}
        <div className="border-b border-border pb-6 mb-8">
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

        {loading ? (
          <div className="animate-pulse space-y-0">
            {[1, 2, 3].map((i) => (
              <div key={i} className="flex items-start justify-between gap-6 border-b border-border/60 py-6">
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
          <div className="py-16 text-center">
            <p className="font-display italic text-2xl text-foreground/60 mb-3">
              No digests yet.
            </p>
            <p className="font-sans text-sm text-muted-foreground max-w-sm mx-auto leading-relaxed">
              {copy.empty}
            </p>
          </div>
        ) : (
          <div>
            {digests.map((d) => (
              <Link
                key={d.id}
                href={`/digests/${d.id}`}
                className="group flex items-start justify-between gap-6 border-b border-border/60 py-6 transition-colors hover:bg-card -mx-4 px-4"
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
                    {d.content.headline || copy.fallbackHeadline}
                  </p>

                  {/* Summary points */}
                  {d.content.summary_points && d.content.summary_points.length > 0 && (
                    <p className="font-sans italic text-sm text-muted-foreground leading-relaxed line-clamp-2">
                      {d.content.summary_points[0]}
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
                          {d.content.missing_theses_count} missing thesis
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
