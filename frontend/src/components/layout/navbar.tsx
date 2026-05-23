"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth";

const NAV_LINKS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/digests", label: "Digests" },
  { href: "/settings", label: "Settings" },
];

export function Navbar() {
  const { logout } = useAuth();
  const pathname = usePathname();

  return (
    <nav className="border-b border-border bg-card">
      <div className="flex items-center justify-between px-8 h-[54px]">
        {/* Wordmark */}
        <Link
          href="/dashboard"
          className="flex items-baseline gap-2 group"
        >
          <span className="font-display text-[1.25rem] font-semibold italic text-primary tracking-tight leading-none">
            Copilot
          </span>
          <span className="font-mono text-[0.6rem] uppercase tracking-[0.3em] text-muted-foreground/70 group-hover:text-muted-foreground transition-colors">
            Investor
          </span>
        </Link>

        {/* Nav items */}
        <div className="flex items-center gap-1">
          {NAV_LINKS.map(({ href, label }) => {
            const active = pathname === href || (href !== "/dashboard" && pathname.startsWith(href));
            return (
              <Link
                key={href}
                href={href}
                className={`relative px-4 py-1 font-mono text-[10px] uppercase tracking-[0.2em] transition-colors ${
                  active
                    ? "text-foreground"
                    : "text-muted-foreground hover:text-foreground/80"
                }`}
              >
                {label}
                {active && (
                  <span className="absolute inset-x-4 bottom-0 h-[2px] bg-primary" />
                )}
              </Link>
            );
          })}
          <div className="w-px h-4 bg-border mx-2" />
          <button
            onClick={logout}
            className="px-4 py-1 font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground hover:text-foreground/80 transition-colors"
          >
            Sign out
          </button>
        </div>
      </div>
    </nav>
  );
}
