"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { TickerSearch } from "@/components/portfolio/ticker-search";
import { mk } from "./tokens";

export function StressTestSearch() {
  const router = useRouter();
  const [query, setQuery] = useState("");

  return (
    <div
      style={{
        marginTop: 22,
        padding: 18,
        border: `1px solid ${mk.rule}`,
        background: "rgba(255,255,255,0.5)",
        position: "relative",
        zIndex: 20,
      }}
    >
      <p
        style={{
          margin: 0,
          fontFamily: mk.mono,
          fontSize: 10,
          letterSpacing: "0.15em",
          textTransform: "uppercase",
          color: mk.accent,
        }}
      >
        Check a stock before you buy
      </p>
      <p
        style={{
          margin: "8px 0 13px",
          fontFamily: mk.sans,
          fontSize: 14,
          lineHeight: 1.5,
          color: mk.inkSoft,
        }}
      >
        Search a company and see the strongest case against owning it. One test is free.
      </p>
      <TickerSearch
        value={query}
        onChange={setQuery}
        onSelect={(ticker) => router.push(`/research/${ticker}`)}
        placeholder="Search NVDA, Tesla or Rolls-Royce"
      />
    </div>
  );
}
