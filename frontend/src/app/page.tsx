import { MarketingNav } from "./_mkt/nav";
import { MarketingFooter } from "./_mkt/footer";
import { WaitlistForm } from "./_mkt/waitlist-form";
import { ThesisDemo } from "./_mkt/thesis-demo";
import { WatchThesisChange } from "./_mkt/timeline";
import { ConvictionDemo } from "./_mkt/conviction-demo";
import { mk } from "./_mkt/tokens";

const STEPS_COPY = [
  { n: "01", t: "Write your reason", d: "Not a price target or a template. Why do you own this? Two sentences is plenty. The quality of the reason predicts whether you'll hold through noise or panic-exit at signal." },
  { n: "02", t: "We watch", d: "Earnings transcripts, SEC filings, analyst tone, insider moves — all mapped back to the specific reason you wrote, not just the ticker." },
  { n: "03", t: "You decide", d: "We tell you when something tied to your reason moves. You say whether it changed your mind. That decision is recorded. Permanently." },
];

const QUOTES = [
  { q: "I finally sold TSLA at the right time — not because the chart broke, but because my own exit condition triggered. It was written in penKeep since March.", a: "Beta user, London" },
  { q: "Every other app tells me what the market is doing. penKeep is the first one that checks whether the market is doing what I specifically thought it would.", a: "Beta user, New York" },
  { q: "I wrote my first real thesis in ten minutes. Six months later I can prove I made a rational decision, not an emotional one. That's worth something.", a: "Beta user, Toronto" },
];

const BUILT_FEATURES = [
  {
    label: "Claim-level evidence mapping",
    desc: "We don't just monitor the stock — we map SEC filings, earnings transcripts, and news to the specific claims inside your reason. A 10-K isn't relevant; whether it confirms your margin assumption is.",
  },
  {
    label: "Closed-loop decision record",
    desc: "Every time evidence fires, your original exit condition is surfaced beside it. You decide. We log it. Six months later you'll know whether you called it correctly.",
  },
  {
    label: "Investor profile adaptation",
    desc: "The system detects whether you invest on fundamentals or on stories and adapts the language it uses everywhere — alerts, reviews, digest emails, all of it.",
  },
  {
    label: "Outcome closure",
    desc: "When a thesis is invalidated after an alert, the decision entry is retroactively marked 'Thesis broke.' When you hold, it's marked 'Holding.' Your track record builds itself.",
  },
  {
    label: "Weekly conviction digest",
    desc: "Not a portfolio summary. A letter about your reasons — which ones held this week, which ones are being tested, which ones are overdue for a review.",
  },
  {
    label: "Quarterly review prep",
    desc: "Every quarter, we build a structured review brief for each position. What you said when you bought. What happened. What you decided. What the numbers say now.",
  },
];

export default function LandingPage() {
  const pad = "clamp(22px, 4.5vw, 56px)";

  return (
    <div style={{ background: mk.paper, color: mk.ink, fontFamily: mk.sans, backgroundImage: "none" }}>
      <style>{`
        @keyframes mkPulse  { 0%,100%{opacity:.4} 50%{opacity:1} }
        @keyframes mkFadeIn { from{opacity:0;transform:translateY(4px) scale(.99)} to{opacity:1;transform:none} }
        @keyframes mkSlideIn{ from{opacity:0;transform:translateY(8px)} to{opacity:1;transform:none} }
        @keyframes mkGlow   { 0%,100%{box-shadow:0 0 0 0 transparent} 50%{box-shadow:0 0 32px 8px oklch(0.66 0.16 35 / 0.18)} }
      `}</style>

      <MarketingNav />

      {/* ── HERO ─────────────────────────────────────────────── */}
      <section
        style={{
          background: mk.ink,
          padding: `clamp(40px,7vw,80px) ${pad} clamp(50px,7vw,72px)`,
        }}
      >
        <div
          style={{
            display: "inline-flex",
            gap: 8,
            alignItems: "center",
            padding: "5px 14px",
            background: "rgba(255,255,255,0.07)",
            color: mk.accent,
            border: `1px solid ${mk.accent}44`,
            borderRadius: 999,
            fontSize: 12,
            fontFamily: mk.mono,
            marginBottom: "clamp(22px,3.5vw,32px)",
            letterSpacing: "0.06em",
          }}
        >
          <span
            style={{
              width: 6,
              height: 6,
              borderRadius: 999,
              background: mk.accent,
              display: "inline-block",
              animation: "mkPulse 2s ease-in-out infinite",
            }}
          />
          Private beta · summer 2026
        </div>

        <h1
          style={{
            fontFamily: mk.sans,
            fontWeight: 700,
            fontSize: "clamp(42px,7vw,92px)",
            lineHeight: 1.0,
            letterSpacing: "-0.038em",
            margin: 0,
            maxWidth: 1050,
            color: mk.paper,
          }}
        >
          You bought it for a reason.
          <br />
          <span
            style={{
              background: `linear-gradient(135deg, ${mk.accent} 0%, ${mk.accentDeep} 100%)`,
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
              backgroundClip: "text",
            }}
          >
            Do you still know what it was?
          </span>
        </h1>

        <p
          style={{
            fontFamily: mk.sans,
            fontSize: "clamp(16px,1.9vw,20px)",
            lineHeight: 1.55,
            marginTop: "clamp(20px,3vw,30px)",
            maxWidth: 620,
            color: "#c8c0b0",
          }}
        >
          Write the reason you bought each position. penKeep watches earnings,
          filings, and news against it — and tells you when something that
          matters to <em>your specific reason</em> moves. Then it asks you what
          you decided. And remembers.
        </p>

        <div
          style={{
            marginTop: "clamp(28px,3.5vw,36px)",
            display: "flex",
            flexWrap: "wrap",
            gap: 10,
            alignItems: "center",
          }}
        >
          <a
            href="#signup"
            style={{
              padding: "clamp(13px,1.5vw,15px) clamp(22px,2vw,28px)",
              background: mk.accent,
              color: mk.paper,
              border: "none",
              borderRadius: 999,
              cursor: "pointer",
              fontFamily: mk.sans,
              fontWeight: 600,
              fontSize: "clamp(14px,1.4vw,16px)",
              textDecoration: "none",
              animation: "mkGlow 3s ease-in-out infinite",
            }}
          >
            Join the waitlist →
          </a>
          <a
            href="#demo"
            style={{
              padding: "clamp(13px,1.5vw,15px) clamp(22px,2vw,28px)",
              background: "transparent",
              color: mk.paper,
              border: "1.4px solid rgba(255,255,255,0.25)",
              borderRadius: 999,
              cursor: "pointer",
              fontFamily: mk.sans,
              fontWeight: 500,
              fontSize: "clamp(14px,1.4vw,16px)",
              textDecoration: "none",
            }}
          >
            See how it works ↓
          </a>
        </div>

        {/* Stats strip */}
        <div
          style={{
            marginTop: "clamp(36px,5vw,52px)",
            display: "flex",
            gap: "clamp(28px,5vw,52px)",
            flexWrap: "wrap",
          }}
        >
          {[
            { n: "47", l: "theses written" },
            { n: "312", l: "signals fired" },
            { n: "18", l: "theses invalidated" },
            { n: "6+", l: "months of decisions" },
          ].map(({ n, l }) => (
            <div key={l}>
              <div
                style={{
                  fontFamily: mk.mono,
                  fontSize: "clamp(24px,3vw,36px)",
                  fontWeight: 700,
                  color: mk.paper,
                  letterSpacing: "-0.03em",
                  lineHeight: 1,
                }}
              >
                {n}
              </div>
              <div
                style={{
                  fontFamily: mk.mono,
                  fontSize: 10,
                  letterSpacing: "0.12em",
                  textTransform: "uppercase",
                  color: "#666",
                  marginTop: 4,
                }}
              >
                {l}
              </div>
            </div>
          ))}
        </div>

        <div id="demo" style={{ marginTop: "clamp(44px,6vw,64px)" }}>
          <ThesisDemo />
        </div>
      </section>

      {/* ── THE LOOP ─────────────────────────────────────────── */}
      <section
        style={{
          background: mk.ink,
          padding: `clamp(50px,7vw,90px) ${pad}`,
          borderTop: "1px solid rgba(255,255,255,0.06)",
        }}
      >
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: "clamp(40px,6vw,80px)",
            alignItems: "start",
          }}
          className="max-md:grid-cols-1"
        >
          {/* Left: copy */}
          <div>
            <div
              style={{
                fontFamily: mk.mono,
                fontSize: 11,
                letterSpacing: "0.14em",
                textTransform: "uppercase",
                color: mk.accent,
                marginBottom: 14,
              }}
            >
              Closed-loop accountability
            </div>
            <h2
              style={{
                fontFamily: mk.sans,
                fontWeight: 700,
                fontSize: "clamp(32px,4.5vw,56px)",
                lineHeight: 1.02,
                letterSpacing: "-0.03em",
                margin: 0,
                color: mk.paper,
              }}
            >
              Your exit condition, surfaced the moment it matters.
            </h2>
            <p
              style={{
                fontFamily: mk.sans,
                fontSize: "clamp(15px,1.7vw,18px)",
                lineHeight: 1.55,
                color: "#c8c0b0",
                marginTop: "clamp(16px,2vw,22px)",
                maxWidth: 500,
              }}
            >
              When you write your thesis, you also write the condition that would
              make you change your mind. When evidence fires, we show that
              condition back to you — not the current news feed, not a price
              alert, your own reasoning.
            </p>
            <p
              style={{
                fontFamily: mk.sans,
                fontSize: "clamp(15px,1.7vw,18px)",
                lineHeight: 1.55,
                color: "#c8c0b0",
                marginTop: 14,
                maxWidth: 500,
              }}
            >
              Your decision — hold or invalidate — is logged with the evidence
              that prompted it. Six months later, penKeep knows whether you were
              right.
            </p>
            <div
              style={{
                marginTop: "clamp(24px,3vw,32px)",
                display: "flex",
                flexDirection: "column",
                gap: 12,
              }}
            >
              {[
                "Evidence mapped to your specific claims, not the stock",
                "Your exact words shown back to you at the moment of decision",
                "Decision + outcome permanently recorded in your conviction log",
                "Track record builds automatically — no extra input from you",
              ].map((item) => (
                <div key={item} style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
                  <span
                    style={{
                      width: 6,
                      height: 6,
                      borderRadius: 999,
                      background: mk.green,
                      flexShrink: 0,
                      marginTop: 7,
                    }}
                  />
                  <span
                    style={{ fontFamily: mk.sans, fontSize: 14, color: "#c8c0b0", lineHeight: 1.45 }}
                  >
                    {item}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Right: demo */}
          <div>
            <ConvictionDemo />
          </div>
        </div>
      </section>

      {/* ── TIMELINE ─────────────────────────────────────────── */}
      <section
        style={{
          padding: `clamp(50px,8vw,90px) ${pad}`,
          background: mk.cardSoft,
          borderTop: `1px solid ${mk.pencilLight}`,
          borderBottom: `1px solid ${mk.pencilLight}`,
        }}
      >
        <div style={{ fontFamily: mk.mono, fontSize: 11, letterSpacing: "0.14em", textTransform: "uppercase", color: mk.pencil, marginBottom: 14 }}>
          Watch a thesis change in real time
        </div>
        <h2
          style={{
            fontFamily: mk.sans,
            fontWeight: 700,
            fontSize: "clamp(34px,5vw,60px)",
            lineHeight: 1,
            letterSpacing: "-0.03em",
            margin: 0,
            maxWidth: 950,
          }}
        >
          One real story. <span style={{ color: mk.accent }}>Eight months.</span>
          <br />
          Press play.
        </h2>
        <p
          style={{
            fontFamily: mk.sans,
            fontSize: "clamp(15px,1.7vw,18px)",
            lineHeight: 1.5,
            color: mk.pencil,
            marginTop: 14,
            maxWidth: 620,
          }}
        >
          Someone bought Tesla in March 2024 with a specific reason. Here&apos;s
          how the evidence moved over eight months, and the exact moment penKeep
          would have surfaced their exit condition.
        </p>
        <div style={{ marginTop: "clamp(28px,4vw,44px)" }}>
          <WatchThesisChange />
        </div>
        <p
          style={{
            fontFamily: mk.sans,
            fontSize: 12,
            color: mk.pencil,
            marginTop: 16,
            fontStyle: "italic",
          }}
        >
          Re-created from public coverage of TSLA, Mar–Oct 2024. penKeep does
          not give buy/sell advice.
        </p>
      </section>

      {/* ── BENTO ────────────────────────────────────────────── */}
      <section style={{ padding: `clamp(50px,8vw,100px) ${pad}` }}>
        <div
          style={{
            fontFamily: mk.mono,
            fontSize: 11,
            letterSpacing: "0.14em",
            textTransform: "uppercase",
            color: mk.pencil,
            marginBottom: 14,
          }}
        >
          What&apos;s inside
        </div>
        <h2
          style={{
            fontFamily: mk.sans,
            fontWeight: 700,
            fontSize: "clamp(34px,5vw,56px)",
            lineHeight: 1,
            letterSpacing: "-0.025em",
            margin: 0,
            maxWidth: 800,
          }}
        >
          Built around <span style={{ color: mk.accent }}>your reason</span>,
          not their feed.
        </h2>

        <div
          style={{
            marginTop: "clamp(28px,4vw,44px)",
            display: "grid",
            gridTemplateColumns: "repeat(6, 1fr)",
            gridAutoRows: "minmax(160px, auto)",
            gap: 14,
          }}
          className="max-md:grid-cols-1"
        >
          {/* Big card — diff */}
          <div
            style={{
              gridColumn: "span 4",
              gridRow: "span 2",
              background: mk.card,
              borderRadius: 16,
              padding: 24,
              border: `1px solid ${mk.pencilLight}`,
              display: "flex",
              flexDirection: "column",
              gap: 14,
            }}
            className="max-md:col-span-1 max-md:row-span-1"
          >
            <div
              style={{
                fontFamily: mk.mono,
                fontSize: 11,
                textTransform: "uppercase",
                letterSpacing: "0.1em",
                color: mk.accent,
              }}
            >
              ! reason changed
            </div>
            <div
              style={{
                fontFamily: mk.sans,
                fontSize: "clamp(20px,2.4vw,30px)",
                fontWeight: 600,
                letterSpacing: "-0.02em",
                lineHeight: 1.1,
              }}
            >
              See exactly what changed since you bought.
            </div>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "1fr 16px 1fr",
                gap: 10,
                marginTop: 8,
                fontSize: 13,
              }}
            >
              {[
                ["EV demand growing", "→", "EU deliveries -12% YoY"],
                ["Robotaxi optionality", "→", '"Underwhelming" — 7 of 9'],
                ["Margins protected", "→", "Auto GM 14.3%"],
              ].map(([was, arr, now], i) => (
                <span key={i} style={{ display: "contents" }}>
                  <span
                    style={{
                      color: mk.pencil,
                      textDecoration: "line-through",
                      textDecorationColor: mk.accent,
                    }}
                  >
                    {was}
                  </span>
                  <span style={{ color: mk.accent, textAlign: "center" }}>{arr}</span>
                  <span style={{ color: mk.ink, fontWeight: 500 }}>{now}</span>
                </span>
              ))}
            </div>
            <div
              style={{ fontFamily: mk.sans, fontSize: 13, color: mk.pencil, marginTop: "auto" }}
            >
              The &ldquo;diff since you bought&rdquo; view — your reason, what the data showed, side by side.
            </div>
          </div>

          {/* Conviction log */}
          <div
            style={{
              gridColumn: "span 2",
              background: mk.ink,
              color: mk.paper,
              borderRadius: 16,
              padding: 24,
              display: "flex",
              flexDirection: "column",
              justifyContent: "space-between",
              gap: 14,
              minHeight: 220,
            }}
            className="max-md:col-span-1"
          >
            <div
              style={{
                fontFamily: mk.mono,
                fontSize: 11,
                textTransform: "uppercase",
                letterSpacing: "0.1em",
                color: mk.accent,
              }}
            >
              conviction log
            </div>
            <div>
              <div
                style={{
                  fontFamily: mk.sans,
                  fontSize: "clamp(22px,2.5vw,32px)",
                  fontWeight: 600,
                  letterSpacing: "-0.025em",
                  lineHeight: 1.0,
                }}
              >
                Every decision, forever.
              </div>
              <div style={{ fontSize: 13, color: "#aaa", lineHeight: 1.45, marginTop: 10 }}>
                Reaffirmed. Invalidated. Ignored. All of it, logged with the evidence that prompted it.
              </div>
            </div>
            <div style={{ display: "flex", gap: 6 }}>
              <span
                style={{
                  padding: "4px 8px",
                  borderRadius: 4,
                  background: `${mk.green}22`,
                  border: `1px solid ${mk.green}44`,
                  color: mk.green,
                  fontFamily: mk.mono,
                  fontSize: 9,
                  letterSpacing: "0.1em",
                  textTransform: "uppercase",
                }}
              >
                Holding
              </span>
              <span
                style={{
                  padding: "4px 8px",
                  borderRadius: 4,
                  background: `${mk.accent}22`,
                  border: `1px solid ${mk.accent}44`,
                  color: mk.accent,
                  fontFamily: mk.mono,
                  fontSize: 9,
                  letterSpacing: "0.1em",
                  textTransform: "uppercase",
                }}
              >
                Thesis broke
              </span>
            </div>
          </div>

          {/* Quiet by default */}
          <div
            style={{
              gridColumn: "span 2",
              background: mk.cardSoft,
              borderRadius: 16,
              padding: 24,
              border: `1px solid ${mk.pencilLight}`,
              display: "flex",
              flexDirection: "column",
              justifyContent: "space-between",
              gap: 14,
              minHeight: 220,
            }}
            className="max-md:col-span-1"
          >
            <div
              style={{
                fontFamily: mk.mono,
                fontSize: 11,
                textTransform: "uppercase",
                letterSpacing: "0.1em",
                color: mk.pencil,
              }}
            >
              silent until it matters
            </div>
            <div>
              <div
                style={{
                  fontFamily: mk.sans,
                  fontSize: "clamp(26px,2.8vw,36px)",
                  fontWeight: 600,
                  letterSpacing: "-0.025em",
                  lineHeight: 1.0,
                  color: mk.ink,
                }}
              >
                0 daily
                <br />
                pushes.
              </div>
              <div style={{ fontSize: 13, color: mk.pencil, lineHeight: 1.45, marginTop: 10 }}>
                No streaks. No &ldquo;you&apos;re up 0.4%.&rdquo; Only signal-level moves tied to your specific reason.
              </div>
            </div>
          </div>

          {/* Sources */}
          <div
            style={{
              gridColumn: "span 2",
              background: mk.card,
              borderRadius: 16,
              padding: 24,
              border: `1px solid ${mk.pencilLight}`,
              display: "flex",
              flexDirection: "column",
              gap: 10,
            }}
            className="max-md:col-span-1"
          >
            <div
              style={{
                fontFamily: mk.mono,
                fontSize: 11,
                textTransform: "uppercase",
                letterSpacing: "0.1em",
                color: mk.pencil,
              }}
            >
              evidence, not vibes
            </div>
            <div style={{ fontFamily: mk.sans, fontSize: 22, fontWeight: 600, lineHeight: 1.1 }}>
              Every signal has sources.
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 5, marginTop: 4 }}>
              {["News", "SEC filings", "10-Q", "8-K", "Earnings calls", "Insider filings"].map(
                (s) => (
                  <span
                    key={s}
                    style={{
                      padding: "4px 10px",
                      borderRadius: 999,
                      border: `1px solid ${mk.pencilLight}`,
                      background: mk.cardSoft,
                      fontSize: 11,
                      color: mk.ink,
                    }}
                  >
                    {s}
                  </span>
                ),
              )}
            </div>
          </div>

          {/* Counter thesis */}
          <div
            style={{
              gridColumn: "span 2",
              background: mk.accentSoft,
              borderRadius: 16,
              padding: 24,
              border: `1px solid ${mk.accent}55`,
              display: "flex",
              flexDirection: "column",
              gap: 10,
            }}
            className="max-md:col-span-1"
          >
            <div
              style={{
                fontFamily: mk.mono,
                fontSize: 11,
                textTransform: "uppercase",
                letterSpacing: "0.1em",
                color: mk.accent,
              }}
            >
              steel-man yourself
            </div>
            <div style={{ fontFamily: mk.sans, fontSize: 22, fontWeight: 600, lineHeight: 1.1 }}>
              The bear case beside your bull case.
            </div>
            <div style={{ fontSize: 13, color: mk.ink, lineHeight: 1.5 }}>
              Write your exit condition and the counter-argument. Stronger conviction or a faster exit. Both fine.
            </div>
          </div>

          {/* Living doc */}
          <div
            style={{
              gridColumn: "span 2",
              background: mk.cardSoft,
              borderRadius: 16,
              padding: 24,
              border: `1px solid ${mk.pencilLight}`,
              display: "flex",
              flexDirection: "column",
              gap: 10,
            }}
            className="max-md:col-span-1"
          >
            <div
              style={{
                fontFamily: mk.mono,
                fontSize: 11,
                textTransform: "uppercase",
                letterSpacing: "0.1em",
                color: mk.pencil,
              }}
            >
              thesis history
            </div>
            <div
              style={{
                fontFamily: mk.sans,
                fontSize: "clamp(18px,2.2vw,26px)",
                fontWeight: 600,
                lineHeight: 1.15,
                letterSpacing: "-0.02em",
              }}
            >
              Versioned, diffable, yours.
            </div>
            <div style={{ display: "flex", gap: 8, marginTop: 6, flexWrap: "wrap" }}>
              {[
                ["v1", "Apr"],
                ["v2", "Jan"],
                ["v3", "Mar"],
                ["v4 · current", "Jun"],
              ].map(([n, d], i) => (
                <div
                  key={n}
                  style={{
                    padding: "6px 12px",
                    borderRadius: 999,
                    background: i === 3 ? mk.ink : mk.card,
                    color: i === 3 ? mk.paper : mk.ink,
                    border: `1px solid ${i === 3 ? mk.ink : mk.pencilLight}`,
                    fontSize: 12,
                  }}
                >
                  {n} · {d}
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ── WHY NOT JUST CLAUDE ──────────────────────────────── */}
      <section
        style={{
          padding: `clamp(50px,8vw,100px) ${pad}`,
          background: mk.ink,
          borderTop: `1px solid rgba(255,255,255,0.06)`,
        }}
      >
        <div
          style={{
            fontFamily: mk.mono,
            fontSize: 11,
            letterSpacing: "0.14em",
            textTransform: "uppercase",
            color: mk.accent,
            marginBottom: 14,
          }}
        >
          What we actually built
        </div>
        <h2
          style={{
            fontFamily: mk.sans,
            fontWeight: 700,
            fontSize: "clamp(34px,5vw,60px)",
            lineHeight: 1.0,
            letterSpacing: "-0.03em",
            margin: 0,
            maxWidth: 900,
            color: mk.paper,
          }}
        >
          The AI part took a weekend.
          <br />
          <span style={{ color: "#666" }}>The accountability infrastructure took eight months.</span>
        </h2>
        <p
          style={{
            fontFamily: mk.sans,
            fontSize: "clamp(15px,1.7vw,18px)",
            lineHeight: 1.55,
            color: "#aaa",
            marginTop: "clamp(16px,2vw,24px)",
            maxWidth: 660,
          }}
        >
          Anyone can prompt an LLM to watch a ticker. What&apos;s hard is building the
          infrastructure that links your original reasoning to the moment evidence fires,
          captures your decision in context, and surfaces your track record without you
          having to maintain it. That&apos;s what penKeep is.
        </p>

        <div
          style={{
            marginTop: "clamp(36px,5vw,52px)",
            display: "grid",
            gridTemplateColumns: "repeat(3, 1fr)",
            gap: 14,
          }}
          className="max-md:grid-cols-1"
        >
          {BUILT_FEATURES.map((f) => (
            <div
              key={f.label}
              style={{
                background: "#1a1916",
                border: "1px solid rgba(255,255,255,0.08)",
                borderRadius: 14,
                padding: 22,
                display: "flex",
                flexDirection: "column",
                gap: 10,
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                }}
              >
                <span
                  style={{
                    width: 6,
                    height: 6,
                    borderRadius: 999,
                    background: mk.green,
                    flexShrink: 0,
                  }}
                />
                <span
                  style={{
                    fontFamily: mk.mono,
                    fontSize: 11,
                    letterSpacing: "0.1em",
                    textTransform: "uppercase",
                    color: mk.green,
                  }}
                >
                  {f.label}
                </span>
              </div>
              <p
                style={{
                  fontFamily: mk.sans,
                  fontSize: 13,
                  color: "#999",
                  lineHeight: 1.55,
                  margin: 0,
                }}
              >
                {f.desc}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* ── HOW IT WORKS ─────────────────────────────────────── */}
      <section
        id="how-it-works"
        style={{ padding: `clamp(50px,8vw,100px) ${pad}` }}
      >
        <div
          style={{
            fontFamily: mk.mono,
            fontSize: 11,
            letterSpacing: "0.14em",
            textTransform: "uppercase",
            color: mk.pencil,
            marginBottom: 14,
          }}
        >
          How it works
        </div>
        <h2
          style={{
            fontFamily: mk.sans,
            fontSize: "clamp(34px,5vw,56px)",
            fontWeight: 700,
            lineHeight: 1,
            letterSpacing: "-0.025em",
            margin: 0,
          }}
        >
          The shortest loop in investing.
        </h2>
        <div
          style={{
            marginTop: "clamp(28px,4vw,48px)",
            display: "grid",
            gridTemplateColumns: "repeat(3, 1fr)",
            gap: 14,
          }}
          className="max-md:grid-cols-1"
        >
          {STEPS_COPY.map((s) => (
            <div
              key={s.n}
              style={{
                background: mk.card,
                border: `1px solid ${mk.pencilLight}`,
                borderRadius: 16,
                padding: 24,
                display: "flex",
                flexDirection: "column",
                gap: 10,
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <div
                  style={{
                    width: 36,
                    height: 36,
                    borderRadius: 999,
                    background: mk.ink,
                    color: mk.paper,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontFamily: mk.mono,
                    fontSize: 14,
                    fontWeight: 600,
                    flex: "0 0 36px",
                  }}
                >
                  {s.n}
                </div>
                <div
                  style={{
                    fontFamily: mk.sans,
                    fontSize: 20,
                    fontWeight: 600,
                    lineHeight: 1.15,
                  }}
                >
                  {s.t}
                </div>
              </div>
              <div style={{ fontSize: 14, color: mk.pencil, lineHeight: 1.55 }}>{s.d}</div>
            </div>
          ))}
        </div>
      </section>

      {/* ── QUOTES ───────────────────────────────────────────── */}
      <section
        style={{
          padding: `clamp(50px,8vw,100px) ${pad}`,
          background: mk.cardSoft,
          borderTop: `1px solid ${mk.pencilLight}`,
          borderBottom: `1px solid ${mk.pencilLight}`,
        }}
      >
        <div
          style={{
            fontFamily: mk.mono,
            fontSize: 11,
            letterSpacing: "0.14em",
            textTransform: "uppercase",
            color: mk.pencil,
            marginBottom: "clamp(28px,4vw,44px)",
          }}
        >
          From the beta
        </div>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(3, 1fr)",
            gap: "clamp(28px,4vw,40px)",
          }}
          className="max-md:grid-cols-1"
        >
          {QUOTES.map((q, i) => (
            <div key={i} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              <div
                style={{
                  fontFamily: mk.sans,
                  fontSize: "clamp(17px,1.9vw,21px)",
                  fontWeight: 500,
                  lineHeight: 1.4,
                  letterSpacing: "-0.01em",
                  color: mk.ink,
                }}
              >
                &ldquo;{q.q}&rdquo;
              </div>
              <div
                style={{
                  fontFamily: mk.mono,
                  fontSize: 10,
                  letterSpacing: "0.12em",
                  textTransform: "uppercase",
                  color: mk.pencil,
                }}
              >
                — {q.a}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ── SIGNUP ───────────────────────────────────────────── */}
      <section
        id="signup"
        style={{
          padding: `clamp(60px,10vw,120px) ${pad}`,
          background: mk.ink,
          textAlign: "center",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 20,
        }}
      >
        <div
          style={{
            fontFamily: mk.mono,
            fontSize: 11,
            letterSpacing: "0.14em",
            textTransform: "uppercase",
            color: mk.accent,
          }}
        >
          Private beta · limited seats
        </div>
        <h2
          style={{
            fontFamily: mk.sans,
            fontSize: "clamp(42px,7vw,88px)",
            fontWeight: 700,
            margin: 0,
            lineHeight: 0.98,
            letterSpacing: "-0.038em",
            maxWidth: 900,
            color: mk.paper,
          }}
        >
          Write your first
          <br />
          <span style={{ color: mk.accent }}>real reason.</span>
        </h2>
        <p
          style={{
            fontFamily: mk.sans,
            fontSize: "clamp(15px,1.7vw,18px)",
            color: "#aaa",
            margin: 0,
            maxWidth: 480,
            lineHeight: 1.5,
          }}
        >
          Free to start. Join the waitlist and we&apos;ll reach out before launch. No pitch — just
          early access and a chance to shape what we build next.
        </p>
        <WaitlistForm dark />
      </section>

      <MarketingFooter />
    </div>
  );
}
