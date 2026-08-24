"use client";

import { useState } from "react";
import { getApiBaseUrl } from "@/lib/api-base";
import { mk } from "./tokens";

export function WaitlistForm({ dark = false }: { dark?: boolean }) {
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState<"idle" | "loading" | "done" | "error">("idle");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!email.trim()) return;
    setStatus("loading");
    try {
      const res = await fetch(`${getApiBaseUrl()}/api/waitlist`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim() }),
      });
      if (!res.ok) throw new Error();
      setStatus("done");
    } catch {
      setStatus("error");
    }
  }

  if (status === "done") {
    return (
      <p
        role="status"
        style={{
          fontFamily: mk.mono,
          fontSize: 13,
          lineHeight: 1.6,
          color: mk.green,
          letterSpacing: "0.04em",
          margin: 0,
          maxWidth: 500,
        }}
      >
        ✓ You&apos;re on the list. We&apos;ll be in touch.
      </p>
    );
  }

  return (
    <div style={{ width: "100%", maxWidth: 500 }}>
      {/* Stacks on phones, collapses into a single pill from `sm` up. The
          layout lives in classes rather than the style object so the
          breakpoint can actually apply — inline styles can't hold a media
          query, and the row is far too tight for an email field at 375px. */}
      <form
        onSubmit={submit}
        className="flex w-full flex-col gap-2 rounded-2xl p-2 sm:flex-row sm:items-stretch sm:gap-2 sm:rounded-full sm:p-1.5"
        style={{
          background: dark ? "rgba(255,255,255,0.08)" : mk.card,
          border: `1px solid ${dark ? "rgba(255,255,255,0.15)" : mk.pencilLight}`,
        }}
      >
        <input
          type="email"
          name="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="you@email.com"
          aria-label="Email address"
          autoComplete="email"
          inputMode="email"
          autoCapitalize="none"
          autoCorrect="off"
          spellCheck={false}
          enterKeyHint="go"
          className="min-h-[48px] w-full flex-1 px-4 sm:w-auto sm:px-[18px]"
          style={{
            background: "transparent",
            border: "none",
            outline: "none",
            fontFamily: mk.sans,
            // 16px keeps iOS Safari from zooming the page in on focus.
            fontSize: 16,
            color: dark ? mk.paper : mk.ink,
            minWidth: 0,
          }}
        />
        <button
          type="submit"
          disabled={status === "loading"}
          className="min-h-[48px] w-full shrink-0 px-6 sm:w-auto"
          style={{
            background: dark ? mk.accent : mk.ink,
            color: mk.paper,
            border: "none",
            borderRadius: 999,
            cursor: status === "loading" ? "default" : "pointer",
            fontFamily: mk.sans,
            fontWeight: 500,
            fontSize: 15,
            whiteSpace: "nowrap",
            opacity: status === "loading" ? 0.7 : 1,
          }}
        >
          {status === "loading" ? "Joining…" : "Join waitlist →"}
        </button>
      </form>

      {status === "error" && (
        <p
          role="alert"
          style={{
            fontFamily: mk.sans,
            fontSize: 13,
            lineHeight: 1.5,
            color: mk.accent,
            margin: "10px 0 0",
          }}
        >
          That didn&apos;t go through. Check the address and try again.
        </p>
      )}
    </div>
  );
}
