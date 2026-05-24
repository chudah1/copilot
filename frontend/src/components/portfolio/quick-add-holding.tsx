"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { TickerSearch } from "@/components/portfolio/ticker-search";
import type { Holding } from "@/types";

interface QuickAddHoldingProps {
  onAdd: () => void;
}

export function QuickAddHolding({ onAdd }: QuickAddHoldingProps) {
  const [ticker, setTicker] = useState("");
  const [name, setName] = useState("");
  const [quantity, setQuantity] = useState("");
  const [avgCost, setAvgCost] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSelect = (selectedTicker: string, selectedName: string) => {
    setTicker(selectedTicker);
    setName(selectedName);
  };

  const handleSubmit = async () => {
    if (!ticker || !quantity || !avgCost) return;
    try {
      setLoading(true);
      setError(null);
      await api.post<Holding>("/api/portfolio/holdings", {
        ticker: ticker.toUpperCase(),
        name: name || ticker.toUpperCase(),
        quantity: parseFloat(quantity),
        average_cost_basis: parseFloat(avgCost),
      });
      setTicker("");
      setName("");
      setQuantity("");
      setAvgCost("");
      onAdd();
    } catch {
      setError("Failed to add holding.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="rounded-lg border border-primary/20 bg-muted/30 p-4">
      <p className="text-sm font-medium mb-3">Add a position</p>
      <div className="grid grid-cols-[1fr_1fr_1fr_auto] gap-2 items-end">
        <div>
          <p className="text-[11px] text-muted-foreground mb-1">Ticker</p>
          <TickerSearch value={ticker} onSelect={handleSelect} />
        </div>
        <div>
          <p className="text-[11px] text-muted-foreground mb-1">Shares</p>
          <Input type="number" placeholder="10" min="0.000001" step="any" value={quantity} onChange={(e) => setQuantity(e.target.value)} className="h-8 text-sm" />
        </div>
        <div>
          <p className="text-[11px] text-muted-foreground mb-1">Avg cost</p>
          <Input type="number" step="0.01" min="0.000001" placeholder="135.00" value={avgCost} onChange={(e) => setAvgCost(e.target.value)} className="h-8 text-sm" />
        </div>
        <Button size="sm" onClick={handleSubmit} disabled={loading || !ticker || !quantity || !avgCost}>
          {loading ? "..." : "Add"}
        </Button>
      </div>
      {error && <p className="text-xs text-red-600 mt-2">{error}</p>}
    </div>
  );
}
