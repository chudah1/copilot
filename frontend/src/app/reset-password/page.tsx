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
        description="This reset link is missing or malformed."
        asideHeading="Next step"
        asideBody="Request a fresh reset email and use the newest link that arrives."
        asideItems={[
          {
            eyebrow: "Retry",
            title: "Generate a new reset link.",
            body: "If you opened an older email, a newer reset request may already have replaced it.",
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
      description="Use a new password you have not used for this account before."
      asideHeading="After reset"
      asideBody="Once this succeeds, you will head back to sign in with the updated password."
      asideItems={[
        {
          eyebrow: "Security",
          title: "Keep it simple but strong.",
          body: "The goal is a password you can reliably use, not a recovery ritual every week.",
        },
        {
          eyebrow: "Access",
          title: "You will sign in again right after.",
          body: "That makes it easy to confirm the reset worked before you move on.",
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
