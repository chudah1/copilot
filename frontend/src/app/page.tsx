import { MarketingNav } from "./_mkt/nav";
import { MarketingFooter } from "./_mkt/footer";
import { WaitlistForm } from "./_mkt/waitlist-form";
import { ThesisDemo } from "./_mkt/thesis-demo";
import { WatchThesisChange } from "./_mkt/timeline";
import { mk } from "./_mkt/tokens";

const STEPS_COPY = [
  { n: "01", t: "Write your reason", d: "Not a target price or a thesis template. Just: why do you own this? One or two sentences is plenty." },
  { n: "02", t: "We watch",          d: "Earnings, filings, analyst commentary, management tone, insider moves. All mapped to the reason you wrote." },
  { n: "03", t: "You hear from us",  d: "When something you specifically care about moves, we send one note. That's it. Silence the rest of the time is on purpose." },
];

const QUOTES = [
  { q: "I finally stopped holding TSLA past the reason it made sense. I had it written down and the note arrived at exactly the right moment.", a: "Beta user, London" },
  { q: "Every other app tells me what the market is doing. penKeep is the first one that checks whether the market is doing what I thought it would.", a: "Beta user, New York" },
  { q: "I wrote my first real thesis in about ten minutes. The second one was better. The third one might actually be right.", a: "Beta user, Toronto" },
];

export default function LandingPage() {
  const pad = "clamp(22px, 4.5vw, 56px)";

  return (
    <div style={{ background: mk.paper, color: mk.ink, fontFamily: mk.sans, backgroundImage: "none" }}>
      <style>{`
        @keyframes mkPulse  { 0%,100%{opacity:.4} 50%{opacity:1} }
        @keyframes mkFadeIn { from{opacity:0;transform:translateY(4px) scale(.99)} to{opacity:1;transform:none} }
        @keyframes mkSlideIn{ from{opacity:0;transform:translateY(8px)} to{opacity:1;transform:none} }
        .mk-root { background-image: none !important; }
      `}</style>

      <MarketingNav />

      {/* ── HERO ─────────────────────────────────────────────── */}
      <section style={{ padding: `clamp(30px,6vw,64px) ${pad} clamp(40px,6vw,56px)` }}>
        <div
          style={{
            display: "inline-flex",
            gap: 8,
            alignItems: "center",
            padding: "5px 12px",
            background: mk.accentSoft,
            color: mk.accent,
            border: `1px solid ${mk.accent}`,
            borderRadius: 999,
            fontSize: 12,
            fontFamily: mk.mono,
            marginBottom: "clamp(18px,3vw,24px)",
          }}
        >
          <span style={{ width: 6, height: 6, borderRadius: 999, background: mk.accent, display: "inline-block" }} />
          Pre-launch · summer 2026
        </div>

        <h1
          style={{
            fontFamily: mk.sans,
            fontWeight: 600,
            fontSize: "clamp(44px,7.5vw,88px)",
            lineHeight: 1.0,
            letterSpacing: "-0.035em",
            margin: 0,
            maxWidth: 1050,
          }}
        >
          You&apos;re holding stocks.<br />
          Are you investing,<br />
          <span
            style={{
              background: `linear-gradient(135deg, ${mk.accent} 0%, ${mk.accentDeep} 100%)`,
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
              backgroundClip: "text",
            }}
          >
            or just hoping?
          </span>
        </h1>

        <p
          style={{
            fontFamily: mk.sans,
            fontSize: "clamp(17px,2vw,21px)",
            lineHeight: 1.5,
            marginTop: "clamp(18px,3vw,28px)",
            maxWidth: 680,
            color: mk.pencil,
          }}
        >
          penKeep is where you write the reason you bought each stock.
          We tell you when that reason might have changed.
        </p>

        <div style={{ marginTop: "clamp(24px,3vw,32px)", display: "flex", flexWrap: "wrap", gap: 10, alignItems: "center" }}>
          <a
            href="#signup"
            style={{
              padding: "clamp(12px,1.5vw,14px) clamp(20px,2vw,24px)",
              background: mk.ink,
              color: mk.paper,
              border: "none",
              borderRadius: 999,
              cursor: "pointer",
              fontFamily: mk.sans,
              fontWeight: 500,
              fontSize: "clamp(15px,1.5vw,16px)",
              textDecoration: "none",
            }}
          >
            Join the waitlist →
          </a>
          <a
            href="#demo"
            style={{
              padding: "clamp(12px,1.5vw,14px) clamp(20px,2vw,24px)",
              background: "transparent",
              color: mk.ink,
              border: `1.4px solid ${mk.ink}`,
              borderRadius: 999,
              cursor: "pointer",
              fontFamily: mk.sans,
              fontWeight: 500,
              fontSize: "clamp(15px,1.5vw,16px)",
              textDecoration: "none",
            }}
          >
            Try the demo ↓
          </a>
        </div>

        <div id="demo" style={{ marginTop: "clamp(32px,5vw,56px)" }}>
          <ThesisDemo />
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
          Watch a thesis change
        </div>
        <h2
          style={{
            fontFamily: mk.sans,
            fontWeight: 600,
            fontSize: "clamp(36px,5vw,60px)",
            lineHeight: 1,
            letterSpacing: "-0.03em",
            margin: 0,
            maxWidth: 950,
          }}
        >
          One real story. <span style={{ color: mk.accent }}>Eight months.</span><br />
          Press play.
        </h2>
        <p style={{ fontFamily: mk.sans, fontSize: "clamp(16px,1.8vw,19px)", lineHeight: 1.5, color: mk.pencil, marginTop: 14, maxWidth: 640 }}>
          Someone bought Tesla in March 2024. Here&apos;s how the reason they wrote moved through the year, and
          the moment penKeep would have flagged it.
        </p>
        <div style={{ marginTop: "clamp(28px,4vw,44px)" }}>
          <WatchThesisChange />
        </div>
        <p style={{ fontFamily: mk.sans, fontSize: 13, color: mk.pencil, marginTop: 16, fontStyle: "italic" }}>
          Re-created from public coverage of TSLA, Mar–Oct 2024. penKeep does not give buy/sell advice.
        </p>
      </section>

      {/* ── BENTO ────────────────────────────────────────────── */}
      <section style={{ padding: `clamp(50px,8vw,100px) ${pad}` }}>
        <div style={{ fontFamily: mk.mono, fontSize: 11, letterSpacing: "0.14em", textTransform: "uppercase", color: mk.pencil, marginBottom: 14 }}>
          What&apos;s inside
        </div>
        <h2
          style={{
            fontFamily: mk.sans,
            fontWeight: 600,
            fontSize: "clamp(36px,5vw,56px)",
            lineHeight: 1,
            letterSpacing: "-0.025em",
            margin: 0,
            maxWidth: 800,
          }}
        >
          Built around <span style={{ color: mk.accent }}>your reason</span>, not their feed.
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
            <div style={{ fontFamily: mk.mono, fontSize: 11, textTransform: "uppercase", letterSpacing: "0.1em", color: mk.accent }}>
              ! reason changed
            </div>
            <div style={{ fontFamily: mk.sans, fontSize: "clamp(22px,2.5vw,32px)", fontWeight: 600, letterSpacing: "-0.02em", lineHeight: 1.1 }}>
              See exactly what changed since you bought.
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 16px 1fr", gap: 10, marginTop: 8, fontSize: 13 }}>
              {[
                ["EV demand growing",    "→", "EU deliveries -12% YoY"],
                ["Robotaxi optionality", "→", '"Underwhelming" — 7 of 9'],
                ["Margins protected",    "→", "Auto GM 14.3%"],
              ].map(([was, arr, now], i) => (
                <span key={i} style={{ display: "contents" }}>
                  <span style={{ color: mk.pencil, textDecoration: "line-through", textDecorationColor: mk.accent }}>{was}</span>
                  <span style={{ color: mk.accent, textAlign: "center" }}>{arr}</span>
                  <span style={{ color: mk.ink, fontWeight: 500 }}>{now}</span>
                </span>
              ))}
            </div>
            <div style={{ fontFamily: mk.sans, fontSize: 13, color: mk.pencil, marginTop: "auto" }}>
              The &ldquo;diff since you bought&rdquo; view: your reason, what we observed, side by side.
            </div>
          </div>

          {/* Quiet by default */}
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
            <div style={{ fontFamily: mk.mono, fontSize: 11, textTransform: "uppercase", letterSpacing: "0.1em", color: mk.accent }}>
              silent until it matters
            </div>
            <div style={{ fontFamily: mk.sans, fontSize: "clamp(28px,3vw,38px)", fontWeight: 600, letterSpacing: "-0.025em", lineHeight: 1.0 }}>
              0 daily<br />pushes.
            </div>
            <div style={{ fontSize: 13, color: "#aaa", lineHeight: 1.45 }}>
              No streaks. No &ldquo;you&apos;re up 0.4%.&rdquo; Only signal-level moves tied to your specific reason.
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
            <div style={{ fontFamily: mk.mono, fontSize: 11, textTransform: "uppercase", letterSpacing: "0.1em", color: mk.pencil }}>evidence, not vibes</div>
            <div style={{ fontFamily: mk.sans, fontSize: 22, fontWeight: 600, lineHeight: 1.1 }}>Every signal has sources.</div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 5, marginTop: 4 }}>
              {["Bloomberg", "Reuters", "FT", "SEC filings", "10-Q", "earnings calls", "analyst notes"].map((s) => (
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
              ))}
            </div>
          </div>

          {/* Counter thesis */}
          <div
            style={{
              gridColumn: "span 2",
              background: mk.accentSoft,
              borderRadius: 16,
              padding: 24,
              border: `1px solid ${mk.accent}`,
              display: "flex",
              flexDirection: "column",
              gap: 10,
            }}
            className="max-md:col-span-1"
          >
            <div style={{ fontFamily: mk.mono, fontSize: 11, textTransform: "uppercase", letterSpacing: "0.1em", color: mk.accent }}>steel-man yourself</div>
            <div style={{ fontFamily: mk.sans, fontSize: 22, fontWeight: 600, lineHeight: 1.1 }}>The bear case beside your bull case.</div>
            <div style={{ fontSize: 13, color: mk.ink, lineHeight: 1.5 }}>
              Optional, but the best users write one. Stronger conviction or a faster exit. Both fine.
            </div>
          </div>

          {/* Living doc */}
          <div
            style={{
              gridColumn: "span 4",
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
            <div style={{ fontFamily: mk.mono, fontSize: 11, textTransform: "uppercase", letterSpacing: "0.1em", color: mk.pencil }}>thesis history</div>
            <div style={{ fontFamily: mk.sans, fontSize: "clamp(22px,2.5vw,30px)", fontWeight: 600, lineHeight: 1.1, letterSpacing: "-0.02em" }}>
              Your reason is a living document: versioned, diffable, yours.
            </div>
            <div style={{ display: "flex", gap: 8, marginTop: 6, flexWrap: "wrap" }}>
              {[["v1", "Apr"], ["v2", "Jan"], ["v3", "Mar"], ["v4 · current", "Jun"]].map(([n, d], i) => (
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

      {/* ── HOW IT WORKS ─────────────────────────────────────── */}
      <section id="how-it-works" style={{ padding: `clamp(50px,8vw,100px) ${pad}` }}>
        <div style={{ fontFamily: mk.mono, fontSize: 11, letterSpacing: "0.14em", textTransform: "uppercase", color: mk.pencil, marginBottom: 14 }}>
          How it works
        </div>
        <h2 style={{ fontFamily: mk.sans, fontSize: "clamp(36px,5vw,56px)", fontWeight: 600, lineHeight: 1, letterSpacing: "-0.025em", margin: 0 }}>
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
                padding: 22,
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
                <div style={{ fontFamily: mk.sans, fontSize: 20, fontWeight: 600, lineHeight: 1.15 }}>{s.t}</div>
              </div>
              <div style={{ fontSize: 14, color: mk.pencil, lineHeight: 1.5 }}>{s.d}</div>
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
          style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "clamp(28px,4vw,40px)" }}
          className="max-md:grid-cols-1"
        >
          {QUOTES.map((q, i) => (
            <div key={i} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              <div style={{ fontFamily: mk.sans, fontSize: "clamp(18px,2vw,22px)", fontWeight: 500, lineHeight: 1.35, letterSpacing: "-0.01em" }}>
                &ldquo;{q.q}&rdquo;
              </div>
              <div style={{ fontFamily: mk.mono, fontSize: 11, letterSpacing: "0.1em", textTransform: "uppercase", color: mk.pencil }}>
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
          textAlign: "center",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 18,
        }}
      >
        <h2
          style={{
            fontFamily: mk.sans,
            fontSize: "clamp(44px,7vw,84px)",
            fontWeight: 600,
            margin: 0,
            lineHeight: 0.98,
            letterSpacing: "-0.035em",
            maxWidth: 900,
          }}
        >
          Write your first<br /><span style={{ color: mk.accent }}>thesis.</span>
        </h2>
        <p style={{ fontFamily: mk.sans, fontSize: "clamp(16px,1.8vw,18px)", color: mk.pencil, margin: 0, maxWidth: 480 }}>
          Free at launch. We&apos;ll email you when it&apos;s ready.
        </p>
        <WaitlistForm />
      </section>

      <MarketingFooter />
    </div>
  );
}
