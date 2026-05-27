"use client";

import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { mk } from "./tokens";
import { PenKeepMark } from "./mark";

interface MarketingNavProps {
  active?: "faq" | "manifesto" | "security" | "pricing";
}

export function MarketingNav({ active }: MarketingNavProps) {
  const { isAuthenticated } = useAuth();

  const linkStyle = (page?: string): React.CSSProperties => ({
    color: active === page ? mk.ink : mk.pencil,
    textDecoration: "none",
    fontWeight: active === page ? 500 : 400,
    borderBottom: active === page ? `1.6px solid ${mk.ink}` : "none",
    paddingBottom: active === page ? 2 : 0,
    fontSize: 14,
    transition: "color 150ms",
  });

  return (
    <nav
      style={{
        position: "sticky",
        top: 0,
        zIndex: 50,
        background: `${mk.paper}ee`,
        backdropFilter: "blur(8px)",
        borderBottom: `1px solid ${mk.pencilLight}`,
        fontFamily: mk.sans,
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "0 clamp(22px, 4.5vw, 56px)",
          height: "clamp(52px, 8vw, 72px)",
        }}
      >
        <Link href="/" style={{ display: "flex", alignItems: "center", gap: 10, textDecoration: "none" }}>
          <PenKeepMark size={22} color={mk.ink} />
          <span style={{ fontFamily: mk.sans, fontWeight: 600, fontSize: "1.1rem", letterSpacing: "-0.02em", color: mk.ink }}>
            penKeep
          </span>
        </Link>

        <div style={{ display: "flex", gap: 26, alignItems: "center" }}>
          <Link href="/manifesto" style={linkStyle("manifesto")} className="hidden sm:inline">
            Manifesto
          </Link>
          <Link href="/faq" style={linkStyle("faq")} className="hidden sm:inline">
            FAQ
          </Link>
          <Link href="/pricing" style={linkStyle("pricing")} className="hidden sm:inline">
            Pricing
          </Link>
          <Link href="/security" style={linkStyle("security")} className="hidden sm:inline">
            Security
          </Link>

          {isAuthenticated ? (
            <Link
              href="/dashboard"
              style={{
                padding: "8px 16px",
                background: mk.ink,
                color: mk.paper,
                borderRadius: 999,
                fontSize: 14,
                fontWeight: 500,
                textDecoration: "none",
                whiteSpace: "nowrap",
              }}
            >
              Go to app →
            </Link>
          ) : (
            <Link
              href="/#signup"
              style={{
                padding: "8px 16px",
                background: mk.ink,
                color: mk.paper,
                borderRadius: 999,
                fontSize: 14,
                fontWeight: 500,
                textDecoration: "none",
                whiteSpace: "nowrap",
              }}
            >
              Join waitlist →
            </Link>
          )}
        </div>
      </div>
    </nav>
  );
}
