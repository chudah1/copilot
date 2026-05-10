"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface Props {
  title: string;
  breakdown: Record<string, number>;
}

export function AllocationChart({ title, breakdown }: Props) {
  const sorted = Object.entries(breakdown).sort(([, a], [, b]) => b - a);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {sorted.map(([label, pct]) => (
          <div key={label}>
            <div className="flex justify-between text-sm">
              <span>{label}</span>
              <span className="text-muted-foreground">{pct}%</span>
            </div>
            <div className="h-2 rounded-full bg-muted">
              <div
                className={`h-2 rounded-full ${pct > 30 ? "bg-orange-500" : "bg-blue-500"}`}
                style={{ width: `${Math.min(pct, 100)}%` }}
              />
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
