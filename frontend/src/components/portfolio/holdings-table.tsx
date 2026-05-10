"use client";

import Link from "next/link";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { formatCurrency, formatPercent } from "@/lib/utils";
import type { Holding } from "@/types";

interface Props {
  holdings: Holding[];
}

export function HoldingsTable({ holdings }: Props) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Ticker</TableHead>
          <TableHead>Name</TableHead>
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

          return (
            <TableRow key={h.id}>
              <TableCell>
                <Link href={`/dashboard/positions/${h.ticker}`} className="font-medium underline">
                  {h.ticker}
                </Link>
              </TableCell>
              <TableCell>{h.name}</TableCell>
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
  );
}
