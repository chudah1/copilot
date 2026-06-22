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
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const router = useRouter();

  useEffect(() => {
    async function checkAuth() {
      const apiUrl = getApiBaseUrl();
      const accessToken = getStoredAccessToken();
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
          body: JSON.stringify({ refresh_token: getStoredRefreshToken() }),
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
    startTransition(() => { setIsAuthenticated(true); });
    router.push("/dashboard");
  };

  const register = async (email: string, password: string) => {
    const tokens = await api.post<TokenResponse>("/api/auth/register", { email, password });
    storeTokens(tokens);
    startTransition(() => { setIsAuthenticated(true); });
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
