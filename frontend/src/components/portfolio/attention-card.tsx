"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { cleanTicker } from "./position-card";
import type { Holding, HoldingPulse } from "@/types";

interface AttentionCardProps {
  holding: Holding;
  pulse: HoldingPulse;
  index: number;
}

export function AttentionCard({ holding, pulse, index }: AttentionCardProps) {
  const isReview = pulse.pulse_status === "review";
  return (
    <motion.div
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.25, delay: index * 0.06 }}
    >
      <Link href={`/dashboard/positions/${holding.ticker}`}>
        <div className={`w-56 shrink-0 border bg-card p-4 space-y-2 transition-all hover:shadow-md cursor-pointer ${
          isReview
            ? "border-l-2 border-l-red-500 border-border hover:border-l-red-600"
            : "border-l-2 border-l-amber-400 border-border hover:border-l-amber-500"
        }`}>
          <div className="flex items-center justify-between">
            <span className="font-mono text-[11px] font-semibold tracking-[0.2em] text-primary">
              {cleanTicker(holding.ticker)}
            </span>
            <span className={`font-mono text-[10px] uppercase tracking-[0.12em] ${isReview ? "text-red-600" : "text-amber-700"}`}>
              {isReview ? "Review" : "Watch"}
            </span>
          </div>
          <p className="font-sans text-[11px] text-foreground/80 leading-relaxed line-clamp-3">
            {pulse.latest_event_summary ?? pulse.reason ?? "Monitoring event requires attention"}
          </p>
          {pulse.recent_event_count > 0 && (
            <p className="font-mono text-[10px] text-muted-foreground/70">
              {pulse.recent_event_count} recent event{pulse.recent_event_count !== 1 ? "s" : ""} →
            </p>
          )}
        </div>
      </Link>
    </motion.div>
  );
}
