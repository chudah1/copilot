"use client";

import Link from "next/link";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { formatCurrency, formatPercent } from "@/lib/utils";
import type { Holding, Thesis, HoldingPulse } from "@/types";

interface Props {
  holdings: Holding[];
  currentThesesByHolding: Record<string, Thesis | undefined>;
  pulseByHolding?: Record<string, HoldingPulse | undefined>;
}

const PULSE_DOT: Record<string, string> = {
  intact: "bg-emerald-500",
  watch: "bg-amber-500",
  review: "bg-red-500",
};

const PULSE_ROW_BG: Record<string, string> = {
  watch: "bg-amber-50",
  review: "bg-red-50",
};

function getHoldingThesisState(thesis: Thesis | undefined) {
  if (!thesis) {
    return {
      label: "Missing thesis",
      detail: "Start with why this position exists.",
      badgeClass: "bg-red-100 text-red-800",
    };
  }

  const interpretation = thesis.interpretation ?? {};
  const monitorability = typeof interpretation.monitorability === "string" ? interpretation.monitorability : null;

  if (thesis.status === "needs_review") {
    return {
      label: "Needs review",
      detail: "Something changed or this thesis is stale.",
      badgeClass: "bg-orange-100 text-orange-800",
    };
  }

  if (monitorability === "low") {
    return {
      label: "Weak thesis",
      detail: "Reason is too vague to monitor well.",
      badgeClass: "bg-stone-200 text-stone-800",
    };
  }

  return {
    label: "Monitored",
    detail: thesis.confidence === "high" ? "High-confidence thesis in place." : "Thesis is active and being monitored.",
    badgeClass: "bg-emerald-100 text-emerald-800",
  };
}

export function HoldingsTable({ holdings, currentThesesByHolding, pulseByHolding = {} }: Props) {
  return (
    <div className="overflow-hidden rounded-xl border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-8"></TableHead>
            <TableHead>Ticker</TableHead>
            <TableHead>Name</TableHead>
            <TableHead>Thesis</TableHead>
            <TableHead className="text-right">Qty</TableHead>
            <TableHead className="text-right">Avg Cost</TableHead>
            <TableHead className="text-right">Current</TableHead>
            <TableHead className="text-right">Value</TableHead>
            <TableHead className="text-right">P&L</TableHead>
            <TableHead>Sector</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {holdings.map((h) => {
            const cost = h.quantity * h.average_cost_basis;
            const value = h.current_value || 0;
            const pnl = value - cost;
            const pnlPct = cost > 0 ? (pnl / cost) * 100 : 0;
            const thesisState = getHoldingThesisState(currentThesesByHolding[h.id]);
            const pulse = pulseByHolding[h.id];
            const pulseStatus = pulse?.pulse_status ?? "intact";
            const rowBg = PULSE_ROW_BG[pulseStatus] ?? "";

            return (
              <TableRow key={h.id} className={`transition-colors hover:bg-muted/30 ${rowBg}`}>
                <TableCell className="pr-0">
                  <span className={`inline-block h-2.5 w-2.5 rounded-full ${PULSE_DOT[pulseStatus] ?? "bg-muted"}`} title={pulseStatus} />
                </TableCell>
                <TableCell>
                  <Link href={`/dashboard/positions/${h.ticker}`} className="font-medium underline-offset-4 hover:underline">
                    {h.ticker}
                  </Link>
                </TableCell>
                <TableCell>{h.name}</TableCell>
                <TableCell>
                  <div className="space-y-1">
                    <Badge className={thesisState.badgeClass}>{thesisState.label}</Badge>
                    <p className="text-xs text-muted-foreground">{thesisState.detail}</p>
                  </div>
                </TableCell>
                <TableCell className="text-right">{h.quantity}</TableCell>
                <TableCell className="text-right">{formatCurrency(h.average_cost_basis, h.currency)}</TableCell>
                <TableCell className="text-right">{h.current_price ? formatCurrency(h.current_price, h.currency) : "—"}</TableCell>
                <TableCell className="text-right">{formatCurrency(value, h.currency)}</TableCell>
                <TableCell className={`text-right ${pnl >= 0 ? "text-green-600" : "text-red-600"}`}>
                  {formatPercent(pnlPct)}
                </TableCell>
                <TableCell>
                  {h.sector ? <Badge variant="secondary">{h.sector}</Badge> : "—"}
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}
