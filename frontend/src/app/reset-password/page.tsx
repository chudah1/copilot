"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import { AuthShell } from "@/components/auth/auth-shell";
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
      <AuthShell
        eyebrow="Password Reset"
        title="Invalid link."
        description="Request a new reset link."
        asideHeading="Try again"
        asideBody="Use the newest reset email."
        asideItems={[
          {
            eyebrow: "Link",
            title: "Open the newest one.",
            body: "Older reset emails may no longer work.",
          },
        ]}
        footer={(
          <p className="font-mono text-[10px] text-muted-foreground/70 text-center">
            <Link href="/forgot-password" className="underline underline-offset-2 hover:text-foreground transition-colors">
              Request a new reset link
            </Link>
          </p>
        )}
      >
        <div className="max-w-sm space-y-4">
          <p className="font-sans text-sm text-muted-foreground leading-relaxed">
            Request another reset email and open the newest link instead.
          </p>
        </div>
      </AuthShell>
    );
  }

  return (
    <AuthShell
      eyebrow="Password Reset"
      title="Set a new password."
      description="You will sign in again after this."
      asideHeading="After reset"
      asideBody="Head back to sign in."
      asideItems={[
        {
          eyebrow: "Password",
          title: "Use something you can keep.",
          body: "At least 8 characters.",
        },
      ]}
    >
      <div className="max-w-sm">
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
    </AuthShell>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense>
      <ResetPasswordInner />
    </Suspense>
  );
}
