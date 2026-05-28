"use client";

import { useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { getErrorMessage } from "@/lib/errors";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await api.post("/api/auth/forgot-password", { email });
      setSent(true);
    } catch (err: unknown) {
      setError(getErrorMessage(err, "Something went wrong"));
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
            {sent ? "Check your inbox." : "Reset your password."}
          </h1>
        </div>

        {sent ? (
          <div className="space-y-4">
            <p className="font-sans text-sm text-muted-foreground leading-relaxed">
              If <span className="text-foreground">{email}</span> has an account, a reset link is on its way. Check your spam folder if it doesn&apos;t arrive within a minute.
            </p>
            <Link
              href="/login"
              className="font-mono text-[10px] uppercase tracking-[0.15em] text-primary hover:text-primary/70 transition-colors block"
            >
              ← Back to sign in
            </Link>
          </div>
        ) : (
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
                autoFocus
                className="w-full border border-border bg-background px-3 py-2 font-sans text-sm text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:border-foreground/30"
              />
            </div>

            {error && (
              <p className="font-sans text-sm text-destructive" role="alert">{error}</p>
            )}

            <Button type="submit" className="w-full" loading={loading}>
              <span className="font-mono text-[11px] uppercase tracking-[0.15em]">Send reset link</span>
            </Button>

            <p className="font-mono text-[10px] text-muted-foreground/70 text-center">
              <Link href="/login" className="underline underline-offset-2 hover:text-foreground transition-colors">
                Back to sign in
              </Link>
            </p>
          </form>
        )}
      </div>
    </div>
  );
}
