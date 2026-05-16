"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

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
    apiFetch("/api/onboarding/banner")
      .then((r) => r.json())
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

  const bgColor =
    banner_type === "first_reason_monitoring"
      ? "bg-emerald-50 border-emerald-200"
      : "bg-amber-50 border-amber-200";

  const textColor =
    banner_type === "first_reason_monitoring"
      ? "text-emerald-800"
      : "text-amber-800";

  const actionColor =
    banner_type === "first_reason_monitoring"
      ? "text-emerald-700 hover:text-emerald-900"
      : "text-amber-700 hover:text-amber-900";

  return (
    <div className={`rounded-lg border px-5 py-4 flex items-center justify-between gap-4 ${bgColor}`}>
      <p className={`text-sm font-medium ${textColor}`}>{message}</p>
      <div className="flex items-center gap-3 shrink-0">
        {actionLabel && banner_type !== "first_reason_monitoring" && (
          <Link href={actionHref} className={`text-sm font-semibold ${actionColor} whitespace-nowrap`}>
            {actionLabel}
          </Link>
        )}
        <button
          onClick={() => setDismissed(true)}
          className="text-stone-400 hover:text-stone-600 text-lg leading-none"
          aria-label="Dismiss"
        >
          ×
        </button>
      </div>
    </div>
  );
}
