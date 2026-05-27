"use client";

import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { TickerSearch } from "@/components/portfolio/ticker-search";

const BULLETS = [
  "Bear case — what the market is pricing in that could hurt you",
  "Key risks — the 3–5 things that could break the trade",
  "Blind spots — what your thesis might be ignoring",
  "What to watch — specific signals with thresholds and dates",
];

export default function ResearchLandingPage() {
  const router = useRouter();

  return (
    <div className="min-h-[calc(100vh-54px)] flex items-center justify-center px-4 py-12">
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="w-full max-w-sm space-y-6"
      >
        <div className="space-y-2">
          <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
            Pre-Buy Stress Test
          </p>
          <h1 className="font-display italic text-[2.2rem] leading-tight text-foreground">
            Which stock are you considering?
          </h1>
          <p className="font-sans text-sm text-muted-foreground leading-relaxed">
            Stress-test the bull case before you commit capital.
          </p>
        </div>

        <TickerSearch
          value=""
          onSelect={(ticker) => router.push(`/research/${ticker}`)}
        />

        <div className="border-t border-border/40 pt-5 space-y-2">
          <p className="font-mono text-[9px] uppercase tracking-[0.2em] text-muted-foreground/50 mb-3">
            You&apos;ll get
          </p>
          {BULLETS.map((b, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, x: -4 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.15 + i * 0.06 }}
              className="flex gap-2.5 items-start"
            >
              <span className="font-mono text-[9px] text-muted-foreground/40 mt-0.5 shrink-0 tabular-nums">
                {String(i + 1).padStart(2, "0")}
              </span>
              <span className="font-sans text-[13px] text-muted-foreground leading-snug">{b}</span>
            </motion.div>
          ))}
        </div>
      </motion.div>
    </div>
  );
}
