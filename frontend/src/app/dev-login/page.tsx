"use client";

import { Suspense, useEffect, useState, useSyncExternalStore } from "react";
import { useSearchParams } from "next/navigation";
import { getApiBaseUrl } from "@/lib/api-base";
import { storeTokens } from "@/lib/auth-tokens";

function isLocalHost() {
  if (typeof window === "undefined") return false;
  return window.location.hostname === "127.0.0.1" || window.location.hostname === "localhost";
}

function subscribeToHost(onStoreChange: () => void) {
  queueMicrotask(onStoreChange);
  return () => {};
}

function safeRedirect(target: string | null) {
  if (!target) return "/dashboard";
  try {
    const parsed = new URL(target, window.location.origin);
    if (!["127.0.0.1", "localhost"].includes(parsed.hostname)) return "/dashboard";
    return `${parsed.pathname}${parsed.search}${parsed.hash}`;
  } catch {
    return "/dashboard";
  }
}

function DevLoginInner() {
  const searchParams = useSearchParams();
  const [message, setMessage] = useState("Signing you in…");
  const localHost = useSyncExternalStore(subscribeToHost, isLocalHost, () => false);
  const email = searchParams.get("email")?.trim().toLowerCase() || "";
  const password = searchParams.get("password")?.trim() || "PenkeepTest123!";
  const redirect = safeRedirect(searchParams.get("redirect"));

  useEffect(() => {
    if (localHost !== true || !email) {
      return;
    }

    let cancelled = false;
    const run = async () => {
      try {
        const response = await fetch(`${getApiBaseUrl()}/api/auth/login`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({ email, password }),
        });
        if (!response.ok) {
          setMessage("Dev login failed.");
          return;
        }
        const tokens = await response.json();
        if (cancelled) return;
        storeTokens(tokens);
        document.cookie = `access_token=local-dev-${encodeURIComponent(email)}; Path=/; SameSite=Lax`;
        document.cookie = `refresh_token=local-dev-${encodeURIComponent(email)}; Path=/; SameSite=Lax`;
        window.location.replace(redirect);
      } catch {
        if (!cancelled) setMessage("Dev login failed.");
      }
    };

    void run();
    return () => {
      cancelled = true;
    };
  }, [email, localHost, password, redirect]);

  if (!localHost) {
    return (
      <main className="flex min-h-screen items-center justify-center">
        <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
          Dev login is only available locally.
        </p>
      </main>
    );
  }

  if (!email) {
    return (
      <main className="flex min-h-screen items-center justify-center">
        <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
          Missing email.
        </p>
      </main>
    );
  }

  return (
    <main className="flex min-h-screen items-center justify-center">
      <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
        {message}
      </p>
    </main>
  );
}

export default function DevLoginPage() {
  return (
    <Suspense>
      <DevLoginInner />
    </Suspense>
  );
}
