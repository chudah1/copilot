"use client";

import { useAuth } from "@/lib/auth";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

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

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      // replace, not push, so the back button doesn't land on the guarded page.
      router.replace("/login");
    }
  }, [isAuthenticated, isLoading, router]);

  if (isLoading) return <GuardScreen label="Loading…" />;
  // Not authenticated: show a clear redirecting state instead of a blank screen
  // while the redirect to /login fires.
  if (!isAuthenticated) return <GuardScreen label="Redirecting to sign in…" />;

  return <>{children}</>;
}
