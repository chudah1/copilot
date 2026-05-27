import { mk } from "./tokens";

export function PenKeepMark({ size = 24, color = mk.ink }: { size?: number; color?: string }) {
  return (
    <svg viewBox="0 0 32 32" fill="none" width={size} height={size} aria-hidden>
      <circle cx="16" cy="16" r="14" stroke={color} strokeWidth="2" />
      <path d="M16 5 L19 16 L16 27 L13 16 Z" fill={color} />
      <path d="M5 16 L27 16" stroke={color} strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}
