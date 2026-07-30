"use client";

import useSWR from "swr";
import { fetcher } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import type { PriceHistoryEvent, PriceHistoryResponse } from "@/types";

/**
 * The life of the decision, drawn: daily closes since the written case was
 * recorded, with penKeep's monitoring events marked on the line. Deliberately
 * quiet — one muted line, no axes, no numbers, no red/green mood fill. The
 * question it answers is "when the price moved, did my reason move?"
 */

// Strongest signal wins when several events share a day.
const DOT_RANK: Record<string, number> = { red: 3, amber: 2, emerald: 1 };
const DOT_CLASS: Record<string, string> = {
  red: "bg-red-500",
  amber: "bg-amber-400",
  emerald: "bg-emerald-500",
};

function dotTone(event: PriceHistoryEvent): "red" | "amber" | "emerald" | null {
  if (event.severity === "thesis_breaking") return "red";
  if (event.verdict === "supports") return "emerald";
  if (event.verdict === "threatens" || event.verdict === "review" || event.severity === "warning") {
    return "amber";
  }
  return null; // neutral/info background evidence stays off the chart
}

interface PriceSparklineProps {
  holdingId: string;
  className?: string;
}

export function PriceSparkline({ holdingId, className = "" }: PriceSparklineProps) {
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
  const dotByIndex = new Map<number, "red" | "amber" | "emerald">();
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
    if (!existing || DOT_RANK[tone] > DOT_RANK[existing]) {
      dotByIndex.set(index, tone);
    }
  }

  const avgCostVisible =
    data.average_cost != null && data.average_cost >= min && data.average_cost <= max;
  const lastClose = closes[closes.length - 1];

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
        {[...dotByIndex.entries()].map(([index, tone]) => (
          <span
            key={index}
            className={`absolute h-[7px] w-[7px] -translate-x-1/2 -translate-y-1/2 rounded-full ring-2 ring-background ${DOT_CLASS[tone]}`}
            style={{ left: `${xFor(index)}%`, top: `${yFor(data.points[index].close)}%` }}
          />
        ))}
        {/* Current position marker */}
        <span
          aria-hidden
          className="absolute h-[5px] w-[5px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-foreground/60"
          style={{ left: "100%", top: `${yFor(lastClose)}%` }}
        />
      </div>
      <p className="mt-1.5 font-mono text-[9px] uppercase tracking-[0.14em] text-muted-foreground/60">
        {data.thesis_anchored ? `Since your case · ${formatDate(data.start_date)}` : "Last 30 days"}
        {avgCostVisible && <span className="ml-2 normal-case tracking-normal">– – your avg cost</span>}
      </p>
    </div>
  );
}
