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
    <nav className="border-b border-border bg-background">
      <div className="flex items-center justify-between px-8 h-[52px]">
        <Link href="/dashboard" className="font-display italic text-[1.1rem] text-primary leading-none">
          Copilot Investor
        </Link>
        <div className="flex items-center">
          {NAV_LINKS.map(({ href, label }) => {
            const active = pathname === href || (href !== "/dashboard" && pathname.startsWith(href));
            return (
              <Link
                key={href}
                href={href}
                className={`px-4 py-1.5 font-mono text-[10px] uppercase tracking-[0.2em] transition-colors ${
                  active
                    ? "text-foreground"
                    : "text-muted-foreground hover:text-foreground/70"
                }`}
              >
                {label}
              </Link>
            );
          })}
          <button
            onClick={logout}
            className="ml-1 px-4 py-1.5 font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground hover:text-foreground/70 transition-colors"
          >
            Sign out
          </button>
        </div>
      </div>
    </nav>
  );
}
