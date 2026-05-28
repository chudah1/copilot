import { MarketingNav } from "./_mkt/nav";
import { MarketingFooter } from "./_mkt/footer";
import { WaitlistForm } from "./_mkt/waitlist-form";
import { ThesisDemo } from "./_mkt/thesis-demo";
import { WatchThesisChange } from "./_mkt/timeline";
import { ConvictionDemo } from "./_mkt/conviction-demo";
import { mk } from "./_mkt/tokens";

export default function LandingPage() {
  const pad = "clamp(24px, 5vw, 72px)";

  return (
    <div style={{ background: mk.paper, color: mk.ink, fontFamily: mk.sans, backgroundImage: "none" }}>
      <style>{`
        @keyframes mkPulse    { 0%,100%{opacity:.35} 50%{opacity:1} }
        @keyframes mkFadeIn   { from{opacity:0;transform:translateY(6px)} to{opacity:1;transform:none} }
        @keyframes mkSlideIn  { from{opacity:0;transform:translateY(10px)} to{opacity:1;transform:none} }
        @keyframes mkFloat    { 0%,100%{transform:perspective(900px) rotateX(4deg) rotateY(-7deg) translateY(0px)} 50%{transform:perspective(900px) rotateX(4deg) rotateY(-7deg) translateY(-8px)} }
        @keyframes mkSweep    { from{transform:scaleX(0)} to{transform:scaleX(1)} }
        @keyframes mkGlowPulse{ 0%,100%{opacity:0.5} 50%{opacity:0.85} }
        .mk-card-hover { transition: transform 200ms ease, box-shadow 200ms ease; }
        .mk-card-hover:hover { transform: translateY(-2px); box-shadow: 0 20px 60px -20px rgba(0,0,0,0.18); }
      `}</style>

      <MarketingNav />

      {/* ─── HERO ──────────────────────────────────────────────────── */}
      <section
        style={{
          padding: `clamp(48px,7vw,88px) ${pad} clamp(40px,6vw,72px)`,
          display: "grid",
          gridTemplateColumns: "1.1fr 1fr",
          gap: "clamp(40px,6vw,80px)",
          alignItems: "center",
          minHeight: "88vh",
          maxWidth: 1400,
          margin: "0 auto",
        }}
        className="max-lg:grid-cols-1"
      >
        {/* Left */}
        <div>
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 8,
              fontFamily: mk.mono,
              fontSize: 11,
              letterSpacing: "0.18em",
              textTransform: "uppercase",
              color: mk.pencil,
              marginBottom: "clamp(24px,3.5vw,36px)",
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
              fontFamily: mk.display,
              fontStyle: "italic",
              fontWeight: 400,
              fontSize: "clamp(64px,8.5vw,116px)",
              lineHeight: 0.95,
              letterSpacing: "-0.015em",
              margin: "0 0 clamp(20px,3vw,32px)",
              color: mk.ink,
            }}
          >
            The reason
            <br />
            you hold it—
            <br />
            <span style={{ color: mk.accent }}>tracked.</span>
          </h1>

          <p
            style={{
              fontFamily: mk.sans,
              fontSize: "clamp(16px,1.7vw,19px)",
              lineHeight: 1.6,
              color: mk.pencil,
              maxWidth: 500,
              margin: "0 0 clamp(28px,4vw,40px)",
            }}
          >
            Write the reason you bought each position. penKeep watches
            earnings, filings, and news against it — and tells you exactly
            when your specific reason to hold starts to break.
          </p>

          <WaitlistForm />

          <div
            style={{
              display: "flex",
              gap: "clamp(24px,4vw,40px)",
              marginTop: "clamp(28px,4vw,40px)",
            }}
          >
            {[
              { n: "47", l: "theses written" },
              { n: "312", l: "signals fired" },
              { n: "18", l: "decisions logged" },
            ].map(({ n, l }) => (
              <div key={l}>
                <div
                  style={{
                    fontFamily: mk.mono,
                    fontSize: "clamp(20px,2.4vw,30px)",
                    fontWeight: 600,
                    letterSpacing: "-0.02em",
                    color: mk.ink,
                    lineHeight: 1,
                  }}
                >
                  {n}
                </div>
                <div
                  style={{
                    fontFamily: mk.mono,
                    fontSize: 10,
                    letterSpacing: "0.14em",
                    textTransform: "uppercase",
                    color: mk.pencil,
                    marginTop: 4,
                  }}
                >
                  {l}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right — floating decision-moment card */}
        <div
          style={{
            position: "relative",
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
          }}
          className="max-lg:hidden"
        >
          {/* Glow behind */}
          <div
            style={{
              position: "absolute",
              inset: "-20%",
              background: `radial-gradient(ellipse 70% 60% at 55% 45%, ${mk.accent}28 0%, transparent 70%)`,
              animation: "mkGlowPulse 4s ease-in-out infinite",
              pointerEvents: "none",
            }}
          />
          {/* The card */}
          <div
            style={{
              position: "relative",
              width: "100%",
              maxWidth: 420,
              background: mk.ink,
              borderRadius: 20,
              overflow: "hidden",
              boxShadow: `0 40px 120px -30px rgba(0,0,0,0.55), 0 0 0 1px rgba(255,255,255,0.06)`,
              animation: "mkFloat 6s ease-in-out infinite",
            }}
          >
            {/* Top stripe */}
            <div
              style={{
                height: 3,
                background: `linear-gradient(90deg, ${mk.accent} 0%, ${mk.accentDeep} 100%)`,
              }}
            />

            {/* Card header */}
            <div
              style={{
                padding: "18px 22px 14px",
                borderBottom: "1px solid rgba(255,255,255,0.06)",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <span
                  style={{
                    width: 8,
                    height: 8,
                    borderRadius: 999,
                    background: mk.accent,
                    animation: "mkPulse 1.8s ease-in-out infinite",
                    flexShrink: 0,
                  }}
                />
                <span
                  style={{
                    fontFamily: mk.mono,
                    fontSize: 12,
                    fontWeight: 600,
                    color: "#fff",
                    letterSpacing: "0.14em",
                  }}
                >
                  TSLA
                </span>
                <span style={{ fontFamily: mk.sans, fontSize: 13, color: "#888" }}>
                  Tesla
                </span>
              </div>
              <span
                style={{
                  fontFamily: mk.mono,
                  fontSize: 9,
                  letterSpacing: "0.18em",
                  textTransform: "uppercase",
                  padding: "3px 9px",
                  background: `${mk.accent}25`,
                  border: `1px solid ${mk.accent}55`,
                  color: mk.accent,
                  borderRadius: 4,
                }}
              >
                HIGH SIGNAL
              </span>
            </div>

            {/* Event */}
            <div style={{ padding: "16px 22px", borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
              <div
                style={{
                  fontFamily: mk.mono,
                  fontSize: 9,
                  letterSpacing: "0.16em",
                  textTransform: "uppercase",
                  color: "#555",
                  marginBottom: 8,
                }}
              >
                Oct 23, 2024 · Evidence
              </div>
              <p
                style={{
                  fontFamily: mk.sans,
                  fontSize: 15,
                  color: "#e8e4dc",
                  lineHeight: 1.5,
                  margin: 0,
                }}
              >
                Q3 deliveries -8.4% YoY. Robotaxi event called{" "}
                <em style={{ color: mk.accent }}>&ldquo;underwhelming&rdquo;</em> by 7 of 9
                analysts covering the stock.
              </p>
            </div>

            {/* Exit condition — the key UI */}
            <div
              style={{
                margin: "16px 22px",
                padding: "14px 16px",
                background: `${mk.accent}12`,
                border: `1px solid ${mk.accent}35`,
                borderRadius: 10,
              }}
            >
              <div
                style={{
                  fontFamily: mk.mono,
                  fontSize: 9,
                  letterSpacing: "0.16em",
                  textTransform: "uppercase",
                  color: mk.accent,
                  marginBottom: 8,
                }}
              >
                Your exit condition · written Mar 12
              </div>
              <p
                style={{
                  fontFamily: mk.display,
                  fontStyle: "italic",
                  fontSize: 17,
                  color: "#e8c8b0",
                  lineHeight: 1.45,
                  margin: 0,
                }}
              >
                &ldquo;If EV demand reverses or robotaxi misses a credible
                timeline, I&apos;m out.&rdquo;
              </p>
            </div>

            {/* Decision */}
            <div
              style={{
                padding: "0 22px 20px",
                display: "flex",
                gap: 8,
              }}
            >
              <button
                style={{
                  flex: 1,
                  padding: "10px 0",
                  background: "transparent",
                  color: "#666",
                  border: "1px solid rgba(255,255,255,0.1)",
                  borderRadius: 8,
                  fontFamily: mk.sans,
                  fontSize: 13,
                  cursor: "pointer",
                }}
              >
                Still believe →
              </button>
              <button
                style={{
                  flex: 1,
                  padding: "10px 0",
                  background: mk.accent,
                  color: "#fff",
                  border: "none",
                  borderRadius: 8,
                  fontFamily: mk.sans,
                  fontSize: 13,
                  fontWeight: 600,
                  cursor: "pointer",
                }}
              >
                Story changed →
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* ─── SEPARATOR ─────────────────────────────────────────────── */}
      <div
        style={{
          padding: `0 ${pad}`,
          overflow: "hidden",
        }}
      >
        <div style={{ height: 1, background: mk.pencilLight }} />
      </div>

      {/* ─── DEMO ──────────────────────────────────────────────────── */}
      <section style={{ padding: `clamp(64px,9vw,110px) ${pad}` }}>
        <div style={{ maxWidth: 1400, margin: "0 auto" }}>
          <p
            style={{
              fontFamily: mk.mono,
              fontSize: 11,
              letterSpacing: "0.18em",
              textTransform: "uppercase",
              color: mk.pencil,
              marginBottom: "clamp(14px,2vw,20px)",
            }}
          >
            Try it
          </p>
          <h2
            style={{
              fontFamily: mk.display,
              fontStyle: "italic",
              fontWeight: 400,
              fontSize: "clamp(48px,6vw,88px)",
              lineHeight: 0.97,
              letterSpacing: "-0.01em",
              margin: "0 0 clamp(32px,5vw,52px)",
              maxWidth: 800,
            }}
          >
            Write any reason.
            <br />
            <span style={{ color: mk.accent }}>Watch what we extract.</span>
          </h2>
          <ThesisDemo />
        </div>
      </section>

      {/* ─── THE CONVICTION LOOP ───────────────────────────────────── */}
      <section
        style={{
          background: mk.ink,
          padding: `clamp(64px,9vw,110px) ${pad}`,
        }}
      >
        <div
          style={{
            maxWidth: 1400,
            margin: "0 auto",
            display: "grid",
            gridTemplateColumns: "1fr 1.1fr",
            gap: "clamp(48px,7vw,96px)",
            alignItems: "center",
          }}
          className="max-lg:grid-cols-1"
        >
          <div>
            <p
              style={{
                fontFamily: mk.mono,
                fontSize: 11,
                letterSpacing: "0.18em",
                textTransform: "uppercase",
                color: mk.accent,
                marginBottom: "clamp(14px,2vw,20px)",
              }}
            >
              Closed-loop accountability
            </p>
            <h2
              style={{
                fontFamily: mk.display,
                fontStyle: "italic",
                fontWeight: 400,
                fontSize: "clamp(44px,5.5vw,80px)",
                lineHeight: 0.97,
                letterSpacing: "-0.01em",
                color: mk.paper,
                margin: "0 0 clamp(20px,3vw,28px)",
              }}
            >
              Your words.
              <br />
              Surfaced when
              <br />
              <span style={{ color: mk.accent }}>evidence fires.</span>
            </h2>
            <p
              style={{
                fontFamily: mk.sans,
                fontSize: "clamp(15px,1.6vw,18px)",
                lineHeight: 1.65,
                color: "#b0a898",
                maxWidth: 460,
              }}
            >
              You wrote what would change your mind when you bought. When
              evidence fires, we show those exact words back to you — not a
              generic alert, not a price move. Your own exit condition,
              beside the data that&apos;s testing it.
            </p>
            <p
              style={{
                fontFamily: mk.sans,
                fontSize: "clamp(15px,1.6vw,18px)",
                lineHeight: 1.65,
                color: "#b0a898",
                maxWidth: 460,
                marginTop: 16,
              }}
            >
              You decide. We log it. Six months later, you&apos;ll know
              whether you called it right.
            </p>
          </div>
          <div>
            <ConvictionDemo />
          </div>
        </div>
      </section>

      {/* ─── TIMELINE ──────────────────────────────────────────────── */}
      <section
        style={{
          padding: `clamp(64px,9vw,110px) ${pad}`,
          borderTop: `1px solid ${mk.pencilLight}`,
        }}
      >
        <div style={{ maxWidth: 1400, margin: "0 auto" }}>
          <p
            style={{
              fontFamily: mk.mono,
              fontSize: 11,
              letterSpacing: "0.18em",
              textTransform: "uppercase",
              color: mk.pencil,
              marginBottom: "clamp(14px,2vw,20px)",
            }}
          >
            A real story
          </p>
          <h2
            style={{
              fontFamily: mk.display,
              fontStyle: "italic",
              fontWeight: 400,
              fontSize: "clamp(48px,6vw,88px)",
              lineHeight: 0.97,
              letterSpacing: "-0.01em",
              margin: "0 0 clamp(10px,2vw,16px)",
            }}
          >
            One thesis.
            <br />
            <span style={{ color: mk.accent }}>Eight months.</span>
          </h2>
          <p
            style={{
              fontFamily: mk.sans,
              fontSize: "clamp(15px,1.6vw,18px)",
              color: mk.pencil,
              lineHeight: 1.6,
              maxWidth: 580,
              margin: "0 0 clamp(32px,5vw,48px)",
            }}
          >
            Someone bought TSLA in March 2024 with a specific reason. Here
            is exactly how the evidence moved — and the moment penKeep would
            have surfaced their own exit condition back to them.
          </p>
          <WatchThesisChange />
          <p
            style={{
              fontFamily: mk.mono,
              fontSize: 11,
              color: mk.pencil,
              marginTop: 18,
              opacity: 0.6,
            }}
          >
            Re-created from public coverage of TSLA, Mar–Oct 2024. Not financial advice.
          </p>
        </div>
      </section>

      {/* ─── BENTO ─────────────────────────────────────────────────── */}
      <section
        style={{
          padding: `clamp(64px,9vw,110px) ${pad}`,
          background: mk.cardSoft,
          borderTop: `1px solid ${mk.pencilLight}`,
          borderBottom: `1px solid ${mk.pencilLight}`,
        }}
      >
        <div style={{ maxWidth: 1400, margin: "0 auto" }}>
          <p
            style={{
              fontFamily: mk.mono,
              fontSize: 11,
              letterSpacing: "0.18em",
              textTransform: "uppercase",
              color: mk.pencil,
              marginBottom: "clamp(14px,2vw,20px)",
            }}
          >
            What&apos;s inside
          </p>
          <h2
            style={{
              fontFamily: mk.display,
              fontStyle: "italic",
              fontWeight: 400,
              fontSize: "clamp(48px,6vw,88px)",
              lineHeight: 0.97,
              letterSpacing: "-0.01em",
              margin: "0 0 clamp(36px,5vw,56px)",
            }}
          >
            Built around your reason.
            <br />
            <span style={{ color: mk.accent }}>Not their feed.</span>
          </h2>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(12, 1fr)",
              gap: 16,
            }}
            className="max-md:grid-cols-1"
          >
            {/* Big hero card */}
            <div
              className="max-md:col-span-1 mk-card-hover"
              style={{
                gridColumn: "span 7",
                gridRow: "span 2",
                background: mk.ink,
                borderRadius: 20,
                padding: "clamp(24px,3vw,36px)",
                display: "flex",
                flexDirection: "column",
                gap: 20,
                overflow: "hidden",
                position: "relative",
              }}
            >
              <div
                style={{
                  position: "absolute",
                  top: 0,
                  left: 0,
                  right: 0,
                  height: 3,
                  background: `linear-gradient(90deg, ${mk.accent} 0%, transparent 100%)`,
                }}
              />
              <div
                style={{
                  fontFamily: mk.mono,
                  fontSize: 10,
                  textTransform: "uppercase",
                  letterSpacing: "0.16em",
                  color: mk.accent,
                }}
              >
                ! Reason changed
              </div>
              <div
                style={{
                  fontFamily: mk.display,
                  fontStyle: "italic",
                  fontSize: "clamp(28px,3vw,42px)",
                  fontWeight: 400,
                  lineHeight: 1.05,
                  color: mk.paper,
                  maxWidth: 520,
                }}
              >
                See exactly what changed since you bought.
              </div>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 20px 1fr",
                  gap: "10px 8px",
                  fontSize: 13,
                }}
              >
                {[
                  ["EV demand growing", "→", "EU deliveries -12% YoY"],
                  ["Robotaxi optionality", "→", '"Underwhelming" — 7 of 9'],
                  ["Margins protected", "→", "Auto GM dropped to 14.3%"],
                ].map(([was, arr, now], i) => (
                  <span key={i} style={{ display: "contents" }}>
                    <span
                      style={{
                        color: "#666",
                        textDecoration: "line-through",
                        textDecorationColor: mk.accent,
                        lineHeight: 1.45,
                      }}
                    >
                      {was}
                    </span>
                    <span style={{ color: mk.accent, textAlign: "center" }}>{arr}</span>
                    <span style={{ color: mk.paper, fontWeight: 500, lineHeight: 1.45 }}>
                      {now}
                    </span>
                  </span>
                ))}
              </div>
              <div
                style={{
                  marginTop: "auto",
                  fontFamily: mk.sans,
                  fontSize: 13,
                  color: "#555",
                  lineHeight: 1.5,
                }}
              >
                The &ldquo;diff since you bought&rdquo; — your reason, mapped to what the data now shows.
              </div>
            </div>

            {/* Conviction log */}
            <div
              className="max-md:col-span-1 mk-card-hover"
              style={{
                gridColumn: "span 5",
                background: mk.accentSoft,
                borderRadius: 20,
                padding: "clamp(22px,2.5vw,32px)",
                border: `1px solid ${mk.accent}40`,
                display: "flex",
                flexDirection: "column",
                gap: 14,
              }}
            >
              <div
                style={{
                  fontFamily: mk.mono,
                  fontSize: 10,
                  textTransform: "uppercase",
                  letterSpacing: "0.16em",
                  color: mk.accent,
                }}
              >
                Conviction log
              </div>
              <div
                style={{
                  fontFamily: mk.display,
                  fontStyle: "italic",
                  fontWeight: 400,
                  fontSize: "clamp(26px,2.8vw,38px)",
                  lineHeight: 1.05,
                  color: mk.ink,
                }}
              >
                Every decision, forever.
              </div>
              <div style={{ fontSize: 13, color: mk.inkSoft, lineHeight: 1.55 }}>
                Reaffirmed. Invalidated. Ignored. All logged with the evidence
                that triggered the decision.
              </div>
              <div style={{ display: "flex", gap: 6, marginTop: "auto", flexWrap: "wrap" }}>
                {["Holding", "Thesis broke", "Lowered conviction"].map((label) => (
                  <span
                    key={label}
                    style={{
                      padding: "4px 10px",
                      border: `1px solid ${mk.accent}55`,
                      borderRadius: 999,
                      fontFamily: mk.mono,
                      fontSize: 10,
                      letterSpacing: "0.1em",
                      textTransform: "uppercase",
                      color: mk.accentDeep,
                    }}
                  >
                    {label}
                  </span>
                ))}
              </div>
            </div>

            {/* Silent */}
            <div
              className="max-md:col-span-1 mk-card-hover"
              style={{
                gridColumn: "span 5",
                background: mk.card,
                borderRadius: 20,
                padding: "clamp(22px,2.5vw,32px)",
                border: `1px solid ${mk.pencilLight}`,
                display: "flex",
                flexDirection: "column",
                justifyContent: "space-between",
                gap: 14,
              }}
            >
              <div
                style={{
                  fontFamily: mk.mono,
                  fontSize: 10,
                  textTransform: "uppercase",
                  letterSpacing: "0.16em",
                  color: mk.pencil,
                }}
              >
                Silent until it matters
              </div>
              <div>
                <div
                  style={{
                    fontFamily: mk.display,
                    fontStyle: "italic",
                    fontWeight: 400,
                    fontSize: "clamp(42px,5vw,68px)",
                    lineHeight: 0.95,
                    letterSpacing: "-0.01em",
                    color: mk.ink,
                  }}
                >
                  0 daily pushes.
                </div>
                <div style={{ fontSize: 13, color: mk.pencil, lineHeight: 1.55, marginTop: 12 }}>
                  No streaks. No &ldquo;you&apos;re up 0.4%.&rdquo; One
                  note, when your specific reason moves.
                </div>
              </div>
            </div>

            {/* Sources */}
            <div
              className="max-md:col-span-1 mk-card-hover"
              style={{
                gridColumn: "span 4",
                background: mk.cardSoft,
                borderRadius: 20,
                padding: "clamp(22px,2.5vw,32px)",
                border: `1px solid ${mk.pencilLight}`,
                display: "flex",
                flexDirection: "column",
                gap: 12,
              }}
            >
              <div
                style={{
                  fontFamily: mk.mono,
                  fontSize: 10,
                  textTransform: "uppercase",
                  letterSpacing: "0.16em",
                  color: mk.pencil,
                }}
              >
                Evidence, not vibes
              </div>
              <div
                style={{
                  fontFamily: mk.display,
                  fontStyle: "italic",
                  fontWeight: 400,
                  fontSize: "clamp(22px,2.4vw,32px)",
                  lineHeight: 1.1,
                  color: mk.ink,
                }}
              >
                Every signal has sources.
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 2 }}>
                {["News", "SEC filings", "10-Q", "8-K", "Earnings calls", "Insider filings"].map(
                  (s) => (
                    <span
                      key={s}
                      style={{
                        padding: "4px 10px",
                        borderRadius: 999,
                        border: `1px solid ${mk.pencilLight}`,
                        background: mk.card,
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

            {/* Versioned */}
            <div
              className="max-md:col-span-1 mk-card-hover"
              style={{
                gridColumn: "span 3",
                background: mk.card,
                borderRadius: 20,
                padding: "clamp(22px,2.5vw,32px)",
                border: `1px solid ${mk.pencilLight}`,
                display: "flex",
                flexDirection: "column",
                gap: 12,
              }}
            >
              <div
                style={{
                  fontFamily: mk.mono,
                  fontSize: 10,
                  textTransform: "uppercase",
                  letterSpacing: "0.16em",
                  color: mk.pencil,
                }}
              >
                Thesis history
              </div>
              <div
                style={{
                  fontFamily: mk.display,
                  fontStyle: "italic",
                  fontWeight: 400,
                  fontSize: "clamp(20px,2.2vw,28px)",
                  lineHeight: 1.1,
                  color: mk.ink,
                }}
              >
                Versioned, diffable, yours.
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 6, marginTop: 4 }}>
                {[["v1", "Apr 24"], ["v2", "Sep 24"], ["v3 · now", "Jan 25"]].map(([n, d], i) => (
                  <div
                    key={n}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      padding: "6px 10px",
                      background: i === 2 ? mk.ink : mk.cardSoft,
                      borderRadius: 8,
                      border: `1px solid ${i === 2 ? mk.ink : mk.pencilLight}`,
                    }}
                  >
                    <span
                      style={{
                        fontFamily: mk.mono,
                        fontSize: 11,
                        fontWeight: 600,
                        color: i === 2 ? mk.paper : mk.ink,
                      }}
                    >
                      {n}
                    </span>
                    <span
                      style={{
                        fontFamily: mk.mono,
                        fontSize: 10,
                        color: i === 2 ? "#aaa" : mk.pencil,
                      }}
                    >
                      {d}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ─── QUOTES ────────────────────────────────────────────────── */}
      <section style={{ padding: `clamp(64px,9vw,110px) ${pad}` }}>
        <div style={{ maxWidth: 1400, margin: "0 auto" }}>
          <p
            style={{
              fontFamily: mk.mono,
              fontSize: 11,
              letterSpacing: "0.18em",
              textTransform: "uppercase",
              color: mk.pencil,
              marginBottom: "clamp(36px,5vw,56px)",
            }}
          >
            From the beta
          </p>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(3, 1fr)",
              gap: "clamp(32px,5vw,56px)",
            }}
            className="max-md:grid-cols-1"
          >
            {[
              {
                q: "I finally sold TSLA at the right time — not because the chart broke, but because my own exit condition triggered. It was in penKeep since March.",
                a: "Beta user · London",
              },
              {
                q: "Every other app tells me what the market is doing. penKeep is the first one that checks whether the market is doing what I specifically thought it would.",
                a: "Beta user · New York",
              },
              {
                q: "I wrote my first real thesis in ten minutes. Six months later I can prove I made a rational decision, not an emotional one. That is worth something.",
                a: "Beta user · Toronto",
              },
            ].map((q, i) => (
              <div
                key={i}
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: 18,
                  paddingTop: "clamp(20px,3vw,28px)",
                  borderTop: `1.5px solid ${mk.pencilLight}`,
                }}
              >
                <p
                  style={{
                    fontFamily: mk.display,
                    fontStyle: "italic",
                    fontWeight: 400,
                    fontSize: "clamp(20px,2.2vw,27px)",
                    lineHeight: 1.35,
                    letterSpacing: "-0.005em",
                    color: mk.ink,
                    margin: 0,
                  }}
                >
                  &ldquo;{q.q}&rdquo;
                </p>
                <div
                  style={{
                    fontFamily: mk.mono,
                    fontSize: 10,
                    letterSpacing: "0.14em",
                    textTransform: "uppercase",
                    color: mk.pencil,
                  }}
                >
                  — {q.a}
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ─── SIGNUP ────────────────────────────────────────────────── */}
      <section
        id="signup"
        style={{
          padding: `clamp(72px,10vw,130px) ${pad}`,
          background: mk.ink,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          textAlign: "center",
          gap: 0,
        }}
      >
        <p
          style={{
            fontFamily: mk.mono,
            fontSize: 11,
            letterSpacing: "0.18em",
            textTransform: "uppercase",
            color: mk.accent,
            marginBottom: "clamp(20px,3vw,28px)",
          }}
        >
          Limited seats · private beta
        </p>
        <h2
          style={{
            fontFamily: mk.display,
            fontStyle: "italic",
            fontWeight: 400,
            fontSize: "clamp(56px,8vw,116px)",
            lineHeight: 0.95,
            letterSpacing: "-0.015em",
            margin: "0 0 clamp(20px,3vw,28px)",
            color: mk.paper,
            maxWidth: 900,
          }}
        >
          Write your first
          <br />
          <span style={{ color: mk.accent }}>real reason.</span>
        </h2>
        <p
          style={{
            fontFamily: mk.sans,
            fontSize: "clamp(15px,1.6vw,18px)",
            color: "#888",
            margin: "0 0 clamp(28px,4vw,40px)",
            maxWidth: 460,
            lineHeight: 1.6,
          }}
        >
          Free to start. Join the waitlist and we&apos;ll reach out before
          launch — early access, and a say in what we build next.
        </p>
        <WaitlistForm dark />
      </section>

      <MarketingFooter />
    </div>
  );
}
