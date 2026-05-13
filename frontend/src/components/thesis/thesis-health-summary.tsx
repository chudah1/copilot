"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { PortfolioSummary } from "@/types";

interface Props {
  summary: PortfolioSummary;
}

export function ThesisHealthSummary({ summary }: Props) {
  return (
    <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">Active Theses</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-2xl font-bold text-green-600">{summary.theses_active}</p>
          <p className="text-sm text-muted-foreground">{summary.holdings_count} total holdings</p>
        </CardContent>
      </Card>
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">Monitorable Coverage</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-2xl font-bold text-sky-600">{summary.monitorable_thesis_coverage_pct.toFixed(0)}%</p>
          <p className="text-sm text-muted-foreground">of portfolio value is meaningfully monitored</p>
        </CardContent>
      </Card>
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">Review Debt</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-2xl font-bold text-orange-500">{summary.theses_need_review}</p>
          <p className="text-sm text-muted-foreground">{summary.stale_theses_count} stale theses</p>
        </CardContent>
      </Card>
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">Unclear Holdings</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-2xl font-bold text-red-500">{summary.unmonitored_holdings_count}</p>
          <p className="text-sm text-muted-foreground">{summary.theses_missing} with no thesis at all</p>
        </CardContent>
      </Card>
    </div>
  );
}
