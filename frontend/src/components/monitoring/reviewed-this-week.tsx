"use client";

import { useState } from "react";
import type { ReviewedItem } from "@/types";

interface Props {
  items: ReviewedItem[];
  className?: string;
}

function timeAgo(iso: string | null | undefined): string {
  if (!iso) return "";
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
 * Adjacency evidence surface: news items the LLM relevance filter looked at
 * and decided not to alert on, with the sentence it wrote to explain each
 * drop. Silence only feels informed when the reviewed-but-dropped items are
 * visible, so this block sits under the events list on the position tab.
 */
export function ReviewedThisWeek({ items, className = "" }: Props) {
  const [showAll, setShowAll] = useState(false);
  if (!items || items.length === 0) return null;
  const visibleItems = showAll ? items : items.slice(0, 3);

  return (
    <section className={`border border-border/50 bg-card/50 px-4 py-3.5 space-y-3 ${className}`}>
      <div className="space-y-1">
        <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
          Checked, no decision needed
        </p>
        <p className="font-sans text-xs text-muted-foreground/80 leading-relaxed">
          PenKeep checked these items against your written case. None directly
          tested it.
        </p>
      </div>

      <ul className="space-y-4">
        {visibleItems.map((item, i) => {
          const when = timeAgo(item.published_at);
          const meta = [item.source_label, when].filter(Boolean).join(" · ");
          const content = (
            <>
              <p className="font-sans text-sm text-foreground leading-snug">
                {item.headline}
              </p>
              {meta && (
                <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground/70 mt-1">
                  {meta}
                </p>
              )}
              <p className="font-sans text-xs text-muted-foreground/90 mt-1.5 leading-relaxed">
                {item.reason.length > 160 ? `${item.reason.slice(0, 160)}…` : item.reason}
              </p>
            </>
          );
          return (
            <li key={`${item.ticker}-${i}`} className="border-l-2 border-border/60 pl-3">
              {item.url ? (
                <a
                  href={item.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block hover:opacity-90 transition-opacity"
                >
                  {content}
                </a>
              ) : (
                content
              )}
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
