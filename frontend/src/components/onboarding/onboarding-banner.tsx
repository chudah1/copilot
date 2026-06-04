"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { OnboardingState } from "@/types";

interface OnboardingBannerData {
  show: boolean;
  banner_type: string | null;
  message: string | null;
  holdings_count: number;
  reasons_count: number;
  suggested_holding: {
    id: string;
    ticker: string;
    name: string;
  } | null;
}

function onboardingBannerCopy(args: {
  bannerType: string | null;
  holdingsCount: number;
  reasonsCount: number;
  ticker: string | null;
  investorProfile: "thesis_driven" | "hearsay_driven" | null;
}) {
  const { bannerType, holdingsCount, reasonsCount, ticker, investorProfile } = args;
  const writeWord = investorProfile === "hearsay_driven" ? "reason" : "thesis";

  if (bannerType === "start_first_reason") {
    return {
      body: `Start with ${ticker ?? "your largest position"} so monitoring has one clear ${writeWord} to track.`,
    };
  }

  if (bannerType === "first_reason_monitoring") {
    return {
      body:
        investorProfile === "hearsay_driven"
          ? "Your first reason is live. We'll stay quiet unless the story shifts."
          : "Your first thesis is live. We'll stay quiet unless the evidence shifts.",
    };
  }

  if (bannerType === "add_more_reasons") {
    const remaining = Math.max(holdingsCount - reasonsCount, 0);
    return {
      body: `${remaining} ${remaining === 1 ? "position still needs" : "positions still need"} a written ${writeWord}. Next up: ${ticker ?? "your next holding"}.`,
    };
  }

  return {
    body: null,
  };
}

export function OnboardingBanner({ onVisibilityChange }: { onVisibilityChange?: (visible: boolean) => void }) {
  const [banner, setBanner] = useState<OnboardingBannerData | null>(null);
  const [dismissed, setDismissed] = useState(false);
  const [onboardingState, setOnboardingState] = useState<OnboardingState | null>(null);

  useEffect(() => {
    api.get<OnboardingBannerData>("/api/onboarding/banner")
      .then(setBanner)
      .catch(() => null);
    api.get<OnboardingState>("/api/onboarding/state")
      .then(setOnboardingState)
      .catch(() => null);
  }, []);

  const visible = Boolean(banner?.show && !dismissed);
  useEffect(() => { onVisibilityChange?.(visible); }, [visible, onVisibilityChange]);

  if (!banner || !banner.show || dismissed) return null;

  const { banner_type, message, suggested_holding } = banner;

  const actionHref =
    suggested_holding
      ? `/dashboard/positions/${suggested_holding.ticker}`
      : "/dashboard";

  const investorProfile = onboardingState?.investor_profile ?? null;
  const bannerCopy = onboardingBannerCopy({
    bannerType: banner_type,
    holdingsCount: banner.holdings_count,
    reasonsCount: banner.reasons_count,
    ticker: suggested_holding?.ticker ?? null,
    investorProfile,
  });

  const actionLabel =
    banner_type === "start_first_reason"
      ? investorProfile === "hearsay_driven"
        ? `Start with ${suggested_holding?.ticker ?? "your largest position"} →`
        : `Start with ${suggested_holding?.ticker ?? "your largest position"} →`
      : banner_type === "add_more_reasons"
      ? investorProfile === "hearsay_driven"
        ? `Write ${suggested_holding?.ticker ?? "the next reason"} →`
        : `Write ${suggested_holding?.ticker ?? "the next thesis"} →`
      : null;

  return (
    <div className="flex items-center justify-between gap-4 border border-amber-400/30 bg-amber-50 px-5 py-3">
      <p className="font-sans text-sm leading-snug text-amber-900">{bannerCopy.body ?? message}</p>
      <div className="flex items-center gap-4 shrink-0">
        {actionLabel && (
          <Link
            href={actionHref}
            className="font-mono text-[10px] uppercase tracking-[0.15em] whitespace-nowrap text-amber-900 hover:text-primary transition-colors"
          >
            {actionLabel}
          </Link>
        )}
        <button
          onClick={() => setDismissed(true)}
          className="text-muted-foreground hover:text-foreground text-sm leading-none transition-colors"
          aria-label="Dismiss"
        >
          ✕
        </button>
      </div>
    </div>
  );
}
