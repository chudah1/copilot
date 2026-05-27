import { mk } from "./tokens";

export function PenKeepMark({ size = 24, color = mk.ink }: { size?: number; color?: string }) {
  return (
    <svg viewBox="0 0 32 36" fill="none" width={size} height={size * (36 / 32)} aria-hidden>
      {/* Arch: flat bottom, rounded top */}
      <path
        d="M3 36 L3 14 Q3 3 16 3 Q29 3 29 14 L29 36 Z"
        stroke={color}
        strokeWidth="2"
        strokeLinejoin="round"
        fill="none"
      />
      {/* Nib body: tall diamond */}
      <path d="M16 9 L19.5 20 L16 24 L12.5 20 Z" fill={color} />
      {/* Nib slit */}
      <line x1="16" y1="15" x2="16" y2="24" stroke="white" strokeWidth="1" strokeLinecap="round" />
      {/* Nib tip dot */}
      <circle cx="16" cy="24" r="1" fill={color} />
    </svg>
  );
}
