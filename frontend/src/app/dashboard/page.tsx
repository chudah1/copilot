"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { formatCurrency, formatPercent } from "@/lib/utils";
import { HoldingsTable } from "@/components/portfolio/holdings-table";
import { AllocationChart } from "@/components/portfolio/allocation-chart";
import { ThesisHealthSummary } from "@/components/thesis/thesis-health-summary";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { Holding, PortfolioSummary } from "@/types";

export default function DashboardPage() {
  const [holdings, setHoldings] = useState<Holding[]>([]);
  const [summary, setSummary] = useState<PortfolioSummary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const [h, s] = await Promise.all([
          api.get<Holding[]>("/api/portfolio/holdings"),
          api.get<PortfolioSummary>("/api/portfolio/summary"),
        ]);
        setHoldings(h);
        setSummary(s);
      } catch (err) {
        console.error("Failed to load portfolio", err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) return <p>Loading portfolio...</p>;

  if (holdings.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-20">
        <h2 className="text-xl font-semibold">No holdings yet</h2>
        <p className="text-muted-foreground">Connect your broker or add positions manually to get started.</p>
        <Link href="/connect">
          <Button>Connect Portfolio</Button>
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {summary && (
        <>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">Portfolio Value</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-bold">{formatCurrency(summary.total_value)}</p>
                <p className={`text-sm ${summary.total_pnl >= 0 ? "text-green-600" : "text-red-600"}`}>
                  {formatCurrency(summary.total_pnl)} ({formatPercent(summary.total_pnl_pct)})
                </p>
              </CardContent>
            </Card>
          </div>

          <ThesisHealthSummary summary={summary} />

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <AllocationChart title="Sector Allocation" breakdown={summary.sector_breakdown} />
            <AllocationChart title="Geography Allocation" breakdown={summary.geography_breakdown} />
          </div>
        </>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Holdings</CardTitle>
        </CardHeader>
        <CardContent>
          <HoldingsTable holdings={holdings} />
        </CardContent>
      </Card>
    </div>
  );
}
