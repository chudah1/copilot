"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Menu, X } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { REGISTRATION_OPEN } from "@/lib/registration";
import { mk } from "./tokens";
import { PenKeepMark } from "./mark";

interface MarketingNavProps {
  active?: "faq" | "blog" | "security" | "pricing";
}

export function MarketingNav({ active }: MarketingNavProps) {
  const { isAuthenticated, isLoading } = useAuth();
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);
  const showAuthenticatedNav = !isLoading && isAuthenticated;

  const derivedActive =
    pathname.startsWith("/blog") ? "blog" :
    pathname.startsWith("/pricing") ? "pricing" :
    pathname.startsWith("/faq") ? "faq" :
    pathname.startsWith("/security") ? "security" :
    undefined;
  const currentActive = active ?? derivedActive;

  const linkStyle = (page?: string): React.CSSProperties => ({
    color: currentActive === page ? mk.ink : mk.pencil,
    textDecoration: "none",
    fontWeight: currentActive === page ? 500 : 400,
    borderBottom: currentActive === page ? `1.6px solid ${mk.ink}` : "none",
    paddingBottom: currentActive === page ? 2 : 0,
    fontSize: 14,
    transition: "color 150ms",
  });

  const links: Array<{ href: string; label: string; page?: MarketingNavProps["active"] }> = [
    { href: "/blog", label: "Blog", page: "blog" },
    { href: "/pricing", label: "Pricing", page: "pricing" },
    { href: "/faq", label: "FAQ", page: "faq" },
    { href: "/security", label: "Security", page: "security" },
  ];

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
          gap: 20,
        }}
      >
        <Link href="/" style={{ display: "flex", alignItems: "center", gap: 10, textDecoration: "none", minWidth: 0 }}>
          <PenKeepMark size={22} color={mk.ink} />
          <div style={{ display: "flex", alignItems: "baseline", gap: 10, minWidth: 0 }}>
            <span style={{ fontFamily: mk.sans, fontWeight: 600, fontSize: "1.1rem", letterSpacing: "-0.02em", color: mk.ink }}>
              penKeep
            </span>
            <span
              style={{
                fontFamily: mk.mono,
                fontSize: 10,
                letterSpacing: "0.12em",
                textTransform: "uppercase",
                color: mk.pencil,
              }}
              className="hidden md:inline"
            >
            </span>
          </div>
        </Link>

        <div style={{ display: "flex", gap: 22, alignItems: "center", flexWrap: "wrap", justifyContent: "flex-end" }}>
          <Link
            href="/#how-it-works"
            className="hidden lg:inline"
            style={{
              color: mk.pencil,
              textDecoration: "none",
              fontSize: 14,
              transition: "color 150ms",
            }}
          >
            How it works
          </Link>
          {links.map((link) => (
            <Link key={link.href} href={link.href} style={linkStyle(link.page)} className="hidden sm:inline">
              {link.label}
            </Link>
          ))}

          <button
            onClick={() => setMobileOpen((v) => !v)}
            className="sm:hidden"
            aria-label={mobileOpen ? "Close menu" : "Open menu"}
            style={{
              background: "none",
              border: `1px solid ${mk.pencilLight}`,
              borderRadius: 6,
              padding: "6px 8px",
              cursor: "pointer",
              color: mk.ink,
              display: "flex",
              alignItems: "center",
            }}
          >
            {mobileOpen ? <X size={18} /> : <Menu size={18} />}
          </button>

          {showAuthenticatedNav ? (
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
              href="/register"
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
              {REGISTRATION_OPEN ? "Create account →" : "Join the waitlist →"}
            </Link>
          )}
        </div>
      </div>

      {mobileOpen && (
        <div
          className="sm:hidden"
          style={{
            position: "absolute",
            top: "100%",
            left: 0,
            right: 0,
            background: `${mk.paper}f8`,
            backdropFilter: "blur(12px)",
            borderBottom: `1px solid ${mk.pencilLight}`,
            padding: "8px clamp(22px, 4.5vw, 56px) 20px",
            fontFamily: mk.sans,
            zIndex: 50,
          }}
        >
          <div style={{ display: "flex", flexDirection: "column" }}>
            <Link
              href="/#how-it-works"
              onClick={() => setMobileOpen(false)}
              style={{
                padding: "13px 0",
                color: mk.pencil,
                textDecoration: "none",
                fontSize: 15,
                borderBottom: `1px solid ${mk.pencilLight}`,
              }}
            >
              How it works
            </Link>
            {links.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                onClick={() => setMobileOpen(false)}
                style={{
                  padding: "13px 0",
                  color: currentActive === link.page ? mk.ink : mk.pencil,
                  textDecoration: "none",
                  fontSize: 15,
                  fontWeight: currentActive === link.page ? 500 : 400,
                  borderBottom: `1px solid ${mk.pencilLight}`,
                }}
              >
                {link.label}
              </Link>
            ))}
          </div>
        </div>
      )}
    </nav>
  );
}
