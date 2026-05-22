"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";

interface TickerResult {
  ticker: string;
  name: string;
  exchange: string;
}

interface TickerSearchProps {
  value: string;
  onSelect: (ticker: string, name: string) => void;
}

export function TickerSearch({ value, onSelect }: TickerSearchProps) {
  const [query, setQuery] = useState(value);
  const [results, setResults] = useState<TickerResult[]>([]);
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const containerRef = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const search = useCallback((q: string) => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (q.length < 1) {
      setResults([]);
      setOpen(false);
      return;
    }
    debounceRef.current = setTimeout(async () => {
      try {
        const data = await api.get<TickerResult[]>(`/api/portfolio/search?q=${encodeURIComponent(q)}`);
        setResults(data);
        setOpen(data.length > 0);
        setActiveIndex(-1);
      } catch {
        setResults([]);
        setOpen(false);
      }
    }, 300);
  }, []);

  useEffect(() => {
    search(query);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [query, search]);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const select = (result: TickerResult) => {
    setQuery(result.ticker);
    setOpen(false);
    onSelect(result.ticker, result.name);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!open || results.length === 0) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex(i => Math.min(i + 1, results.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex(i => Math.max(i - 1, 0));
    } else if (e.key === "Enter" && activeIndex >= 0) {
      e.preventDefault();
      select(results[activeIndex]);
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  };

  return (
    <div ref={containerRef} className="relative">
      <Input
        placeholder="NVDA or Nvidia"
        value={query}
        onChange={(e) => setQuery(e.target.value.toUpperCase())}
        onKeyDown={handleKeyDown}
        className="h-8 text-sm"
        autoComplete="off"
        spellCheck={false}
      />
      {open && (
        <div className="absolute left-0 top-full z-50 mt-1 min-w-[240px] rounded-md border bg-background shadow-md">
          {results.map((result, i) => (
            <button
              key={result.ticker}
              type="button"
              className={`flex w-full items-baseline gap-2 px-3 py-2 text-left text-sm transition-colors hover:bg-muted ${i === activeIndex ? "bg-muted" : ""}`}
              onMouseDown={(e) => { e.preventDefault(); select(result); }}
              onMouseEnter={() => setActiveIndex(i)}
            >
              <span className="font-mono text-xs font-semibold">{result.ticker}</span>
              <span className="truncate text-xs text-muted-foreground">{result.name}</span>
              {result.exchange && (
                <span className="ml-auto shrink-0 text-[10px] text-muted-foreground/60">{result.exchange}</span>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
