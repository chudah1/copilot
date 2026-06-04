"use client";

import { useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { AuthShell } from "@/components/auth/auth-shell";
import { Button } from "@/components/ui/button";
import { getErrorMessage } from "@/lib/errors";

const inputCls = "w-full border border-border bg-background px-3 py-2 font-sans text-sm text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:border-foreground/30";

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
    <AuthShell
      eyebrow={sent ? "Email Sent" : "Password Reset"}
      title={sent ? "Check your inbox." : "Reset your password."}
      description={sent
        ? "If the address exists, the reset link is already on its way."
        : "We will send a reset link without confirming whether the address has an account."}
      asideHeading="What to expect"
      asideBody="Password reset should feel calm and obvious, not like a dead end."
      asideItems={[
        {
          eyebrow: "Delivery",
          title: "The email usually arrives quickly.",
          body: "If it is not there within a minute, check spam and then try again.",
        },
        {
          eyebrow: "Access",
          title: "Use the newest link.",
          body: "Fresh reset links are the safest way back in if you requested more than one.",
        },
      ]}
      footer={(
        <p className="font-mono text-[10px] text-muted-foreground/70 text-center">
          <Link href="/login" className="underline underline-offset-2 hover:text-foreground transition-colors">
            Back to sign in
          </Link>
        </p>
      )}
    >
      <div className="max-w-sm">
        {sent ? (
          <div className="space-y-4">
            <p className="font-sans text-sm text-muted-foreground leading-relaxed">
              If <span className="text-foreground">{email}</span> has an account, a reset link is on its way. Check your spam folder if it doesn&apos;t arrive within a minute.
            </p>
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
                className={inputCls}
              />
            </div>

            {error && (
              <p className="font-sans text-sm text-destructive" role="alert">{error}</p>
            )}

            <Button type="submit" className="w-full" loading={loading}>
              <span className="font-mono text-[11px] uppercase tracking-[0.15em]">Send reset link</span>
            </Button>
          </form>
        )}
      </div>
    </AuthShell>
  );
}
