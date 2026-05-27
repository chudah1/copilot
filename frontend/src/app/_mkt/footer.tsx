import Link from "next/link";
import { mk } from "./tokens";
import { PenKeepMark } from "./mark";

export function MarketingFooter() {
  return (
    <footer
      style={{
        borderTop: `1px solid ${mk.pencilLight}`,
        padding: "clamp(24px, 4vw, 36px) clamp(22px, 4.5vw, 56px)",
        display: "flex",
        flexWrap: "wrap",
        gap: 14,
        alignItems: "center",
        justifyContent: "space-between",
        fontFamily: mk.sans,
        fontSize: 13,
        color: mk.pencil,
        background: mk.paper,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <PenKeepMark size={18} color={mk.pencil} />
        <span style={{ fontWeight: 600, fontSize: 14, color: mk.ink }}>penKeep</span>
        <span>© 2026</span>
      </div>

      <div style={{ display: "flex", gap: 18, flexWrap: "wrap" }}>
        {[
          { label: "Manifesto", href: "/manifesto" },
          { label: "FAQ", href: "/faq" },
          { label: "Security", href: "/security" },
        ].map(({ label, href }) => (
          <Link key={label} href={href} style={{ color: mk.pencil, textDecoration: "none" }}>
            {label}
          </Link>
        ))}
      </div>

      <div style={{ fontFamily: mk.mono, fontSize: 11 }}>not financial advice</div>
    </footer>
  );
}
