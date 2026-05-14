"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface Props {
  title: string;
  breakdown: Record<string, number>;
}

const COLORS = [
  "bg-violet-600",
  "bg-violet-400",
  "bg-indigo-500",
  "bg-blue-500",
  "bg-blue-400",
  "bg-sky-400",
  "bg-cyan-400",
  "bg-teal-400",
  "bg-emerald-400",
  "bg-stone-400",
];

export function AllocationChart({ title, breakdown }: Props) {
  const sorted = Object.entries(breakdown).sort(([, a], [, b]) => b - a);
  const warning = sorted.find(([, pct]) => pct > 40);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Stacked bar */}
        <div className="flex h-7 w-full overflow-hidden rounded-md">
          {sorted.map(([label, pct], i) => (
            <div
              key={label}
              className={`${COLORS[i % COLORS.length]} flex items-center justify-center overflow-hidden`}
              style={{ width: `${Math.max(pct, 2)}%` }}
              title={`${label}: ${pct}%`}
            >
              {pct >= 10 && (
                <span className="truncate px-1 text-[10px] font-medium text-white">
                  {label} {pct}%
                </span>
              )}
            </div>
          ))}
        </div>

        {/* Legend for small segments */}
        <div className="flex flex-wrap gap-x-4 gap-y-1">
          {sorted.map(([label, pct], i) => (
            <div key={label} className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <span className={`inline-block h-2.5 w-2.5 rounded-sm ${COLORS[i % COLORS.length]}`} />
              <span>{label}</span>
              <span className="font-medium text-foreground">{pct}%</span>
            </div>
          ))}
        </div>

        {warning && (
          <p className="text-xs text-amber-700">
            {warning[0]} is {warning[1]}% — high concentration
          </p>
        )}
      </CardContent>
    </Card>
  );
}
