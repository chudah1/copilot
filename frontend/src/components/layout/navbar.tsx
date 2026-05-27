"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Bell, Menu, X } from "lucide-react";
import useSWR from "swr";
import { useAuth } from "@/lib/auth";
import { fetcher } from "@/lib/api";
import type { PortfolioSummary } from "@/types";

const NAV_LINKS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/digests", label: "Digests" },
  { href: "/settings", label: "Settings" },
];

export function Navbar() {
  const { logout, isAuthenticated } = useAuth();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  const { data: summary } = useSWR<PortfolioSummary>(
    isAuthenticated ? "/api/portfolio/summary" : null,
    fetcher,
    { refreshInterval: 5 * 60 * 1000 }
  );
  const alertCount = summary?.attention_queue?.filter(
    (item) => item.priority === "critical" || item.priority === "high"
  ).length ?? 0;

  return (
    <nav className="border-b border-border bg-card relative z-40">
      <div className="flex items-center justify-between px-4 sm:px-8 h-[54px]">
        {/* Wordmark */}
        <Link href="/dashboard" className="flex items-baseline gap-2 group">
          <span className="font-display text-[1.25rem] font-semibold italic text-primary tracking-tight leading-none">
            penKeep
          </span>
        </Link>

        {/* Desktop nav */}
        <div className="hidden sm:flex items-center gap-1">
          {NAV_LINKS.map(({ href, label }) => {
            const active = pathname === href || (href !== "/dashboard" && pathname.startsWith(href));
            return (
              <Link
                key={href}
                href={href}
                className={`relative px-4 py-1 font-mono text-[10px] uppercase tracking-[0.2em] transition-colors ${
                  active ? "text-foreground" : "text-muted-foreground hover:text-foreground/80"
                }`}
              >
                {label}
                {active && <span className="absolute inset-x-4 bottom-0 h-[2px] bg-primary" />}
              </Link>
            );
          })}
          <div className="w-px h-4 bg-border mx-2" />
          <Link
            href="/dashboard"
            className="relative p-2 text-muted-foreground hover:text-foreground transition-colors"
            aria-label={alertCount > 0 ? `${alertCount} alerts` : "No alerts"}
          >
            <Bell className="w-4 h-4" />
            {alertCount > 0 && (
              <span className="absolute top-1 right-1 w-1.5 h-1.5 rounded-full bg-destructive" />
            )}
          </Link>
          <button
            onClick={logout}
            className="px-4 py-1 font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground hover:text-foreground/80 transition-colors"
          >
            Sign out
          </button>
        </div>

        {/* Mobile hamburger */}
        <button
          onClick={() => setOpen((v) => !v)}
          className="sm:hidden p-2 text-muted-foreground hover:text-foreground transition-colors"
          aria-label={open ? "Close menu" : "Open menu"}
        >
          {open ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </button>
      </div>

      {/* Mobile drawer */}
      {open && (
        <div className="sm:hidden absolute top-[54px] inset-x-0 border-b border-border bg-card shadow-md">
          <div className="flex flex-col py-2">
            {NAV_LINKS.map(({ href, label }) => {
              const active = pathname === href || (href !== "/dashboard" && pathname.startsWith(href));
              return (
                <Link
                  key={href}
                  href={href}
                  onClick={() => setOpen(false)}
                  className={`px-6 py-3 font-mono text-[10px] uppercase tracking-[0.2em] transition-colors border-l-2 ${
                    active
                      ? "text-foreground border-primary"
                      : "text-muted-foreground hover:text-foreground border-transparent"
                  }`}
                >
                  {label}
                </Link>
              );
            })}
            <div className="h-px bg-border mx-6 my-1" />
            <Link
              href="/dashboard"
              onClick={() => setOpen(false)}
              className="flex items-center gap-3 px-6 py-3 font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground hover:text-foreground transition-colors border-l-2 border-transparent"
            >
              <span className="relative">
                <Bell className="w-3.5 h-3.5" />
                {alertCount > 0 && (
                  <span className="absolute -top-0.5 -right-0.5 w-1.5 h-1.5 rounded-full bg-destructive" />
                )}
              </span>
              Alerts{alertCount > 0 && ` (${alertCount})`}
            </Link>
            <button
              onClick={() => { setOpen(false); logout(); }}
              className="px-6 py-3 text-left font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground hover:text-foreground transition-colors"
            >
              Sign out
            </button>
          </div>
        </div>
      )}
    </nav>
  );
}
