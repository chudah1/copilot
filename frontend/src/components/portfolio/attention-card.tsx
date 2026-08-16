"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { formatAssumptionLabel } from "@/lib/assumption-label";
import { tightenInvestorCopy } from "@/lib/investor-language";
import { positionMonitoringHref } from "@/lib/position-links";
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
      headline: `${target} needs your read.`,
      detail:
        pulseReason ||
        (investorProfile === "hearsay_driven"
          ? "This reason now needs a clear call."
          : investorProfile === "thesis_driven"
            ? "This thesis now needs a clear call."
            : "This position now needs a clear call."),
    };
  }

  return {
    eyebrow: "Watch",
    headline: `${target} is being tested.`,
    detail:
      pulseReason ||
      (investorProfile === "hearsay_driven"
        ? "Nothing looks broken yet, but this reason is under pressure."
        : investorProfile === "thesis_driven"
          ? "Nothing looks broken yet, but this thesis is being tested."
          : "Nothing looks broken yet, but this position is under pressure."),
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
  const toneClasses = isReview
    ? {
        panel: "border-red-500/20 bg-[linear-gradient(180deg,rgba(239,68,68,0.08),rgba(255,255,255,0.95))]",
        chip: "border-red-500/20 bg-red-500/8 text-red-700",
        footer: "text-red-600/80",
      }
    : {
        panel: "border-amber-500/20 bg-[linear-gradient(180deg,rgba(245,158,11,0.08),rgba(255,255,255,0.95))]",
        chip: "border-amber-500/20 bg-amber-500/8 text-amber-800",
        footer: "text-amber-700/85",
      };
  return (
    <motion.div
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.25, delay: index * 0.06 }}
    >
      <Link href={positionMonitoringHref(holding.ticker)}>
        <div
          className={`product-panel w-64 shrink-0 border p-4 space-y-3 transition-all hover:-translate-y-0.5 hover:shadow-[0_10px_28px_-14px_rgba(52,40,24,0.28)] cursor-pointer ${toneClasses.panel}`}
        >
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0 space-y-1">
              <span className="font-mono text-[11px] font-semibold tracking-[0.2em] text-primary">
                {cleanTicker(holding.ticker)}
              </span>
              <p className="truncate font-sans text-[11px] text-muted-foreground">
                {holding.name}
              </p>
            </div>
            <span className={`shrink-0 border px-2 py-1 font-mono text-[10px] uppercase tracking-[0.12em] ${toneClasses.chip}`}>
              {copy.eyebrow}
            </span>
          </div>
          <div className="space-y-1.5">
            <p className="font-sans text-[12px] text-foreground/92 leading-relaxed line-clamp-2">
              {copy.headline}
            </p>
            <p className="font-sans text-[11px] text-muted-foreground leading-relaxed line-clamp-3">
              {latestEventSummary ?? copy.detail}
            </p>
          </div>
          {pulseReason && latestEventSummary && pulseReason !== latestEventSummary && (
            <div className="border-t border-border/50 pt-3">
              <p className="font-mono text-[10px] uppercase tracking-[0.12em] text-foreground/55">
                Why now
              </p>
              <p className="mt-1 font-sans text-[11px] text-foreground/70 leading-relaxed line-clamp-2">
                {pulseReason}
              </p>
            </div>
          )}
          <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border/50 pt-3">
            {pulse.days_since_thesis_update != null ? (
              <p className="font-mono text-[10px] text-muted-foreground/60">
                {formatThesisUpdateAge(pulse.days_since_thesis_update)}
              </p>
            ) : (
              <span />
            )}
            {pulse.unresolved_event_count > 0 ? (
              <p className={`font-mono text-[10px] ${toneClasses.footer}`}>
                {pulse.unresolved_event_count} open call{pulse.unresolved_event_count !== 1 ? "s" : ""}
              </p>
            ) : pulse.last_checked_at ? (
              <p className="font-mono text-[10px] text-muted-foreground/60">
                Checked recently
              </p>
            ) : null}
          </div>
          <div className="flex items-center justify-end">
            <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-primary/75">
              Open review →
            </span>
          </div>
        </div>
      </Link>
    </motion.div>
  );
}
