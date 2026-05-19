"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

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

export function OnboardingBanner() {
  const [banner, setBanner] = useState<OnboardingBannerData | null>(null);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    api.get<OnboardingBannerData>("/api/onboarding/banner")
      .then(setBanner)
      .catch(() => null);
  }, []);

  if (!banner || !banner.show || dismissed) return null;

  const { banner_type, message, suggested_holding } = banner;

  const actionHref =
    banner_type === "add_more_reasons" && suggested_holding
      ? `/dashboard/positions/${suggested_holding.ticker}`
      : "/dashboard";

  const actionLabel =
    banner_type === "start_first_reason"
      ? "Pick a holding →"
      : banner_type === "add_more_reasons"
      ? `Add reason for ${suggested_holding?.ticker ?? "next holding"} →`
      : null;

  const isSuccess = banner_type === "first_reason_monitoring";

  return (
    <div className={`flex items-center justify-between gap-4 rounded border px-4 py-3 ${
      isSuccess ? "border-emerald-500/20 bg-emerald-500/10" : "border-amber-500/20 bg-amber-500/10"
    }`}>
      <p className={`text-sm ${isSuccess ? "text-emerald-300/90" : "text-amber-300/90"}`}>{message}</p>
      <div className="flex items-center gap-3 shrink-0">
        {actionLabel && !isSuccess && (
          <Link href={actionHref} className="text-xs font-mono uppercase tracking-wide text-amber-700/80 hover:text-amber-700 whitespace-nowrap transition-colors">
            {actionLabel}
          </Link>
        )}
        <button
          onClick={() => setDismissed(true)}
          className="text-muted-foreground hover:text-foreground/70 text-lg leading-none transition-colors"
          aria-label="Dismiss"
        >
          ×
        </button>
      </div>
    </div>
  );
}
