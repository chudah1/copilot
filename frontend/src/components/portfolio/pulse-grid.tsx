"use client";

import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { positionDetailHref } from "@/lib/position-links";
import type { HoldingPulse } from "@/types";

const PULSE_DOT: Record<string, string> = {
  intact: "bg-emerald-500",
  watch: "bg-amber-400",
  review: "bg-red-500",
};

const PULSE_BG: Record<string, string> = {
  intact: "",
  watch: "bg-amber-50",
  review: "bg-red-50",
};

function timeAgo(days: number | null): string {
  if (days == null) return "";
  if (days === 0) return "today";
  if (days === 1) return "1d ago";
  if (days < 30) return `${days}d ago`;
  if (days < 365) return `${Math.floor(days / 30)}mo ago`;
  return `${Math.floor(days / 365)}y ago`;
}

export function PulseGrid({ pulses }: { pulses: HoldingPulse[] }) {
  if (pulses.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Portfolio Pulse</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            Add your first holding to start seeing your portfolio pulse.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Portfolio Pulse</CardTitle>
      </CardHeader>
      <CardContent className="space-y-0 divide-y">
        {pulses.map((pulse) => (
          <Link
            key={pulse.holding_id}
            href={positionDetailHref(pulse.ticker)}
            className={`flex items-center gap-3 px-1 py-3 transition-colors hover:bg-muted/50 first:pt-0 last:pb-0 ${PULSE_BG[pulse.pulse_status] ?? ""}`}
          >
            <span className={`h-2.5 w-2.5 flex-shrink-0 rounded-full ${PULSE_DOT[pulse.pulse_status] ?? "bg-gray-300"}`} />
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span className="font-semibold text-sm">{pulse.ticker}</span>
                <span className="text-xs text-muted-foreground truncate">{pulse.name}</span>
              </div>
              <p className="text-xs text-muted-foreground truncate">{pulse.reason}</p>
            </div>
            {pulse.has_thesis && pulse.days_since_thesis_update != null && (
              <span className="flex-shrink-0 text-xs text-muted-foreground">
                {timeAgo(pulse.days_since_thesis_update)}
              </span>
            )}
          </Link>
        ))}
      </CardContent>
    </Card>
  );
}
