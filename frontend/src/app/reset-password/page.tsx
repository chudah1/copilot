"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { getErrorMessage } from "@/lib/errors";

const inputCls = "w-full border border-border bg-background px-3 py-2 font-sans text-sm text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:border-foreground/30";

function ResetPasswordInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get("token") ?? "";

  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const passwordOk = password.length >= 8;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (!passwordOk) {
      setError("Password must be at least 8 characters");
      return;
    }
    if (!token) {
      setError("Invalid reset link — please request a new one.");
      return;
    }
    setLoading(true);
    try {
      await api.post("/api/auth/reset-password", { token, new_password: password });
      router.push("/login?reset=1");
    } catch (err: unknown) {
      setError(getErrorMessage(err, "Reset failed — the link may have expired."));
    } finally {
      setLoading(false);
    }
  };

  if (!token) {
    return (
      <div className="flex min-h-screen items-center justify-center px-4">
        <div className="w-full max-w-sm border border-border/60 bg-card p-8 space-y-4">
          <div>
            <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground mb-2">
              penKeep
            </p>
            <h1 className="font-display italic text-[2rem] leading-tight text-foreground">
              Invalid link.
            </h1>
          </div>
          <p className="font-sans text-sm text-muted-foreground leading-relaxed">
            This reset link is missing or malformed.
          </p>
          <Link
            href="/forgot-password"
            className="font-mono text-[10px] uppercase tracking-[0.15em] text-primary hover:text-primary/70 transition-colors block"
          >
            Request a new reset link →
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-sm border border-border/60 bg-card p-8 space-y-6">
        <div>
          <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground mb-2">
            penKeep
          </p>
          <h1 className="font-display italic text-[2rem] leading-tight text-foreground">
            New password.
          </h1>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <label htmlFor="password" className="font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground block">
              New password
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoFocus
              className={inputCls}
            />
            {password.length > 0 && (
              <p className={`font-mono text-[10px] tracking-[0.1em] transition-colors ${passwordOk ? "text-emerald-600" : "text-muted-foreground/60"}`}>
                {passwordOk ? "✓ 8+ characters" : `${password.length}/8 characters`}
              </p>
            )}
          </div>

          {error && (
            <p className="font-sans text-sm text-destructive" role="alert">{error}</p>
          )}

          <Button type="submit" className="w-full" loading={loading} disabled={password.length > 0 && !passwordOk}>
            <span className="font-mono text-[11px] uppercase tracking-[0.15em]">Set new password</span>
          </Button>
        </form>
      </div>
    </div>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense>
      <ResetPasswordInner />
    </Suspense>
  );
}
