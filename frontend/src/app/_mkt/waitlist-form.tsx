"use client";

import { useState } from "react";
import { mk } from "./tokens";

export function WaitlistForm({ dark = false }: { dark?: boolean }) {
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState<"idle" | "loading" | "done" | "error">("idle");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!email.trim()) return;
    setStatus("loading");
    try {
      const res = await fetch("/api/waitlist", {
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
        style={{
          fontFamily: mk.mono,
          fontSize: 13,
          color: dark ? mk.green : mk.green,
          letterSpacing: "0.04em",
        }}
      >
        ✓ You&apos;re on the list. We&apos;ll be in touch.
      </p>
    );
  }

  return (
    <form
      onSubmit={submit}
      style={{
        display: "flex",
        flexDirection: "row",
        gap: 8,
        alignItems: "stretch",
        background: dark ? "rgba(255,255,255,0.08)" : mk.card,
        padding: 6,
        borderRadius: 999,
        border: `1px solid ${dark ? "rgba(255,255,255,0.15)" : mk.pencilLight}`,
        width: "100%",
        maxWidth: 500,
      }}
    >
      <input
        type="email"
        required
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        placeholder="you@email.com"
        style={{
          flex: 1,
          padding: "12px 18px",
          background: "transparent",
          border: "none",
          outline: "none",
          fontFamily: mk.sans,
          fontSize: 15,
          color: dark ? mk.paper : mk.ink,
          minWidth: 0,
        }}
      />
      <button
        type="submit"
        disabled={status === "loading"}
        style={{
          padding: "12px 22px",
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
      {status === "error" && (
        <span style={{ fontSize: 12, color: mk.accent, alignSelf: "center", paddingRight: 8 }}>
          Try again
        </span>
      )}
    </form>
  );
}
