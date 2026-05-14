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
    border: "border-emerald-200",
    label: "text-emerald-800",
    value: "text-emerald-800",
    verdict: "text-emerald-700",
  },
  amber: {
    border: "border-amber-200",
    label: "text-amber-800",
    value: "text-amber-800",
    verdict: "text-amber-700",
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

  return (
    <Card className={c.border}>
      <CardContent className="pt-4 pb-3 px-4">
        <p className={`text-[11px] font-semibold uppercase tracking-wide ${c.label}`}>{label}</p>
        <p className={`text-2xl font-bold mt-1 ${c.value}`}>{value}</p>
        <p className={`text-xs mt-1 ${c.verdict}`}>{verdict}</p>
        {trend && (
          <p className={`text-[11px] mt-1.5 ${trend.improving ? "text-emerald-600" : "text-red-500"}`}>
            {trend.improving ? "↓" : "↑"} was {trend.previous} last week
          </p>
        )}
      </CardContent>
    </Card>
  );
}
