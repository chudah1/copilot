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

  if (!decisions || decisions.length === 0) return null;

  return (
    <section className="space-y-4">
      <div className="product-panel product-panel-muted p-5 sm:p-6">
        <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground mb-0.5">
          Your calls
        </p>
        <p className="font-sans text-xs text-muted-foreground/70">
          Each decision you made on this position, and where it stands.
        </p>
      </div>

      <div className="space-y-3">
        {decisions.map((d) => (
          <div key={d.id} className="product-panel p-5 sm:p-6">
            <div className="min-w-0 flex-1 space-y-1">
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
                    {d.next_test_days != null ? `open · next test in ${d.next_test_days}d` : "open"}
                  </span>
                )}
              </div>
              {d.resolved && d.read ? (
                <p className="font-sans text-[13px] text-foreground/85 leading-relaxed pt-1">{d.read}</p>
              ) : d.bet_text ? (
                <p className="font-sans text-[13px] text-muted-foreground leading-relaxed line-clamp-2 pt-1">
                  {d.bet_text}
                </p>
              ) : null}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
