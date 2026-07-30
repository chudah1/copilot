"use client";

import { useState } from "react";
import useSWR from "swr";
import { fetcher } from "@/lib/api";
import { formatCurrency, formatDate } from "@/lib/utils";
import type { PriceHistoryEvent, PriceHistoryResponse } from "@/types";

/**
 * The life of the decision, drawn: daily closes since the written case was
 * recorded, with penKeep's monitoring events marked on the line. Deliberately
 * quiet — one muted line, no axes, no numbers, no red/green mood fill. The
 * question it answers is "when the price moved, did my reason move?"
 */

// Strongest signal wins when several events share a day.
const DOT_RANK: Record<string, number> = { red: 2, amber: 1 };
const DOT_CLASS: Record<string, string> = {
  red: "bg-red-500",
  amber: "bg-amber-400",
};

function dotTone(event: PriceHistoryEvent): "red" | "amber" | null {
  if (event.severity === "thesis_breaking") return "red";
  if (event.verdict === "threatens" || event.verdict === "review" || event.severity === "warning") {
    return "amber";
  }
  return null; // supporting and background evidence stay off this pressure chart
}

interface PriceSparklineProps {
  holdingId: string;
  className?: string;
}

export function PriceSparkline({ holdingId, className = "" }: PriceSparklineProps) {
  const [activeEventIndex, setActiveEventIndex] = useState<number | null>(null);
  const { data } = useSWR<PriceHistoryResponse>(
    `/api/portfolio/holdings/${holdingId}/price-history`,
    fetcher,
    { revalidateOnFocus: false, dedupingInterval: 60 * 60 * 1000 },
  );

  if (!data || data.points.length < 2) return null;

  const closes = data.points.map((p) => p.close);
  let min = Math.min(...closes);
  let max = Math.max(...closes);
  if (max === min) {
    max += 1;
    min -= 1;
  }
  const pad = (max - min) * 0.12;
  min -= pad;
  max += pad;

  const xFor = (index: number) => (index / (data.points.length - 1)) * 100;
  const yFor = (close: number) => 100 - ((close - min) / (max - min)) * 100;

  const path = data.points
    .map((point, index) => `${index === 0 ? "M" : "L"}${xFor(index).toFixed(2)},${yFor(point.close).toFixed(2)}`)
    .join(" ");

  // Map each event to the last trading day on/before it; strongest tone wins.
  const dotByIndex = new Map<number, { tone: "red" | "amber"; event: PriceHistoryEvent }>();
  for (const event of data.events) {
    const tone = dotTone(event);
    if (!tone) continue;
    let index = -1;
    for (let i = data.points.length - 1; i >= 0; i -= 1) {
      if (data.points[i].date <= event.date) {
        index = i;
        break;
      }
    }
    if (index < 0) continue;
    const existing = dotByIndex.get(index);
    if (!existing || DOT_RANK[tone] > DOT_RANK[existing.tone]) {
      dotByIndex.set(index, { tone, event });
    }
  }

  const avgCostVisible =
    data.average_cost != null && data.average_cost >= min && data.average_cost <= max;
  const firstClose = closes[0];
  const lastClose = closes[closes.length - 1];
  const activeEvent =
    activeEventIndex == null ? null : dotByIndex.get(activeEventIndex)?.event ?? null;

  return (
    <div className={className}>
      <div className="relative h-12 w-full">
        <svg
          viewBox="0 0 100 100"
          preserveAspectRatio="none"
          className="absolute inset-0 h-full w-full overflow-visible text-muted-foreground/45"
          aria-hidden
        >
          <path d={path} fill="none" stroke="currentColor" strokeWidth={1.4} vectorEffect="non-scaling-stroke" />
        </svg>
        {avgCostVisible && (
          <div
            aria-hidden
            className="absolute inset-x-0 border-t border-dashed border-muted-foreground/30"
            style={{ top: `${yFor(data.average_cost!)}%` }}
          />
        )}
        {[...dotByIndex.entries()].map(([index, marker]) => (
          <button
            key={index}
            type="button"
            aria-label={`${formatDate(marker.event.date)}: ${marker.event.title}`}
            aria-pressed={activeEventIndex === index}
            title={`${formatDate(marker.event.date)} — ${marker.event.title}`}
            onClick={() => setActiveEventIndex((current) => current === index ? null : index)}
            onFocus={() => setActiveEventIndex(index)}
            className="absolute z-10 flex h-5 w-5 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
            style={{ left: `${xFor(index)}%`, top: `${yFor(data.points[index].close)}%` }}
          >
            <span className={`h-[7px] w-[7px] rounded-full ring-2 ring-background ${DOT_CLASS[marker.tone]}`} />
          </button>
        ))}
        {/* Current position marker */}
        <span
          aria-hidden
          className="absolute h-[5px] w-[5px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-foreground/60"
          style={{ left: "100%", top: `${yFor(lastClose)}%` }}
        />
      </div>
      <div className="mt-1.5 flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
        <p className="font-mono text-[9px] uppercase tracking-[0.12em] text-muted-foreground/70">
          {data.thesis_anchored
            ? `Price since you wrote this case · ${formatDate(data.start_date)}`
            : "Price · last 30 days"}
        </p>
        <p className="font-mono text-[9px] tabular-nums text-muted-foreground/70">
          {formatCurrency(firstClose, data.currency)} → {formatCurrency(lastClose, data.currency)}
        </p>
      </div>
      {(dotByIndex.size > 0 || avgCostVisible) && (
        <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 font-sans text-[10px] text-muted-foreground/70">
          {dotByIndex.size > 0 && (
            <span className="inline-flex items-center gap-1.5">
              <span className="h-1.5 w-1.5 rounded-full bg-amber-400" />
              Evidence that tested your case
            </span>
          )}
          {avgCostVisible && (
            <span className="inline-flex items-center gap-1.5">
              <span className="w-3 border-t border-dashed border-muted-foreground/50" />
              Your average cost
            </span>
          )}
        </div>
      )}
      {activeEvent && (
        <div role="status" className="mt-2 border-l-2 border-amber-400/70 pl-2.5">
          <p className="font-mono text-[9px] uppercase tracking-[0.12em] text-muted-foreground">
            Evidence reviewed · {formatDate(activeEvent.date)}
          </p>
          <p className="mt-0.5 line-clamp-2 font-sans text-[11px] leading-relaxed text-foreground/85">
            {activeEvent.title}
          </p>
        </div>
      )}
    </div>
  );
}
