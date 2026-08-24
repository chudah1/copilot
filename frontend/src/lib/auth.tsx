"use client";

import { createContext, useContext, useEffect, useState, ReactNode, startTransition } from "react";
import { useRouter } from "next/navigation";
import { api } from "./api";
import { getApiBaseUrl } from "./api-base";
import { clearStoredTokens, getStoredAccessToken, getStoredRefreshToken, storeTokens } from "./auth-tokens";
import type { TokenResponse } from "@/types";

interface AuthContextType {
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  // Lazy-init from durable storage so a re-mount (or the destination page
  // rendering before setIsAuthenticated commits) doesn't briefly report
  // `false` and get the user bounced to /login. The initial render sees
  // "we have a token, presume authenticated" — the `checkAuth` effect
  // below still runs the real validation and downgrades to false if the
  // token turns out to be stale.
  const [isAuthenticated, setIsAuthenticated] = useState(() => {
    if (typeof window === "undefined") return false;
    return Boolean(getStoredAccessToken());
  });
  const [isLoading, setIsLoading] = useState(true);
  const router = useRouter();

  useEffect(() => {
    async function checkAuth() {
      const apiUrl = getApiBaseUrl();
      const accessToken = getStoredAccessToken();
      const refreshToken = getStoredRefreshToken();

      // Public pages should not probe protected endpoints for visitors who
      // have no local session. Besides wasting a request, the expected 403/422
      // responses make a clean waitlist page look broken in DevTools.
      if (!accessToken && !refreshToken) {
        startTransition(() => {
          setIsAuthenticated(false);
          setIsLoading(false);
        });
        return;
      }

      try {
        // Try access token cookie first
        const r = await fetch(`${apiUrl}/api/auth/me`, {
          credentials: "include",
          headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : undefined,
        });
        if (r.ok) {
          startTransition(() => { setIsAuthenticated(true); setIsLoading(false); });
          return;
        }
        // Access token expired — try refreshing
        const refreshed = await fetch(`${apiUrl}/api/auth/refresh`, {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: refreshToken }),
        });
        if (refreshed.ok) {
          const tokens = await refreshed.json() as TokenResponse;
          storeTokens(tokens);
        } else {
          clearStoredTokens();
        }
        startTransition(() => {
          setIsAuthenticated(refreshed.ok);
          setIsLoading(false);
        });
      } catch {
        startTransition(() => { setIsAuthenticated(false); setIsLoading(false); });
      }
    }
    void checkAuth();
  }, []);

  const login = async (email: string, password: string) => {
    const tokens = await api.post<TokenResponse>("/api/auth/login", { email, password });
    storeTokens(tokens);
    // Urgent (non-transition) so React commits the state before router.push
    // navigates. Belt-and-braces with the AuthGuard's stored-token fallback.
    setIsAuthenticated(true);
    router.push("/dashboard");
  };

  const register = async (email: string, password: string) => {
    const tokens = await api.post<TokenResponse>("/api/auth/register", { email, password });
    storeTokens(tokens);
    setIsAuthenticated(true);
    router.push("/connect");
  };

  const logout = async () => {
    const apiUrl = getApiBaseUrl();
    try {
      await fetch(`${apiUrl}/api/auth/logout`, { method: "POST", credentials: "include" });
    } catch { /* ignore — clear local state regardless */ }
    clearStoredTokens();
    setIsAuthenticated(false);
    router.push("/login");
  };

  return (
    <AuthContext.Provider value={{ isAuthenticated, isLoading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
