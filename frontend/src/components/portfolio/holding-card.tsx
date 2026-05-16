"use client";

import Link from "next/link";
import { formatCurrency, formatPercent } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Line, LineChart, ResponsiveContainer } from "recharts";
import type { Holding, Thesis, HoldingPulse, UpcomingEarnings } from "@/types";

interface Props {
  holding: Holding;
  thesis?: Thesis;
  pulse?: HoldingPulse;
  earnings?: UpcomingEarnings;
  onGenerateDraft?: () => void;
}

const PULSE_COLORS: Record<string, string> = {
  intact: "bg-emerald-500",
  watch: "bg-amber-500",
  review: "bg-red-500",
};

export function HoldingCard({ holding, thesis, pulse, earnings, onGenerateDraft }: Props) {
  const cost = holding.quantity * holding.average_cost_basis;
  const value = holding.current_value || 0;
  const pnl = value - cost;
  const pnlPct = cost > 0 ? (pnl / cost) * 100 : 0;
  
  const pulseStatus = pulse?.pulse_status ?? "intact";
  const hasThesis = !!thesis;
  
  // Mock sparkline data - in reality this would come from a price history endpoint
  const mockSparklineData = Array.from({length: 14}, () => holding.current_price ? holding.current_price * (1 + (Math.random() - 0.5) * 0.05) : 100);

  return (
    <Card className="overflow-hidden hover:shadow-md transition-shadow">
      <CardContent className="p-0">
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between p-5 gap-4">
          
          <div className="flex items-center gap-4 min-w-[200px]">
             <div className={`w-2 h-2 rounded-full ${hasThesis ? PULSE_COLORS[pulseStatus] : "bg-stone-300"}`} />
             <div>
               <Link href={`/dashboard/positions/${holding.ticker}`} className="text-lg font-semibold hover:underline">
                 {holding.ticker}
               </Link>
               <p className="text-sm text-muted-foreground line-clamp-1">{holding.name}</p>
             </div>
          </div>

          <div className="hidden md:block w-32 h-10 opacity-70">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={mockSparklineData.map((v, i) => ({ val: v, index: i }))}>
                <Line 
                  type="monotone" 
                  dataKey="val" 
                  stroke={pnl >= 0 ? "#10b981" : "#ef4444"} 
                  strokeWidth={2} 
                  dot={false} 
                  isAnimationActive={false} 
                />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="text-right min-w-[120px]">
             <p className="font-medium">{formatCurrency(value, holding.currency)}</p>
             <p className={`text-sm ${pnl >= 0 ? "text-emerald-600" : "text-red-600"}`}>
               {pnl >= 0 ? "+" : ""}{formatCurrency(pnl, holding.currency)} ({formatPercent(pnlPct)})
             </p>
          </div>
          
        </div>
        
        <div className="bg-stone-50/50 border-t px-5 py-3 flex items-center justify-between gap-3">
          {!hasThesis ? (
            <div className="flex items-center gap-3 flex-1 min-w-0">
              <span className="text-sm text-stone-500">No thesis recorded.</span>
              <button
                onClick={onGenerateDraft}
                className="text-sm text-emerald-600 font-medium hover:underline flex items-center gap-1"
              >
                ✨ 1-Click AI Draft
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-3 flex-1 min-w-0">
              <Badge variant="outline" className={
                pulseStatus === "review" ? "border-red-200 text-red-700 bg-red-50" :
                pulseStatus === "watch" ? "border-amber-200 text-amber-700 bg-amber-50" :
                "border-emerald-200 text-emerald-700 bg-emerald-50"
              }>
                {pulseStatus === "review" ? "Needs Review" : pulseStatus === "watch" ? "Watching" : "Thesis Intact"}
              </Badge>
              <p className="text-sm text-stone-600 line-clamp-1 flex-1 min-w-0">
                {thesis.why_own_it}
              </p>
            </div>
          )}
          {earnings && earnings.days_until <= 7 && (
            <Badge variant="outline" className="shrink-0 border-violet-200 text-violet-700 bg-violet-50 whitespace-nowrap">
              {earnings.days_until === 0
                ? "Earnings today"
                : earnings.days_until === 1
                ? "Earnings tomorrow"
                : `Earnings in ${earnings.days_until}d`}
            </Badge>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
