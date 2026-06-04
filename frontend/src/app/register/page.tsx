"use client";

import { useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { AuthShell } from "@/components/auth/auth-shell";
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
    <AuthShell
      eyebrow="Create Account"
      title="Create your account."
      description="Start with a few positions and write down why you own them."
      asideHeading="Start"
      asideBody="One to three names is enough."
      asideItems={[
        {
          eyebrow: "First step",
          title: "Add a few names.",
          body: "You do not need a full import to feel the product.",
        },
        {
          eyebrow: "Outcome",
          title: "Make the case explicit.",
          body: "Write what must stay true and what would break it.",
        },
      ]}
      footer={(
        <p className="font-mono text-[10px] text-muted-foreground/70 text-center">
          Already have an account?{" "}
          <Link href="/login" className="underline underline-offset-2 hover:text-foreground transition-colors">
            Sign in
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
      </div>
    </AuthShell>
  );
}
