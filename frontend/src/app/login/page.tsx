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
  const [handoff, setHandoff] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    setHandoff(false);
    try {
      await login(email, password);
      setHandoff(true);
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
      description="Pick up where you left off."
      asideHeading="Inside"
      asideBody="What needs attention shows up first."
      asideItems={[
        {
          eyebrow: "Review",
          title: "Judgment first.",
          body: "Review items surface before quiet holdings.",
        },
        {
          eyebrow: "History",
          title: "Record intact.",
          body: "Theses, reviews, and notes stay with the position.",
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
              disabled={loading || handoff}
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
              disabled={loading || handoff}
              className={inputCls}
            />
          </div>

          {error && (
            <p className="font-sans text-sm text-destructive" role="alert">
              {error}
            </p>
          )}

          {(loading || handoff) && !error && (
            <div className="border border-border/70 bg-background/55 px-3 py-2.5">
              <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-primary">
                {handoff ? "Opening dashboard" : "Signing you in"}
              </p>
              <p className="mt-1 font-sans text-sm leading-relaxed text-foreground/72">
                {handoff
                  ? "Your session is live. Bringing your portfolio and decision inbox into view now."
                  : "Checking your session and pulling your latest portfolio state. This can take a few seconds."}
              </p>
            </div>
          )}

          <Button type="submit" className="w-full" loading={loading}>
            <span className="font-mono text-[11px] uppercase tracking-[0.15em]">
              {handoff ? "Opening dashboard" : loading ? "Signing in" : "Sign in"}
            </span>
          </Button>
        </form>
      </div>
    </AuthShell>
  );
}
