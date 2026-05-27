"use client";

const PATHS: Record<string, string> = {
  up:    "M0,12 C8,10 16,6 24,3 C32,0 40,1 48,2",
  flat:  "M0,8 C8,8 16,9 24,8 C32,7 40,8 48,8",
  down:  "M0,2 C8,3 16,6 24,9 C32,12 40,13 48,14",
  bumpy: "M0,8 C6,4 10,12 16,7 C22,2 28,11 34,8 C40,5 44,10 48,8",
};

export function Sparkline({ trend, width = 48, height = 16, color }: {
  trend: string;
  width?: number;
  height?: number;
  color: string;
}) {
  const d = PATHS[trend] ?? PATHS.flat;
  return (
    <svg width={width} height={height} viewBox={`0 0 48 16`} fill="none" style={{ flex: '0 0 auto' }}>
      <path d={d} stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
