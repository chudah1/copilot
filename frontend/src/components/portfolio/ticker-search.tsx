"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { createPortal } from "react-dom";
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
  onChange?: (value: string) => void;
  placeholder?: string;
}

interface MenuPosition {
  top: number;
  left: number;
  width: number;
  maxHeight: number;
}

function getSearchPriority(query: string, result: TickerResult) {
  const normalizedQuery = query.trim().toUpperCase();
  const ticker = result.ticker.toUpperCase();
  const name = result.name.toUpperCase();
  const exchange = result.exchange.toUpperCase();

  let score = 0;

  if (ticker === normalizedQuery) score += 120;
  else if (ticker.startsWith(normalizedQuery)) score += 55;

  if (name === normalizedQuery) score += 90;
  else if (name.startsWith(normalizedQuery)) score += 28;
  else if (name.includes(normalizedQuery)) score += 10;

  if (["NMS", "NYQ", "NGM", "ASE"].includes(exchange)) score += 8;
  if (ticker.includes(".")) score -= 6;
  if (/\b(ETF|TRUST|FUND|DAILY|BULL|BEAR|SHORT|LONG|2X|3X)\b/i.test(result.name)) score -= 18;

  return score;
}

export function TickerSearch({ value, onSelect, onChange, placeholder = "NVDA or Nvidia" }: TickerSearchProps) {
  const [results, setResults] = useState<TickerResult[]>([]);
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const containerRef = useRef<HTMLDivElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [menuPosition, setMenuPosition] = useState<MenuPosition | null>(null);

  const updateMenuPosition = useCallback(() => {
    const inputBounds = containerRef.current?.getBoundingClientRect();
    if (!inputBounds) return;

    const top = inputBounds.bottom + 8;
    setMenuPosition({
      top,
      left: inputBounds.left,
      width: inputBounds.width,
      maxHeight: Math.max(160, window.innerHeight - top - 16),
    });
  }, []);

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
        const ranked = [...data]
          .sort((a, b) => getSearchPriority(q, b) - getSearchPriority(q, a))
          .slice(0, 6);
        setResults(ranked);
        setOpen(ranked.length > 0);
        setActiveIndex(-1);
      } catch {
        setResults([]);
        setOpen(false);
      }
    }, 300);
  }, []);

  useEffect(() => {
    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }
    };
  }, []);

  useEffect(() => {
    if (!open) {
      return;
    }

    updateMenuPosition();
    window.addEventListener("resize", updateMenuPosition);
    // Follow the input when its parent scrolls inside the dashboard.
    window.addEventListener("scroll", updateMenuPosition, true);
    return () => {
      window.removeEventListener("resize", updateMenuPosition);
      window.removeEventListener("scroll", updateMenuPosition, true);
    };
  }, [open, updateMenuPosition]);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      const target = e.target as Node;
      if (
        containerRef.current &&
        !containerRef.current.contains(target) &&
        !menuRef.current?.contains(target)
      ) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const select = (result: TickerResult) => {
    onChange?.(result.ticker);
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
    <div ref={containerRef} className="relative w-full">
      <Input
        placeholder={placeholder}
        value={value}
        onChange={(e) => {
          const nextQuery = e.target.value.toUpperCase();
          onChange?.(nextQuery);
          search(nextQuery);
        }}
        onKeyDown={handleKeyDown}
        className="h-11 text-base"
        autoComplete="off"
        spellCheck={false}
      />
      {open && menuPosition && typeof document !== "undefined" && createPortal(
        <div
          ref={menuRef}
          className="fixed z-[100] overflow-hidden border border-border/70 bg-background shadow-[0_20px_50px_rgba(33,24,17,0.12)]"
          style={{
            top: menuPosition.top,
            left: menuPosition.left,
            width: menuPosition.width,
            maxHeight: menuPosition.maxHeight,
          }}
        >
          <div className="border-b border-border/60 px-4 py-2">
            <p className="font-mono text-[9px] uppercase tracking-[0.18em] text-muted-foreground/70">
              Top matches
            </p>
          </div>
          <div
            className="overflow-y-auto"
            style={{ maxHeight: Math.max(96, menuPosition.maxHeight - 44) }}
          >
            {results.map((result, i) => (
              <button
                key={result.ticker}
                type="button"
                className={`grid w-full grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-3 px-4 py-3 text-left text-sm transition-colors hover:bg-muted ${i === activeIndex ? "bg-muted" : ""}`}
                onMouseDown={(e) => { e.preventDefault(); select(result); }}
                onMouseEnter={() => setActiveIndex(i)}
              >
                <span className="font-mono text-[11px] font-semibold uppercase tracking-[0.12em] text-foreground">
                  {result.ticker}
                </span>
                <span className="min-w-0 truncate text-sm text-muted-foreground">
                  {result.name}
                </span>
                {result.exchange ? (
                  <span className="shrink-0 font-mono text-[10px] text-muted-foreground/60">
                    {result.exchange}
                  </span>
                ) : (
                  <span />
                )}
              </button>
            ))}
          </div>
        </div>,
        document.body,
      )}
    </div>
  );
}
