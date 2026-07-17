"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { formatAssumptionLabel } from "@/lib/assumption-label";
import { tightenInvestorCopy } from "@/lib/investor-language";
import { cleanTicker } from "./position-card";
import type { Holding, HoldingPulse } from "@/types";

interface AttentionCardProps {
  holding: Holding;
  pulse: HoldingPulse;
  investorProfile?: "thesis_driven" | "hearsay_driven" | null;
  index: number;
}

function assumptionHeadline(
  assumptionLabel: string | null | undefined,
  investorProfile?: "thesis_driven" | "hearsay_driven" | null,
) {
  return formatAssumptionLabel(assumptionLabel, investorProfile, {
    maxLength: 52,
    sentenceCaseFallback: true,
  });
}

function attentionCopy(
  pulse: HoldingPulse,
  investorProfile?: "thesis_driven" | "hearsay_driven" | null,
) {
  const isReview = pulse.pulse_status === "review";
  const target = assumptionHeadline(pulse.assumption_label, investorProfile);
  const pulseReason = tightenInvestorCopy(pulse.reason, investorProfile);
  if (isReview) {
    return {
      eyebrow: "Review",
      headline: `${target} may have changed.`,
      detail:
        pulseReason ||
        (investorProfile === "hearsay_driven"
          ? "This story now needs a clear call."
          : "This thesis now needs a clear call."),
    };
  }

  return {
    eyebrow: "Watch",
    headline: `${target} is under pressure.`,
    detail:
      pulseReason ||
      (investorProfile === "hearsay_driven"
        ? "Nothing looks broken yet, but the story needs a closer look."
        : "Nothing looks broken yet, but this thesis needs a closer look."),
  };
}

function formatThesisUpdateAge(days: number) {
  if (days <= 0) return "Updated today";
  if (days === 1) return "Updated yesterday";
  return `Updated ${days}d ago`;
}

export function AttentionCard({ holding, pulse, investorProfile, index }: AttentionCardProps) {
  const isReview = pulse.pulse_status === "review";
  const copy = attentionCopy(pulse, investorProfile);
  const pulseReason = tightenInvestorCopy(pulse.reason, investorProfile);
  const latestEventSummary = pulse.latest_event_summary
    ? tightenInvestorCopy(pulse.latest_event_summary, investorProfile)
    : null;
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
              {copy.eyebrow}
            </span>
          </div>
          <div className="space-y-1">
            <p className="font-sans text-[11px] text-foreground/90 leading-relaxed line-clamp-2">
              {copy.headline}
            </p>
            <p className="font-sans text-[11px] text-muted-foreground leading-relaxed line-clamp-3">
              {latestEventSummary ?? copy.detail}
            </p>
          </div>
          {pulseReason && latestEventSummary && pulseReason !== latestEventSummary && (
            <p className="font-mono text-[10px] text-foreground/65 leading-relaxed line-clamp-2">
              Why now: {pulseReason}
            </p>
          )}
          {pulse.days_since_thesis_update != null && (
            <p className="font-mono text-[10px] text-muted-foreground/60">
              {formatThesisUpdateAge(pulse.days_since_thesis_update)}
            </p>
          )}
          {pulse.unresolved_event_count > 0 && (
            <p className={`font-mono text-[10px] ${isReview ? "text-red-600/80" : "text-amber-700/80"}`}>
              {pulse.unresolved_event_count} unresolved item{pulse.unresolved_event_count !== 1 ? "s" : ""}
            </p>
          )}
          {!pulse.unresolved_event_count && pulse.last_checked_at && (
            <p className="font-mono text-[10px] text-muted-foreground/60">
              Checked recently
            </p>
          )}
        </div>
      </Link>
    </motion.div>
  );
}
