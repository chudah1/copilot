"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Bell, BookOpenText, BriefcaseBusiness, Menu, Search, X } from "lucide-react";
import useSWR from "swr";
import { useAuth } from "@/lib/auth";
import { fetcher } from "@/lib/api";
import type { PortfolioPulse } from "@/types";

const NAV_LINKS = [
  { href: "/dashboard", label: "Portfolio" },
  { href: "/research", label: "Research" },
  { href: "/digests", label: "Digests" },
  { href: "/settings", label: "Settings" },
];

const PUBLIC_NAV_LINKS = [
  { href: "/research", label: "Research" },
];

export function Navbar() {
  const { logout, isAuthenticated, isLoading } = useAuth();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const showAuthenticatedNav = !isLoading && isAuthenticated;
  const visibleLinks = showAuthenticatedNav ? NAV_LINKS : PUBLIC_NAV_LINKS;

  const { data: pulse } = useSWR<PortfolioPulse>(
    showAuthenticatedNav ? "/api/portfolio/pulse" : null,
    fetcher,
    { refreshInterval: 60 * 1000 }
  );
  const evidencePulses = pulse?.pulses.filter(
    (item) => item.has_thesis && item.pulse_basis === "evidence" && item.pulse_status !== "intact",
  ) ?? [];
  const alertCount = evidencePulses.length;
  const decisionCount = evidencePulses.filter((item) => item.pulse_status === "review").length;
  const primaryReviewPulse = evidencePulses.reduce<(typeof evidencePulses)[number] | null>(
    (highest, item) => !highest || item.urgency_score > highest.urgency_score ? item : highest,
    null,
  );
  const alertsHref = primaryReviewPulse
    ? `/dashboard/positions/${primaryReviewPulse.ticker}?tab=monitoring`
    : "/dashboard#positions";
  const reviewStatus = decisionCount > 0
    ? `${decisionCount} decision${decisionCount === 1 ? "" : "s"} waiting`
    : alertCount > 0
      ? `${alertCount} change${alertCount === 1 ? "" : "s"} waiting`
    : "Nothing waiting";
  const mobileLinks = [
    { href: "/dashboard", label: "Portfolio", icon: BriefcaseBusiness },
    { href: "/research", label: "Research", icon: Search },
    { href: alertsHref, label: "Review", icon: Bell, count: alertCount },
    { href: "/digests", label: "Digests", icon: BookOpenText },
  ];

  return (
    <>
    <nav className="sticky top-0 z-40 border-b border-border/80 bg-background/88 backdrop-blur-xl">
      <div className="px-4 py-3 sm:px-8">
        <div className="product-panel product-panel-muted flex items-center justify-between gap-4 px-4 py-3 sm:px-5">
          <div className="flex items-center gap-3">
            <Link href={showAuthenticatedNav ? "/dashboard" : "/"} className="group">
              <div className="flex flex-col">
                <span className="font-display text-[1.3rem] font-semibold italic leading-none tracking-tight text-primary transition-colors group-hover:text-primary/80">
                  penKeep
                </span>
              </div>
            </Link>
            {showAuthenticatedNav && (
              <div className={`hidden lg:flex items-center gap-2 border px-2.5 py-1 ${
                alertCount > 0
                  ? "border-amber-500/25 bg-amber-500/8"
                  : "border-border/70 bg-background/70"
              }`}>
                <span className={`inline-block h-1.5 w-1.5 rounded-full ${alertCount > 0 ? "bg-amber-500" : "bg-emerald-500"}`} />
                <span className={`font-mono text-[10px] uppercase tracking-[0.14em] ${
                  alertCount > 0 ? "text-amber-700" : "text-muted-foreground"
                }`}>
                  {reviewStatus}
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
            {showAuthenticatedNav ? (
              <>
                <Link
                  href={alertsHref}
                  className="relative flex items-center gap-2 border border-border/80 bg-background/70 px-3 py-2 text-muted-foreground transition-colors hover:text-foreground"
                  aria-label={reviewStatus}
                >
                  <Bell className="w-4 h-4" />
                  <span className="font-mono text-[10px] uppercase tracking-[0.14em]">
                    Review
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
            {showAuthenticatedNav ? (
              <>
                <Link
                  href={alertsHref}
                  onClick={() => setOpen(false)}
                  className="mx-2 flex items-center justify-between px-4 py-3 font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground transition-colors hover:bg-background hover:text-foreground"
                >
                  <span className="flex items-center gap-3">
                    <Bell className="w-3.5 h-3.5" />
                    Review
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
    {showAuthenticatedNav && (
      <>
        <div aria-hidden className="h-[4.5rem] sm:hidden" />
        <div className="fixed inset-x-0 bottom-0 z-50 border-t border-border/80 bg-background/94 px-2 pb-[max(0.45rem,env(safe-area-inset-bottom))] pt-2 backdrop-blur-xl sm:hidden">
          <div className="mx-auto grid max-w-md grid-cols-4">
            {mobileLinks.map(({ href, label, icon: Icon, count }) => {
              const active = pathname === href.split("?")[0] ||
                (label === "Research" && pathname.startsWith("/research")) ||
                (label === "Digests" && pathname.startsWith("/digests"));
              return (
                <Link
                  key={label}
                  href={href}
                  aria-label={label === "Review" ? reviewStatus : label}
                  className={`relative flex min-h-12 flex-col items-center justify-center gap-1 px-1 font-mono text-[9px] uppercase tracking-[0.08em] transition-colors ${
                    active ? "text-primary" : "text-muted-foreground"
                  }`}
                >
                  <span className="relative">
                    <Icon className="h-[18px] w-[18px]" strokeWidth={active ? 2.1 : 1.7} />
                    {count && count > 0 ? (
                      <span className="absolute -right-2.5 -top-1.5 inline-flex min-w-4 items-center justify-center rounded-full bg-destructive px-1 text-[8px] leading-4 text-white">
                        {count}
                      </span>
                    ) : null}
                  </span>
                  <span>{label}</span>
                </Link>
              );
            })}
          </div>
        </div>
      </>
    )}
    </>
  );
}
