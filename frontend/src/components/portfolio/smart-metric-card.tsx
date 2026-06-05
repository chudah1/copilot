"use client";

import { Card, CardContent } from "@/components/ui/card";

interface SmartMetricCardProps {
  label: string;
  value: string;
  verdict: string;
  color: "green" | "amber" | "neutral";
  trend?: { previous: string; improving: boolean } | null;
}

const COLOR_MAP = {
  green: {
    border: "border-emerald-500/30",
    label: "text-emerald-700",
    value: "text-emerald-700",
    verdict: "text-emerald-700/80",
  },
  amber: {
    border: "border-amber-500/30",
    label: "text-amber-700",
    value: "text-amber-700",
    verdict: "text-amber-700/80",
  },
  neutral: {
    border: "border-border",
    label: "text-muted-foreground",
    value: "text-foreground",
    verdict: "text-muted-foreground",
  },
};

export function SmartMetricCard({ label, value, verdict, color, trend }: SmartMetricCardProps) {
  const c = COLOR_MAP[color];
  const currentValue = Number.parseFloat(value.replace(/[^0-9.-]/g, ""));
  const previousValue = trend ? Number.parseFloat(trend.previous.replace(/[^0-9.-]/g, "")) : Number.NaN;
  const hasNumericTrend = Number.isFinite(currentValue) && Number.isFinite(previousValue);
  const trendArrow = !hasNumericTrend ? null : currentValue > previousValue ? "↑" : currentValue < previousValue ? "↓" : "→";

  return (
    <Card className={c.border}>
      <CardContent className="pt-4 pb-3 px-4">
        <p className={`text-[11px] font-semibold uppercase tracking-wide ${c.label}`}>{label}</p>
        <p className={`text-2xl font-bold mt-1 ${c.value}`}>{value}</p>
        <p className={`text-xs mt-1 ${c.verdict}`}>{verdict}</p>
        {trend && trend.previous !== value && (
          <p className={`text-[11px] mt-1.5 ${trend.improving ? "text-emerald-700" : "text-red-600"}`}>
            {trendArrow ?? (trend.improving ? "↑" : "↓")} from {trend.previous} last week
          </p>
        )}
      </CardContent>
    </Card>
  );
}
