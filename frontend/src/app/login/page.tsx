"use client";

import { useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { AuthShell } from "@/components/auth/auth-shell";
import { Button } from "@/components/ui/button";
import { getErrorMessage } from "@/lib/errors";

const inputCls = "w-full border border-border bg-background px-3 py-2 font-sans text-sm text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:border-foreground/30";

export default function LoginPage() {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(email, password);
    } catch (error: unknown) {
      setError(getErrorMessage(error, "Login failed"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthShell
      eyebrow="Sign In"
      title="Welcome back."
      description="Pick up your positions, review queue, and thesis changes where you left them."
      asideHeading="Inside your account"
      asideBody="The product opens on what needs thought first, not on a generic watchlist."
      asideItems={[
        {
          eyebrow: "Review",
          title: "See what needs judgment first.",
          body: "Weak theses, stale names, and live pressure surface before the quiet holdings do.",
        },
        {
          eyebrow: "History",
          title: "Keep the decision record intact.",
          body: "Every thesis, review, and conviction note stays attached to the position it belongs to.",
        },
      ]}
      footer={(
        <p className="font-mono text-[10px] text-muted-foreground/70 text-center">
          No account?{" "}
          <Link href="/register" className="underline underline-offset-2 hover:text-foreground transition-colors">
            Sign up
          </Link>
        </p>
      )}
    >
      <div className="max-w-sm">
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
            <div className="flex items-center justify-between">
              <label htmlFor="password" className="font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground">
                Password
              </label>
              <Link
                href="/forgot-password"
                className="font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground/60 hover:text-foreground transition-colors"
              >
                Forgot?
              </Link>
            </div>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className={inputCls}
            />
          </div>

          {error && (
            <p className="font-sans text-sm text-destructive" role="alert">
              {error}
            </p>
          )}

          <Button type="submit" className="w-full" loading={loading}>
            <span className="font-mono text-[11px] uppercase tracking-[0.15em]">Sign in</span>
          </Button>
        </form>
      </div>
    </AuthShell>
  );
}
