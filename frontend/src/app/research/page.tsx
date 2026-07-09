"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { TickerSearch } from "@/components/portfolio/ticker-search";

const BULLETS = [
  "Bear case — what can hurt you",
  "Key risks — what breaks the trade",
  "Blind spots — what your thesis may miss",
  "What to watch — signals, thresholds, dates",
];

export default function ResearchLandingPage() {
  const router = useRouter();
  const [query, setQuery] = useState("");

  return (
    <div className="min-h-[calc(100vh-54px)] px-4 py-12 sm:px-8">
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="mx-auto w-full max-w-4xl space-y-6"
      >
        <div className="product-panel product-panel-muted relative z-20 overflow-visible p-6 sm:p-8">
          <div className="grid gap-6 lg:grid-cols-[minmax(0,1.3fr)_minmax(18rem,22rem)]">
            <div className="space-y-4">
              <div className="space-y-2">
                <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                  Stress Test
                </p>
                <h1 className="font-display italic text-[2.5rem] leading-tight text-foreground sm:text-[3rem]">
                  Stress-test a ticker
                </h1>
                <p className="max-w-xl font-sans text-sm leading-relaxed text-muted-foreground">
                  Bear case before you buy.
                </p>
              </div>

              <div className="relative z-30">
                <TickerSearch
                  value={query}
                  onChange={setQuery}
                  onSelect={(ticker) => router.push(`/research/${ticker}`)}
                />
              </div>
            </div>

            <aside className="grid gap-3">
              <div className="border border-border/60 bg-background/70 p-4">
                <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                  You get
                </p>
                <p className="mt-2 font-display text-[1.4rem] italic leading-tight text-foreground">
                  A decision memo.
                </p>
              </div>
              <div className="border border-border/60 bg-background/70 p-4">
                <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                  Use for
                </p>
                <p className="mt-2 font-sans text-sm leading-relaxed text-foreground/80">
                  Buying and sizing.
                </p>
              </div>
            </aside>
          </div>
        </div>

        <div className="relative z-0 grid gap-3 sm:grid-cols-2">
          {BULLETS.map((bullet, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, x: -4 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.15 + i * 0.06 }}
              className="product-panel p-4"
            >
              <div className="flex gap-3 items-start">
                <span className="font-mono text-[10px] text-muted-foreground/40 mt-0.5 shrink-0 tabular-nums">
                  {String(i + 1).padStart(2, "0")}
                </span>
                <span className="font-sans text-sm leading-relaxed text-foreground/80">{bullet}</span>
              </div>
            </motion.div>
          ))}
        </div>
      </motion.div>
    </div>
  );
}
