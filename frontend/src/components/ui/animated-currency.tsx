"use client";

import { useEffect, useRef } from "react";
import { animate, motion, useMotionValue, useTransform } from "framer-motion";
import { formatCurrency } from "@/lib/utils";

interface AnimatedCurrencyProps {
  value: number;
  currency: string;
  className?: string;
}

/**
 * Renders a currency amount that tweens smoothly when the value changes
 * (live price refreshes) instead of snapping. First paint is instant.
 */
export function AnimatedCurrency({ value, currency, className }: AnimatedCurrencyProps) {
  const motionValue = useMotionValue(value);
  const mounted = useRef(false);

  useEffect(() => {
    if (!mounted.current) {
      mounted.current = true;
      motionValue.set(value);
      return;
    }
    const controls = animate(motionValue, value, { duration: 0.7, ease: "easeOut" });
    return () => controls.stop();
  }, [value, motionValue]);

  const text = useTransform(motionValue, (v) => formatCurrency(v, currency));

  return <motion.span className={className}>{text}</motion.span>;
}
