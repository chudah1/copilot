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

  const actionLabel =
    banner_type === "start_first_reason"
      ? investorProfile === "hearsay_driven"
        ? `Turn the story on ${suggested_holding?.ticker ?? "your largest position"} into a reason →`
        : `Start with ${suggested_holding?.ticker ?? "your largest position"} →`
      : banner_type === "add_more_reasons"
      ? investorProfile === "hearsay_driven"
        ? `Write the real reason for ${suggested_holding?.ticker ?? "your next position"} →`
        : `Write down why you hold ${suggested_holding?.ticker ?? "your next position"} →`
      : null;

  return (
    <div className="flex items-center justify-between gap-4 border border-amber-400/30 bg-amber-50 px-5 py-3">
      <p className="font-sans text-sm leading-snug text-amber-900">{message}</p>
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
