import Link from "next/link";
import { mk } from "./tokens";

export function LaunchActions({ dark = false }: { dark?: boolean }) {
  return (
    <div
      style={{
        display: "flex",
        gap: 12,
        flexWrap: "wrap",
        alignItems: "center",
      }}
    >
      <Link
        href="/register"
        style={{
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          padding: "13px 22px",
          borderRadius: 999,
          background: dark ? mk.accent : mk.ink,
          color: mk.paper,
          fontFamily: mk.sans,
          fontSize: 15,
          fontWeight: 500,
          textDecoration: "none",
          whiteSpace: "nowrap",
        }}
      >
        Record your first decision →
      </Link>
      <Link
        href="/research"
        style={{
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          padding: "13px 22px",
          borderRadius: 999,
          border: `1px solid ${dark ? "rgba(255,255,255,0.18)" : mk.pencilLight}`,
          background: dark ? "rgba(255,255,255,0.05)" : mk.card,
          color: dark ? mk.cream : mk.ink,
          fontFamily: mk.sans,
          fontSize: 15,
          fontWeight: 500,
          textDecoration: "none",
          whiteSpace: "nowrap",
        }}
      >
        Stress-test a ticker →
      </Link>
    </div>
  );
}
