"use client";

import { useEffect, useState } from "react";
import { mk } from "./tokens";

// Display-only mirror of the backend catalogue (app/routes/presale.py). The
// server is authoritative on price; these values only render the cards.
const TIERS = [
  {
    key: "annual",
    label: "Founding Year",
    price: "£59",
    cadence: "first year, price locked",
    blurb: "One year of Premium at the founding rate — locked for as long as you stay.",
  },
  {
    key: "lifetime",
    label: "Founding Lifetime",
    price: "£149",
    cadence: "once, then never again",
    blurb: "Premium for life. Pay once. Best value if you're in for the long run.",
  },
] as const;

type TierKey = (typeof TIERS)[number]["key"];

export function FoundingForm({ dark = false }: { dark?: boolean }) {
  const [email, setEmail] = useState("");
  const [tier, setTier] = useState<TierKey>("lifetime");
  const [status, setStatus] = useState<"idle" | "loading" | "done" | "error">("idle");
  const [error, setError] = useState("");
  const [seats, setSeats] = useState<{ remaining: number; total: number } | null>(null);
  // Server decides whether we take money ("charge") or just capture intent
  // ("reserve"). Defaults to the safe reserve flow until the seats call says
  // otherwise, so no charge UI ever flashes before we know.
  const [mode, setMode] = useState<"reserve" | "charge">("reserve");

  useEffect(() => {
    fetch("/api/presale/seats")
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (!d) return;
        setSeats({ remaining: d.remaining, total: d.total });
        if (d.mode === "charge") setMode("charge");
      })
      .catch(() => {});
  }, []);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!email.trim()) return;
    setStatus("loading");
    setError("");
    try {
      const endpoint = mode === "charge" ? "/api/presale/checkout" : "/api/presale/reserve";
      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim(), tier }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.detail || data.error || "Something went wrong.");
      }
      if (mode === "charge") {
        if (!data.checkout_url) throw new Error("Could not start checkout.");
        window.location.href = data.checkout_url;
        return;
      }
      setStatus("done");
    } catch (err) {
      setStatus("error");
      setError(err instanceof Error ? err.message : "Something went wrong.");
    }
  }

  const soldOut = seats != null && seats.remaining <= 0;
  const muted = dark ? mk.creamDim : mk.pencil;
  const fg = dark ? mk.cream : mk.ink;

  const selectedTier = TIERS.find((t) => t.key === tier);

  if (status === "done") {
    return (
      <div style={{ width: "100%", maxWidth: 520 }}>
        <p
          style={{
            fontFamily: mk.display,
            fontSize: "clamp(20px,2.4vw,26px)",
            fontWeight: 500,
            color: fg,
            margin: "0 0 10px",
            lineHeight: 1.3,
          }}
        >
          ✓ Your{" "}
          <span style={{ color: mk.accent, fontStyle: "italic" }}>{selectedTier?.label}</span>{" "}
          seat is reserved.
        </p>
        <p style={{ fontFamily: mk.sans, fontSize: 14.5, color: muted, lineHeight: 1.6, margin: 0 }}>
          No payment now — we&apos;ve locked your founding price. We&apos;ll email you to complete
          it the moment we open the doors, before the public launch. Check your inbox.
        </p>
      </div>
    );
  }

  return (
    <form onSubmit={submit} style={{ width: "100%", maxWidth: 520 }}>
      {/* Tier cards */}
      <div style={{ display: "flex", flexDirection: "column", gap: 10, marginBottom: 16 }}>
        {TIERS.map((t) => {
          const active = tier === t.key;
          return (
            <button
              type="button"
              key={t.key}
              onClick={() => setTier(t.key)}
              style={{
                textAlign: "left",
                display: "flex",
                alignItems: "center",
                gap: 14,
                padding: "16px 18px",
                borderRadius: 14,
                cursor: "pointer",
                background: active
                  ? dark
                    ? "rgba(193,73,42,0.14)"
                    : mk.accentSoft
                  : dark
                    ? "rgba(255,255,255,0.04)"
                    : mk.card,
                border: `1.5px solid ${active ? mk.accent : dark ? "rgba(255,255,255,0.12)" : mk.pencilLight}`,
                transition: "border-color 120ms, background 120ms",
              }}
            >
              <span
                style={{
                  width: 18,
                  height: 18,
                  borderRadius: 999,
                  flexShrink: 0,
                  border: `2px solid ${active ? mk.accent : muted}`,
                  background: active ? mk.accent : "transparent",
                  boxShadow: active ? `inset 0 0 0 3px ${dark ? mk.night : mk.card}` : "none",
                }}
              />
              <span style={{ flex: 1, minWidth: 0 }}>
                <span style={{ display: "flex", alignItems: "baseline", gap: 8, flexWrap: "wrap" }}>
                  <span style={{ fontFamily: mk.sans, fontWeight: 600, fontSize: 16, color: fg }}>
                    {t.label}
                  </span>
                  <span style={{ fontFamily: mk.sans, fontWeight: 600, fontSize: 16, color: mk.accent }}>
                    {t.price}
                  </span>
                  <span style={{ fontFamily: mk.mono, fontSize: 11, color: muted }}>
                    {t.cadence}
                  </span>
                </span>
                <span
                  style={{
                    display: "block",
                    fontFamily: mk.sans,
                    fontSize: 13,
                    color: muted,
                    marginTop: 3,
                    lineHeight: 1.4,
                  }}
                >
                  {t.blurb}
                </span>
              </span>
            </button>
          );
        })}
      </div>

      {/* Email + submit */}
      <div
        style={{
          display: "flex",
          gap: 8,
          background: dark ? "rgba(255,255,255,0.08)" : mk.card,
          padding: 6,
          borderRadius: 999,
          border: `1px solid ${dark ? "rgba(255,255,255,0.15)" : mk.pencilLight}`,
        }}
      >
        <input
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="you@email.com"
          disabled={soldOut}
          style={{
            flex: 1,
            padding: "12px 18px",
            background: "transparent",
            border: "none",
            outline: "none",
            fontFamily: mk.sans,
            fontSize: 15,
            color: fg,
            minWidth: 0,
          }}
        />
        <button
          type="submit"
          disabled={status === "loading" || soldOut}
          style={{
            padding: "12px 22px",
            background: soldOut ? muted : mk.accent,
            color: "#fff",
            border: "none",
            borderRadius: 999,
            cursor: status === "loading" || soldOut ? "default" : "pointer",
            fontFamily: mk.sans,
            fontWeight: 500,
            fontSize: 15,
            whiteSpace: "nowrap",
            opacity: status === "loading" ? 0.7 : 1,
          }}
        >
          {soldOut
            ? "Sold out"
            : status === "loading"
              ? mode === "charge"
                ? "Opening checkout…"
                : "Reserving…"
              : "Reserve my seat →"}
        </button>
      </div>

      {/* Reassurance + scarcity */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: 12,
          marginTop: 12,
          flexWrap: "wrap",
        }}
      >
        <span style={{ fontFamily: mk.mono, fontSize: 11, color: muted, letterSpacing: "0.03em" }}>
          {mode === "charge"
            ? "Secure checkout via Stripe · refundable until launch"
            : "No payment now · your founding price, locked"}
        </span>
        {seats != null && !soldOut && (
          <span style={{ fontFamily: mk.mono, fontSize: 11, color: mk.accent, letterSpacing: "0.03em" }}>
            {seats.remaining} of {seats.total} founding seats left
          </span>
        )}
      </div>

      {status === "error" && (
        <p style={{ fontFamily: mk.sans, fontSize: 13, color: mk.accent, marginTop: 10 }}>{error}</p>
      )}

      <p style={{ fontFamily: mk.sans, fontSize: 12, color: muted, marginTop: 12, lineHeight: 1.5 }}>
        By reserving a seat you agree to our{" "}
        <a href="/terms" style={{ color: mk.accent, textDecoration: "none" }}>
          Terms
        </a>{" "}
        and{" "}
        <a href="/refunds" style={{ color: mk.accent, textDecoration: "none" }}>
          Refund Policy
        </a>
        . penKeep is a research tool, not financial advice.
      </p>
    </form>
  );
}
