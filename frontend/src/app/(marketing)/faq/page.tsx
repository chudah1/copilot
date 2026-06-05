"use client";

import { useState } from "react";
import { LaunchActions } from "../../_mkt/launch-actions";
import { mk } from "../../_mkt/tokens";

const FAQS = [
  {
    cat: "The product",
    items: [
      ["Will penKeep tell me what to buy?",
        "No, and we don't intend to. penKeep is not an advisor, broker, or stock picker. It's a tool for writing down why you bought, and noticing when that reason might have changed."],
      ["What's the thesis health score?",
        "A number from 0 to 100 that reflects how well the picture has held up since you wrote your thesis. Healthy (75 and above) means the signals are broadly supportive. At Risk (45 to 74) means some things have moved against you. Broken is below 45: the core of the reason has weakened. It's not a buy or sell signal. It's a prompt to re-read what you wrote."],
      ["What if I'm a complete beginner?",
        "We can help, but we're not a learning app. If you don't yet have a reason for owning a stock, you probably haven't done the work. penKeep can't substitute for it. That's by design."],
      ["What stocks does it support?",
        "Major listings on US (NYSE, NASDAQ), UK (LSE), and major European exchanges at launch. Crypto, options, and ETFs are not in scope for v1."],
    ],
  },
  {
    cat: "Signals & alerts",
    items: [
      ["What kinds of signals do you watch?",
        "Earnings & guidance, news & press releases, SEC filings (10-Q, 8-K), earnings call transcripts, insider transactions, and price moves relative to your thesis."],
      ["How often will I hear from you?",
        "Almost never. The product is silent by default. The only push you'll get is a \"your reason may have changed\" note, typically a few per quarter across a portfolio of 10 to 15 stocks."],
      ["What if a signal is wrong?",
        "Every signal has sources you can click. If we flagged something that doesn't actually touch your reason, hit dismiss and we'll learn from it."],
      ["Do you predict prices?",
        "No. Price is one signal among many, and we treat it as evidence, not as a recommendation."],
    ],
  },
  {
    cat: "Connections & data",
    items: [
      ["Will it connect to my broker?",
        "Optional, and read-only. We can read your positions to save you re-typing. We don't read your trade history. We don't execute trades. We never will."],
      ["Which brokers are supported?",
        "At launch: Trading 212, plus CSV upload. We're adding more through 2026."],
      ["Where is my data?",
        "Encrypted at rest. Your thesis notes are scoped to your account; we don't read them for ad targeting, and we don't sell them. Email privacy@penkeep.io to request an export or to delete your account."],
    ],
  },
  {
    cat: "Money",
    items: [
      ["How do you make money?",
        "Subscription. Free tier lets you keep up to 5 active theses, and the premium tier unlocks unlimited theses, broker connections, full history, and the counter-thesis assistant. Pricing announced closer to launch."],
      ["Will there ever be ads?",
        "No. Showing you a sponsored \"hot stock\" would break the whole product."],
      ["Are you regulated?",
        "penKeep is a research and journaling tool, not an investment advisor or broker-dealer. Nothing in the app is a recommendation. We're set up that way on purpose."],
    ],
  },
] as const;

const CATEGORY_INTROS: Record<string, string> = {
  "The product": "What penKeep is, what it is not, and who it is actually built for.",
  "Signals & alerts": "How the product decides when to stay quiet and when a reason may have changed.",
  "Connections & data": "What gets connected, what does not, and how your information is treated.",
  Money: "How the business works without turning the app into a feed of incentives and noise.",
};

function FAQItem({ q, a, defaultOpen }: { q: string; a: string; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(!!defaultOpen);
  return (
    <div
      style={{
        border: `1px solid ${open ? mk.accent : mk.pencilLight}`,
        borderRadius: 16,
        background: open ? mk.paperHi : mk.card,
        padding: "0 18px",
        transition: "all 220ms ease",
      }}
    >
      <button
        onClick={() => setOpen((o) => !o)}
        style={{
          all: "unset",
          cursor: "pointer",
          display: "flex",
          alignItems: "center",
          gap: 18,
          padding: "20px 0 18px",
          width: "100%",
          textAlign: "left",
        }}
      >
        <span style={{ flex: 1, fontFamily: mk.sans, fontSize: 18, fontWeight: 500, lineHeight: 1.35, letterSpacing: "-0.01em", color: mk.ink }}>
          {q}
        </span>
        <span
          style={{
            width: 28,
            height: 28,
            borderRadius: 999,
            border: `1.4px solid ${mk.pencilLight}`,
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: 16,
            flex: "0 0 28px",
            transition: "all 220ms ease",
            background: open ? mk.ink : "transparent",
            color: open ? mk.paper : mk.ink,
          }}
        >
          {open ? "−" : "+"}
        </span>
      </button>
      {open && (
        <div
          style={{
            paddingBottom: 20,
            fontFamily: mk.sans,
            fontSize: 16,
            lineHeight: 1.6,
            color: mk.inkSoft,
            maxWidth: 760,
            animation: "mkFadeIn 240ms ease-out",
          }}
        >
          {a}
        </div>
      )}
    </div>
  );
}

export default function FAQPage() {
  const pad = "clamp(22px, 4.5vw, 56px)";
  return (
    <>
      {/* Header */}
      <section style={{ padding: `clamp(50px,8vw,110px) ${pad} clamp(32px,4vw,60px)` }}>
        <div style={{ fontFamily: mk.mono, fontSize: 11, letterSpacing: "0.14em", textTransform: "uppercase", color: mk.pencil, marginBottom: 14 }}>
          FAQ
        </div>
        <h1
          style={{
            fontFamily: mk.sans,
            fontWeight: 600,
            fontSize: "clamp(48px,8vw,96px)",
            lineHeight: 1,
            letterSpacing: "-0.035em",
            margin: 0,
          }}
        >
          Questions<br />
          <span style={{ color: mk.accent }}>you&apos;ll probably ask.</span>
        </h1>
        <p style={{ fontFamily: mk.sans, fontSize: "clamp(17px,1.8vw,19px)", lineHeight: 1.55, color: mk.pencil, marginTop: "clamp(18px,2vw,24px)", maxWidth: 600 }}>
          The short answers are here. If you have something else,
          email <span style={{ color: mk.ink, fontWeight: 500 }}>hi@penkeep.io</span>.
        </p>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
            gap: 12,
            marginTop: "clamp(24px,3vw,32px)",
            maxWidth: 920,
          }}
          className="max-md:grid-cols-1"
        >
          {[
            ["No stock tips", "The product never tells you what to buy."],
            ["Quiet by default", "Most weeks, if nothing relevant changed, it says nothing."],
            ["Read-only data", "Broker links are optional and never execute trades."],
          ].map(([label, value]) => (
            <div
              key={label}
              style={{
                background: mk.card,
                border: `1px solid ${mk.pencilLight}`,
                borderRadius: 16,
                padding: "16px 18px",
              }}
            >
              <div style={{ fontFamily: mk.mono, fontSize: 10, letterSpacing: "0.14em", textTransform: "uppercase", color: mk.pencil }}>
                {label}
              </div>
              <div style={{ fontFamily: mk.sans, fontSize: 15, lineHeight: 1.45, color: mk.inkSoft, marginTop: 8 }}>
                {value}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Categories */}
      <section style={{ padding: `0 ${pad} clamp(70px,8vw,130px)` }}>
        {FAQS.map((cat, ci) => (
          <div key={cat.cat} style={{ marginBottom: 50 }}>
            <div
              style={{
                background: mk.card,
                border: `1px solid ${mk.pencilLight}`,
                borderRadius: 18,
                padding: "22px 22px 18px",
                marginBottom: 14,
              }}
            >
              <div
                style={{
                  fontFamily: mk.mono,
                  fontSize: 11,
                  letterSpacing: "0.14em",
                  textTransform: "uppercase",
                  color: mk.accent,
                  marginBottom: 10,
                }}
              >
                § {cat.cat}
              </div>
              <div
                style={{
                  fontFamily: mk.sans,
                  fontSize: 15,
                  lineHeight: 1.55,
                  color: mk.inkSoft,
                  maxWidth: 760,
                }}
              >
                {CATEGORY_INTROS[cat.cat] ?? ""}
              </div>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {cat.items.map(([q, a], i) => (
                <FAQItem key={q} q={q} a={a} defaultOpen={ci === 0 && i === 0} />
              ))}
            </div>
          </div>
        ))}
      </section>

      {/* CTA */}
      <section style={{ padding: `clamp(50px,8vw,100px) ${pad}`, background: mk.ink, color: mk.paper }}>
        <div style={{ maxWidth: 760 }}>
          <div style={{ fontFamily: mk.mono, fontSize: 11, letterSpacing: "0.14em", textTransform: "uppercase", color: "#8f877d", marginBottom: 12 }}>
            Try the product
          </div>
        <h2 style={{ fontFamily: mk.sans, fontSize: "clamp(36px,5vw,56px)", fontWeight: 600, margin: 0, lineHeight: 1, letterSpacing: "-0.03em" }}>
          Still curious? <span style={{ color: mk.accent }}>Just try it.</span>
        </h2>
        <p style={{ fontFamily: mk.sans, fontSize: "clamp(15px,1.6vw,17px)", color: "#bdb4ab", lineHeight: 1.6, margin: "16px 0 0", maxWidth: 560 }}>
          The fastest way to understand penKeep is to put one real position through the thesis and review loop.
        </p>
        </div>
        <div style={{ marginTop: "clamp(24px,3vw,36px)" }}>
          <LaunchActions dark />
        </div>
      </section>
    </>
  );
}
