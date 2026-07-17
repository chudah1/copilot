"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

interface Decision {
  id: string;
  bucket: "held" | "exited" | "dismissed" | string;
  verdict: string;
  decision_source: string;
  decided_at: string | null;
  bet_text: string | null;
  resolved: boolean;
  read: string | null;
  next_test_days: number | null;
}

const BUCKET_LABEL: Record<string, string> = { held: "Held", exited: "Exited", dismissed: "Dismissed" };
const BUCKET_DOT: Record<string, string> = {
  held: "bg-emerald-500",
  exited: "bg-red-500",
  dismissed: "bg-amber-400",
};

function sentenceCase(value: string) {
  const cleaned = value.replace(/_/g, " ").trim();
  if (!cleaned) return "Decision recorded";
  return cleaned.charAt(0).toUpperCase() + cleaned.slice(1);
}

interface Props {
  holdingId: string;
  /** Bump to refetch (e.g. after a review creates a new call). */
  reloadKey?: number;
}

export function PositionDecisions({ holdingId, reloadKey }: Props) {
  const [decisions, setDecisions] = useState<Decision[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .get<Decision[]>(`/api/monitoring/holdings/${holdingId}/decisions`)
      .then((d) => { if (!cancelled) setDecisions(d); })
      .catch(() => { if (!cancelled) setDecisions([]); });
    return () => { cancelled = true; };
  }, [holdingId, reloadKey]);

  if (!decisions) {
    return (
      <section className="product-panel product-panel-muted p-5 sm:p-6">
        <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
          Decision record
        </p>
        <p className="mt-3 font-sans text-sm text-muted-foreground">
          Loading your previous calls…
        </p>
      </section>
    );
  }

  return (
    <section className="space-y-4">
      <div className="product-panel product-panel-muted p-5 sm:p-6">
        <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground mb-0.5">
          Decision record
        </p>
        <p className="mt-2 max-w-2xl font-display text-[1.55rem] italic leading-tight text-foreground sm:text-[1.8rem]">
          What you decided, and what happened next.
        </p>
        <p className="mt-2 max-w-2xl font-sans text-sm leading-relaxed text-muted-foreground">
          This is the record to judge later. A good decision can still lose money; a bad one can still get lucky.
        </p>
      </div>

      {decisions.length === 0 ? (
        <div className="product-panel p-5 sm:p-6">
          <p className="font-sans text-sm text-foreground/85">
            No decisions recorded yet.
          </p>
          <p className="mt-1 font-sans text-xs leading-relaxed text-muted-foreground">
            Your first call will appear here after you review a change and decide what to do.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {decisions.map((d) => (
          <div key={d.id} className="product-panel p-5 sm:p-6">
            <div className="min-w-0 flex-1 space-y-3">
              <div className="flex items-start justify-between gap-4">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className={`h-1.5 w-1.5 rounded-full shrink-0 ${BUCKET_DOT[d.bucket] ?? "bg-border"}`} />
                  <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-foreground/70">
                    {BUCKET_LABEL[d.bucket] ?? d.bucket}
                  </span>
                  {d.decided_at && (
                    <span className="font-mono text-[10px] text-muted-foreground/70">
                      {new Date(d.decided_at).toLocaleDateString()}
                    </span>
                  )}
                </div>
                {!d.resolved && (
                  <span className="font-mono text-[10px] text-primary/70 text-right">
                    {d.next_test_days != null ? `Open · revisit in ${d.next_test_days}d` : "Open"}
                  </span>
                )}
                {d.resolved && (
                  <span className="font-mono text-[10px] text-muted-foreground/70 text-right">
                    Resolved
                  </span>
                )}
              </div>

              <p className="font-display text-[1.2rem] italic leading-snug text-foreground">
                {sentenceCase(d.verdict)}
              </p>

              {d.bet_text && (
                <div className="border-l-2 border-border/70 pl-3">
                  <p className="font-mono text-[9px] uppercase tracking-[0.16em] text-muted-foreground">
                    What you expected
                  </p>
                  <p className="mt-1 font-sans text-[13px] leading-relaxed text-foreground/80">
                    {d.bet_text}
                  </p>
                </div>
              )}

              {d.resolved && d.read && (
                <div className="border-l-2 border-primary/30 pl-3">
                  <p className="font-mono text-[9px] uppercase tracking-[0.16em] text-primary/70">
                    Later read
                  </p>
                  <p className="mt-1 font-sans text-[13px] leading-relaxed text-foreground/85">
                    {d.read}
                  </p>
                </div>
              )}
            </div>
          </div>
          ))}
        </div>
      )}
    </section>
  );
}
