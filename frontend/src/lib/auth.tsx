"use client";

import { createContext, useContext, useEffect, useState, ReactNode, startTransition } from "react";
import { useRouter } from "next/navigation";
import { api } from "./api";
import type { TokenResponse } from "@/types";

interface AuthContextType {
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const router = useRouter();

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    startTransition(() => {
      setIsAuthenticated(!!token);
      setIsLoading(false);
    });
  }, []);

  const handleTokens = (data: TokenResponse) => {
    localStorage.setItem("access_token", data.access_token);
    localStorage.setItem("refresh_token", data.refresh_token);
    setIsAuthenticated(true);
  };

  const login = async (email: string, password: string) => {
    const data = await api.post<TokenResponse>("/api/auth/login", { email, password });
    handleTokens(data);
    router.push("/dashboard");
  };

  const register = async (email: string, password: string) => {
    const data = await api.post<TokenResponse>("/api/auth/register", { email, password });
    handleTokens(data);
    router.push("/connect");
  };

  const logout = () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
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
