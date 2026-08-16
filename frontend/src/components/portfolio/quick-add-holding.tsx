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
  const selectedLabel = name.trim();

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
    <form
      onSubmit={(event) => {
        event.preventDefault();
        void handleSubmit();
      }}
      className="product-panel space-y-4 border border-border/70 bg-background/72 p-4"
    >
      <div className="space-y-1.5">
        <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
          Add position
        </p>
        <p className="max-w-2xl font-sans text-sm leading-relaxed text-foreground/78">
          Add one position quickly. PenKeep will refresh the dashboard and pull it into the decision workflow right away.
        </p>
      </div>

      <div className="grid gap-3 lg:grid-cols-[minmax(11rem,1.6fr)_7rem_8rem_auto]">
        <div className="space-y-1">
          <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
            Ticker
          </p>
          <div className="min-w-0">
            <TickerSearch
              value={ticker}
              onChange={(nextTicker) => {
                setTicker(nextTicker);
                setName("");
              }}
              onSelect={handleSelect}
            />
          </div>
        </div>
        <div className="space-y-1">
          <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
            Shares
          </p>
          <Input
            type="number"
            placeholder="0"
            min="0.000001"
            step="any"
            value={quantity}
            onChange={(e) => setQuantity(e.target.value)}
            className="h-9 text-sm"
            disabled={loading}
          />
        </div>
        <div className="space-y-1">
          <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
            Avg cost
          </p>
          <Input
            type="number"
            step="0.01"
            min="0.000001"
            placeholder="0.00"
            value={avgCost}
            onChange={(e) => setAvgCost(e.target.value)}
            className="h-9 text-sm"
            disabled={loading}
          />
        </div>
        <div className="flex items-end">
          <Button type="submit" size="sm" loading={loading} disabled={loading || !ticker || !quantity || !avgCost} className="h-9 w-full lg:w-auto">
            {loading ? "Adding" : "Add position"}
          </Button>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-border/60 pt-3">
        {selectedLabel ? (
          <p className="font-sans text-xs text-foreground/72">
            Adding <span className="font-medium text-foreground">{selectedLabel}</span>
            {ticker ? ` (${ticker})` : ""}.
          </p>
        ) : ticker ? (
          <p className="font-sans text-xs text-muted-foreground">
            Pick the listed company match to confirm the symbol before you add it.
          </p>
        ) : (
          <p className="font-sans text-xs text-muted-foreground">
            Add one name at a time. The dashboard will refresh as soon as it lands.
          </p>
        )}

        {loading && (
          <p className="font-sans text-xs text-primary">
            Saving the position and refreshing the dashboard…
          </p>
        )}

        {error && <p className="font-sans text-xs text-red-600">{error}</p>}
      </div>
    </form>
  );
}
