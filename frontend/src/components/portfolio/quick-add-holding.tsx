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
    <div className="flex flex-nowrap items-center gap-2">
      <div className="w-40 shrink-0">
        <TickerSearch
          value={ticker}
          onChange={(nextTicker) => { setTicker(nextTicker); setName(""); }}
          onSelect={handleSelect}
        />
      </div>
      <Input type="number" placeholder="Shares" min="0.000001" step="any" value={quantity} onChange={(e) => setQuantity(e.target.value)} className="h-8 text-sm w-24" />
      <Input type="number" step="0.01" min="0.000001" placeholder="Avg cost" value={avgCost} onChange={(e) => setAvgCost(e.target.value)} className="h-8 text-sm w-24" />
      <Button size="sm" onClick={handleSubmit} disabled={loading || !ticker || !quantity || !avgCost}>
        {loading ? "…" : "Add"}
      </Button>
      {error && <p className="text-xs text-red-600">{error}</p>}
    </div>
  );
}
