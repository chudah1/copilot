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
  { href: "/research", label: "Research" },
  { href: "/digests", label: "Digests" },
  { href: "/settings", label: "Settings" },
];

const PUBLIC_NAV_LINKS = [
  { href: "/research", label: "Research" },
];

export function Navbar() {
  const { logout, isAuthenticated } = useAuth();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const visibleLinks = isAuthenticated ? NAV_LINKS : PUBLIC_NAV_LINKS;

  const { data: summary } = useSWR<PortfolioSummary>(
    isAuthenticated ? "/api/portfolio/summary" : null,
    fetcher,
    { refreshInterval: 5 * 60 * 1000 }
  );
  const alertCount = summary?.attention_queue?.filter(
    (item) => item.priority === "critical" || item.priority === "high"
  ).length ?? 0;
  const alertsHref = alertCount > 0 ? "/dashboard#live-pressure" : "/dashboard#positions";

  return (
    <nav className="sticky top-0 z-40 border-b border-border/80 bg-background/88 backdrop-blur-xl">
      <div className="px-4 py-3 sm:px-8">
        <div className="product-panel product-panel-muted flex items-center justify-between gap-4 px-4 py-3 sm:px-5">
          <div className="flex items-center gap-3">
            <Link href="/dashboard" className="group">
              <div className="flex flex-col">
                <span className="font-display text-[1.3rem] font-semibold italic leading-none tracking-tight text-primary transition-colors group-hover:text-primary/80">
                  penKeep
                </span>
              </div>
            </Link>
            {isAuthenticated && (
              <div className="hidden lg:flex items-center gap-2 border border-emerald-500/20 bg-emerald-500/8 px-2.5 py-1">
                <span className="inline-block h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-emerald-700">
                  Monitoring live
                </span>
              </div>
            )}
          </div>

          <div className="hidden sm:flex items-center gap-3">
            <div className="flex items-center gap-1 border border-border/80 bg-background/70 px-1 py-1">
          {visibleLinks.map(({ href, label }) => {
            const active = pathname === href || (href !== "/dashboard" && pathname.startsWith(href));
            return (
              <Link
                key={href}
                href={href}
                    className={`relative px-3 py-2 font-mono text-[10px] uppercase tracking-[0.18em] transition-colors ${
                  active
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-card hover:text-foreground/80"
                }`}
              >
                {label}
              </Link>
            );
          })}
            </div>
            {isAuthenticated ? (
              <>
                <Link
                  href={alertsHref}
                  className="relative flex items-center gap-2 border border-border/80 bg-background/70 px-3 py-2 text-muted-foreground transition-colors hover:text-foreground"
                  aria-label={alertCount > 0 ? `${alertCount} alerts` : "No alerts"}
                >
                  <Bell className="w-4 h-4" />
                  <span className="font-mono text-[10px] uppercase tracking-[0.14em]">
                    Alerts
                  </span>
                  {alertCount > 0 && (
                    <span className="inline-flex min-w-5 items-center justify-center bg-destructive px-1.5 py-0.5 font-mono text-[10px] text-white">
                      {alertCount}
                    </span>
                  )}
                </Link>
                <button
                  onClick={logout}
                  className="border border-border/80 px-3 py-2 font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground transition-colors hover:border-foreground/20 hover:text-foreground/80"
                >
                  Sign out
                </button>
              </>
            ) : (
              <>
                <Link
                  href="/login"
                  className="border border-border/80 px-3 py-2 font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground transition-colors hover:border-foreground/20 hover:text-foreground/80"
                >
                  Sign in
                </Link>
                <Link
                  href="/register"
                  className="bg-primary px-3 py-2 font-mono text-[10px] uppercase tracking-[0.18em] text-primary-foreground transition-colors hover:bg-primary/90"
                >
                  Create account
                </Link>
              </>
            )}
          </div>

          <button
            onClick={() => setOpen((v) => !v)}
            className="sm:hidden border border-border/80 bg-background/80 p-2 text-muted-foreground transition-colors hover:text-foreground"
            aria-label={open ? "Close menu" : "Open menu"}
          >
            {open ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>
        </div>
      </div>

      {open && (
        <div className="px-4 pb-3 sm:hidden sm:px-8">
          <div className="product-panel product-panel-muted flex flex-col py-2 shadow-[0_18px_50px_rgba(52,40,24,0.12)]">
            {visibleLinks.map(({ href, label }) => {
              const active = pathname === href || (href !== "/dashboard" && pathname.startsWith(href));
              return (
                <Link
                  key={href}
                  href={href}
                  onClick={() => setOpen(false)}
                  className={`mx-2 px-4 py-3 font-mono text-[10px] uppercase tracking-[0.18em] transition-colors ${
                    active
                      ? "bg-primary text-primary-foreground"
                      : "text-muted-foreground hover:bg-background hover:text-foreground"
                  }`}
                >
                  {label}
                </Link>
              );
            })}
            <div className="mx-4 my-2 h-px bg-border" />
            {isAuthenticated ? (
              <>
                <Link
                  href={alertsHref}
                  onClick={() => setOpen(false)}
                  className="mx-2 flex items-center justify-between px-4 py-3 font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground transition-colors hover:bg-background hover:text-foreground"
                >
                  <span className="flex items-center gap-3">
                    <Bell className="w-3.5 h-3.5" />
                    Alerts
                  </span>
                  {alertCount > 0 && (
                    <span className="inline-flex min-w-5 items-center justify-center bg-destructive px-1.5 py-0.5 text-[10px] text-white">
                      {alertCount}
                    </span>
                  )}
                </Link>
                <button
                  onClick={() => { setOpen(false); logout(); }}
                  className="mx-2 px-4 py-3 text-left font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground transition-colors hover:bg-background hover:text-foreground"
                >
                  Sign out
                </button>
              </>
            ) : (
              <>
                <Link
                  href="/login"
                  onClick={() => setOpen(false)}
                  className="mx-2 px-4 py-3 font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground transition-colors hover:bg-background hover:text-foreground"
                >
                  Sign in
                </Link>
                <Link
                  href="/register"
                  onClick={() => setOpen(false)}
                  className="mx-2 px-4 py-3 font-mono text-[10px] uppercase tracking-[0.18em] text-primary transition-colors hover:bg-background hover:text-primary/80"
                >
                  Create account
                </Link>
              </>
            )}
          </div>
        </div>
      )}
    </nav>
  );
}
