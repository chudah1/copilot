"use client";

import { useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { getErrorMessage } from "@/lib/errors";

const inputCls = "w-full border border-border bg-background px-3 py-2 font-sans text-sm text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:border-foreground/30";

export default function RegisterPage() {
  const { register } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const passwordOk = password.length >= 8;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (!passwordOk) {
      setError("Password must be at least 8 characters");
      return;
    }
    setLoading(true);
    try {
      await register(email, password);
    } catch (error: unknown) {
      setError(getErrorMessage(error, "Registration failed"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-sm border border-border/60 bg-card p-8 space-y-6">
        <div>
          <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground mb-2">
            penKeep
          </p>
          <h1 className="font-display italic text-[2rem] leading-tight text-foreground">
            Keep your thinking honest.
          </h1>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <label htmlFor="email" className="font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground block">
              Email
            </label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className={inputCls}
            />
          </div>

          <div className="space-y-1.5">
            <label htmlFor="password" className="font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground block">
              Password
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className={inputCls}
            />
            {password.length > 0 && (
              <p className={`font-mono text-[10px] tracking-[0.1em] transition-colors ${passwordOk ? "text-emerald-600" : "text-muted-foreground/60"}`}>
                {passwordOk ? "✓ 8+ characters" : `${password.length}/8 characters`}
              </p>
            )}
          </div>

          {error && (
            <p className="font-sans text-sm text-destructive" role="alert">
              {error}
            </p>
          )}

          <Button type="submit" className="w-full" loading={loading} disabled={password.length > 0 && !passwordOk}>
            <span className="font-mono text-[11px] uppercase tracking-[0.15em]">Create account</span>
          </Button>
        </form>

        <p className="font-mono text-[10px] text-muted-foreground/70 text-center">
          Already have an account?{" "}
          <Link href="/login" className="underline underline-offset-2 hover:text-foreground transition-colors">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
