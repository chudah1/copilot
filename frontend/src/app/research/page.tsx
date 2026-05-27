"use client";

import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { TickerSearch } from "@/components/portfolio/ticker-search";

export default function ResearchLandingPage() {
  const router = useRouter();

  return (
    <div className="min-h-[calc(100vh-54px)] flex items-center justify-center px-4">
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="w-full max-w-sm space-y-4"
      >
        <div>
          <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground mb-2">
            Pre-Buy Stress Test
          </p>
          <h1 className="font-display italic text-[2rem] leading-tight text-foreground mb-1">
            Which stock are you considering?
          </h1>
          <p className="font-sans text-sm text-muted-foreground">
            Search for a ticker to stress-test the bull case before you commit capital.
          </p>
        </div>

        <TickerSearch
          value=""
          onSelect={(ticker) => router.push(`/research/${ticker}`)}
        />
      </motion.div>
    </div>
  );
}
