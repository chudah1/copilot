"use client";

import { useState } from "react";
import type { SupportingItem } from "@/types";

interface Props {
  items: SupportingItem[];
  className?: string;
}

function timeAgo(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const diffSec = Math.max(0, Math.floor((Date.now() - then) / 1000));
  if (diffSec < 3600) return "just now";
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`;
  const days = Math.floor(diffSec / 86400);
  if (days <= 1) return "yesterday";
  return `${days}d ago`;
}

/**
 * Supporting evidence — signals the pipeline judged as validating the
 * thesis rather than threatening it. Rendered distinctly from the events
 * list so a positive read never gets mixed in with threat cards, which is
 * the design point: users should sometimes feel "my thesis was validated"
 * rather than only "my thesis is under attack."
 *
 * Intentionally quiet visually. The whole feature loses its emotional
 * balance if it turns into a green highlight reel.
 */
export function HeldUpThisWeek({ items, className = "" }: Props) {
  const [showAll, setShowAll] = useState(false);
  if (!items || items.length === 0) return null;
  const visibleItems = showAll ? items : items.slice(0, 3);

  return (
    <section className={`product-panel border-emerald-500/25 bg-emerald-500/5 px-4 py-4 sm:px-5 sm:py-5 space-y-4 ${className}`}>
      <div className="space-y-1">
        <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-emerald-700">
          Holding up
        </p>
        <p className="font-sans text-sm text-foreground/80 leading-relaxed">
          Recent evidence that supported part of your view.
        </p>
      </div>

      <ul className="space-y-3">
        {visibleItems.map((item) => {
          const meta = [item.assumption_label, timeAgo(item.created_at)]
            .filter(Boolean)
            .join(" · ");
          return (
            <li key={item.event_id} className="border border-border/60 bg-background/70 px-3 py-3 space-y-1.5">
              {meta && (
                <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground/70">
                  {meta}
                </p>
              )}
              <p className="font-sans text-sm text-foreground leading-snug">
                {item.title}
              </p>
            </li>
          );
        })}
      </ul>
      {items.length > 3 && (
        <button
          onClick={() => setShowAll((current) => !current)}
          className="font-mono text-[10px] uppercase tracking-[0.15em] text-primary hover:text-primary/75"
        >
          {showAll ? "Show less" : `See all ${items.length}`}
        </button>
      )}
    </section>
  );
}
