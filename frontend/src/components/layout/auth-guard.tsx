"use client";

import { useAuth } from "@/lib/auth";
import { getStoredAccessToken } from "@/lib/auth-tokens";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

function GuardScreen({ label }: { label: string }) {
  return (
    <div className="flex min-h-screen items-center justify-center">
      <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
        {label}
      </p>
    </div>
  );
}

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();
  const router = useRouter();

  // Token check as a race-proof fallback. After register()/login() stores
  // tokens and pushes here, isAuthenticated may not have committed yet
  // (React can defer the state update behind the urgent navigation), and
  // without this fallback the guard reads a stale `false` and kicks the
  // user to /login — which is exactly the bug testers keep hitting. Trust
  // the durable stored token during the render gap. If it turns out to
  // be invalid, the api client will 401 and clear it.
  //
  // Lazy-init so the very first render already sees the token; deferring
  // it to a useEffect would let the sibling redirect useEffect race and
  // fire /login before the token-check state settled.
  const [hasStoredToken, setHasStoredToken] = useState(() => {
    if (typeof window === "undefined") return false;
    return Boolean(getStoredAccessToken());
  });
  useEffect(() => {
    // Re-read after auth state changes (e.g. logout clears tokens).
    setHasStoredToken(Boolean(getStoredAccessToken()));
  }, [isAuthenticated, isLoading]);

  const effectivelyAuthenticated = isAuthenticated || hasStoredToken;

  useEffect(() => {
    if (!isLoading && !effectivelyAuthenticated) {
      // replace, not push, so the back button doesn't land on the guarded page.
      router.replace("/login");
    }
  }, [effectivelyAuthenticated, isLoading, router]);

  if (isLoading) return <GuardScreen label="Loading…" />;
  // Not authenticated and no token in storage: redirect. Otherwise render
  // the guarded page — the AuthProvider's own state will catch up shortly.
  if (!effectivelyAuthenticated) return <GuardScreen label="Redirecting to sign in…" />;

  return <>{children}</>;
}
