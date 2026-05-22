"use client";

import { createContext, useContext, useEffect, useState, ReactNode, startTransition } from "react";
import { useRouter } from "next/navigation";
import { api } from "./api";
import type { TokenResponse } from "@/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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
      try {
        // Try access token cookie first
        let r = await fetch(`${API_URL}/api/auth/me`, { credentials: "include" });
        if (r.ok) {
          startTransition(() => { setIsAuthenticated(true); setIsLoading(false); });
          return;
        }
        // Access token expired — try refreshing
        const refreshed = await fetch(`${API_URL}/api/auth/refresh`, {
          method: "POST",
          credentials: "include",
        });
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
    await api.post<TokenResponse>("/api/auth/login", { email, password });
    setIsAuthenticated(true);
    router.push("/dashboard");
  };

  const register = async (email: string, password: string) => {
    await api.post<TokenResponse>("/api/auth/register", { email, password });
    setIsAuthenticated(true);
    router.push("/connect");
  };

  const logout = async () => {
    try {
      await fetch(`${API_URL}/api/auth/logout`, { method: "POST", credentials: "include" });
    } catch { /* ignore — clear local state regardless */ }
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
