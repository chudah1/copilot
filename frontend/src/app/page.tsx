import { MarketingNav } from "./_mkt/nav";
import { MarketingFooter } from "./_mkt/footer";
import { WaitlistForm } from "./_mkt/waitlist-form";
import { ThesisDemo } from "./_mkt/thesis-demo";
import { WatchThesisChange } from "./_mkt/timeline";
import { ConvictionDemo } from "./_mkt/conviction-demo";
import { mk } from "./_mkt/tokens";

const hPad = "clamp(24px, 4vw, 48px)";
const vPad = "clamp(80px, 9vw, 110px)";

function Kicker({ children, color = mk.accent }: { children: React.ReactNode; color?: string }) {
  return (
    <div
      style={{
        fontFamily: mk.mono,
        fontSize: 10.5,
        letterSpacing: "0.16em",
        textTransform: "uppercase",
        color,
        marginBottom: 22,
      }}
    >
      {children}
    </div>
  );
}

function NVDACard() {
  return (
    <div
      style={{
        width: "100%",
        maxWidth: 470,
        background: mk.night,
        color: mk.cream,
        borderRadius: 16,
        padding: 34,
        boxShadow: "0 40px 80px -30px rgba(40,30,18,0.5)",
        border: `1px solid ${mk.nightLine}`,
        position: "relative",
      }}
    >
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 24,
          right: 24,
          height: 2,
          background: mk.accent,
          borderRadius: 2,
        }}
      />

      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 26,
        }}
      >
        <div style={{ display: "flex", alignItems: "baseline", gap: 10 }}>
          <span
            style={{
              fontFamily: mk.mono,
              fontSize: 14,
              letterSpacing: "0.12em",
              color: mk.cream,
            }}
          >
            NVDA
          </span>
          <span style={{ fontFamily: mk.sans, fontSize: 14, color: mk.creamDim }}>NVIDIA</span>
        </div>
        <span
          style={{
            fontFamily: mk.mono,
            fontSize: 9,
            letterSpacing: "0.16em",
            textTransform: "uppercase",
            padding: "3px 9px",
            background: `${mk.accent}22`,
            border: `1px solid ${mk.accent}55`,
            color: mk.accent,
            borderRadius: 4,
          }}
        >
          HIGH SIGNAL
        </span>
      </div>

      <div
        style={{
          fontFamily: mk.mono,
          fontSize: 9.5,
          letterSpacing: "0.16em",
          textTransform: "uppercase",
          color: mk.creamDim,
          marginBottom: 12,
        }}
      >
        AUG 28 · EVIDENCE
      </div>

      <div style={{ fontFamily: mk.display, fontSize: 21, lineHeight: 1.45, color: mk.cream }}>
        Blackwell shipments slipping into Q4. Gross margin came in at{" "}
        <span style={{ color: mk.accent }}>74.6%</span>, below the 76.4% everyone expected.
        Google and Amazon both stepping up their own chip programs.
      </div>

      <div style={{ height: 1, background: mk.nightLine, margin: "26px 0" }} />

      <div
        style={{
          fontFamily: mk.mono,
          fontSize: 9.5,
          letterSpacing: "0.16em",
          textTransform: "uppercase",
          color: mk.accent,
          marginBottom: 12,
        }}
      >
        YOUR EXIT CONDITION · WRITTEN JAN 9
      </div>
      <div
        style={{
          fontFamily: mk.display,
          fontStyle: "italic",
          fontSize: 18,
          lineHeight: 1.5,
          color: mk.cream,
        }}
      >
        &ldquo;If the cloud companies stop spending on AI chips, or Nvidia loses the developer ecosystem, I&apos;m out.&rdquo;
      </div>

      <div style={{ display: "flex", gap: 12, marginTop: 28 }}>
        <span
          style={{
            flex: 1,
            textAlign: "center",
            fontFamily: mk.sans,
            fontSize: 14,
            fontWeight: 500,
            color: mk.cream,
            border: `1px solid ${mk.nightLine}`,
            borderRadius: 10,
            padding: "13px 0",
            cursor: "pointer",
          }}
        >
          Still believe →
        </span>
        <span
          style={{
            flex: 1,
            textAlign: "center",
            fontFamily: mk.sans,
            fontSize: 14,
            fontWeight: 500,
            color: "#fff",
            background: mk.accent,
            borderRadius: 10,
            padding: "13px 0",
            cursor: "pointer",
          }}
        >
          Story changed →
        </span>
      </div>
    </div>
  );
}

export default function LandingPage() {
  return (
    <div style={{ background: mk.paper, color: mk.ink, fontFamily: mk.sans }}>
      <style>{`
        @keyframes pkPulse {
          0%   { box-shadow: 0 0 0 0   rgba(193,73,42,0.55); }
          100% { box-shadow: 0 0 0 8px rgba(193,73,42,0); }
        }
        @keyframes mkFloat {
          0%,100% { transform: rotate(1.4deg) translateY(0); }
          50%     { transform: rotate(1.4deg) translateY(-10px); }
        }
      `}</style>

      <MarketingNav />

      {/* ─── HERO ────────────────────────────────────────────────── */}
      <section style={{ background: mk.paper, position: "relative", overflow: "hidden" }}>
        <div
          style={{
            maxWidth: 1180,
            margin: "0 auto",
            padding: `0 ${hPad}`,
          }}
        >
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1.02fr 0.98fr",
              gap: "clamp(40px, 5vw, 56px)",
              alignItems: "center",
              minHeight: 720,
              paddingTop: 36,
              paddingBottom: 36,
            }}
            className="max-lg:grid-cols-1"
          >
            {/* Left */}
            <div>
              <div
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 10,
                  marginBottom: 30,
                }}
              >
                <span
                  style={{
                    width: 6,
                    height: 6,
                    borderRadius: 999,
                    background: mk.accent,
                    display: "inline-block",
                    animation: "pkPulse 2.4s ease-out infinite",
                  }}
                />
                <span
                  style={{
                    fontFamily: mk.mono,
                    fontSize: 10.5,
                    letterSpacing: "0.16em",
                    textTransform: "uppercase",
                    color: mk.pencil,
                  }}
                >
                  Private beta · summer 2026
                </span>
              </div>

              <h1
                style={{
                  fontFamily: mk.display,
                  fontWeight: 500,
                  fontSize: "clamp(72px, 9.5vw, 100px)",
                  lineHeight: 0.98,
                  letterSpacing: "-0.03em",
                  margin: "0 0 clamp(20px, 3vw, 30px)",
                  color: mk.ink,
                }}
              >
                The reason
                <br />
                you hold it,
                <br />
                <span style={{ fontStyle: "italic", color: mk.accent }}>kept honest.</span>
              </h1>

              <p
                style={{
                  fontFamily: mk.display,
                  fontWeight: 500,
                  fontSize: "clamp(18px, 1.9vw, 21px)",
                  lineHeight: 1.5,
                  color: mk.inkSoft,
                  maxWidth: 460,
                  margin: "0 0 clamp(28px, 4vw, 40px)",
                }}
              >
                Write the reason you bought each position. We read the earnings, filings and news
                against it. When it starts to break,{" "}
                <em style={{ color: mk.ink }}>we tell you.</em>
              </p>

              <div style={{ display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap" }}>
                <a
                  href="#signup"
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    background: mk.accent,
                    color: "#fff",
                    fontFamily: mk.sans,
                    fontSize: 16,
                    fontWeight: 500,
                    padding: "15px 26px",
                    borderRadius: 999,
                    boxShadow: `0 1px 0 ${mk.accentDeep}`,
                    textDecoration: "none",
                    whiteSpace: "nowrap",
                  }}
                >
                  Write your first reason →
                </a>
                <a
                  href="#try-it"
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 9,
                    fontFamily: mk.sans,
                    fontSize: 15,
                    fontWeight: 500,
                    color: mk.ink,
                    textDecoration: "none",
                  }}
                >
                  <span
                    style={{
                      width: 30,
                      height: 30,
                      borderRadius: 999,
                      border: `1.4px solid ${mk.ink}`,
                      display: "inline-flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontSize: 11,
                      flexShrink: 0,
                    }}
                  >
                    ▶
                  </span>
                  See how it works
                </a>
              </div>
            </div>

            {/* Right — product card */}
            <div
              style={{
                position: "relative",
                display: "flex",
                justifyContent: "center",
                alignItems: "center",
              }}
              className="max-lg:hidden"
            >
              <div
                style={{
                  animation: "mkFloat 6s ease-in-out infinite",
                  width: "100%",
                  display: "flex",
                  justifyContent: "center",
                }}
              >
                <NVDACard />
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ─── THE PROBLEM ─────────────────────────────────────────── */}
      <section
        style={{
          background: mk.paperHi,
          padding: `${vPad} ${hPad}`,
          borderTop: `1px solid ${mk.rule}`,
        }}
      >
        <div style={{ maxWidth: 1180, margin: "0 auto" }}>
          <div style={{ maxWidth: 820 }}>
            <Kicker>The problem</Kicker>
            <h2
              style={{
                fontFamily: mk.display,
                fontSize: "clamp(36px, 5vw, 56px)",
                fontWeight: 500,
                letterSpacing: "-0.025em",
                lineHeight: 1.04,
                margin: 0,
              }}
            >
              You bought it for a reason.
              <br />
              <span style={{ fontStyle: "italic", color: mk.accent }}>
                Can you still remember it?
              </span>
            </h2>
            <div
              style={{
                fontFamily: mk.display,
                fontWeight: 500,
                fontSize: "clamp(18px, 1.8vw, 22px)",
                lineHeight: 1.6,
                marginTop: 32,
              }}
            >
              <p style={{ margin: "0 0 22px", color: mk.ink }}>
                You had a reason when you bought.{" "}
                <em>
                  &ldquo;AI is the next decade.&rdquo; &ldquo;The market has completely mispriced
                  this.&rdquo;
                </em>{" "}
                Six months later you can barely remember it, never mind whether it still holds.
              </p>
              <p style={{ margin: 0, color: mk.inkSoft }}>
                So you check the price instead. Green feels like being right. Red feels like being
                wrong. Neither one tells you whether{" "}
                <strong style={{ color: mk.ink, fontWeight: 600 }}>the reason you bought</strong>{" "}
                still holds. That is the thing that separates conviction from hope, and nothing out
                there keeps an eye on it.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ─── TRY IT ──────────────────────────────────────────────── */}
      <section
        id="try-it"
        style={{
          padding: `${vPad} ${hPad}`,
          background: mk.paper,
          borderTop: `1px solid ${mk.rule}`,
        }}
      >
        <div style={{ maxWidth: 1180, margin: "0 auto" }}>
          <Kicker color={mk.pencil}>Try it</Kicker>
          <h2
            style={{
              fontFamily: mk.display,
              fontStyle: "italic",
              fontWeight: 400,
              fontSize: "clamp(36px, 5vw, 72px)",
              lineHeight: 0.97,
              letterSpacing: "-0.01em",
              margin: "0 0 clamp(28px, 4vw, 48px)",
              maxWidth: 800,
            }}
          >
            Write any reason.
            <br />
            <span style={{ color: mk.accent }}>See what comes back.</span>
          </h2>
          <ThesisDemo />
        </div>
      </section>

      {/* ─── HOW IT WORKS ────────────────────────────────────────── */}
      <section
        id="how-it-works"
        style={{
          padding: `${vPad} ${hPad}`,
          background: mk.paper,
          borderTop: `1px solid ${mk.rule}`,
        }}
      >
        <div style={{ maxWidth: 1180, margin: "0 auto" }}>
          <Kicker color={mk.pencil}>How it works</Kicker>
          <h2
            style={{
              fontFamily: mk.display,
              fontSize: "clamp(36px, 5vw, 56px)",
              fontWeight: 500,
              letterSpacing: "-0.025em",
              lineHeight: 1,
              margin: 0,
            }}
          >
            Three steps.{" "}
            <span style={{ fontStyle: "italic", color: mk.accent }}>
              That is the whole thing.
            </span>
          </h2>

          <div style={{ marginTop: 56 }}>
            {(
              [
                [
                  "01",
                  "Write the reason",
                  "A sentence or two. Why you own it and what would make you sell. That becomes your exit condition.",
                ],
                [
                  "02",
                  "We stand watch",
                  "PenKeep reads the earnings, filings, analyst notes and news, then ignores everything that does not touch the reason you wrote.",
                ],
                [
                  "03",
                  "You decide",
                  "When something real tests your reason, we put your own words back in front of you. You make the call. We keep a record of it.",
                ],
              ] as const
            ).map(([n, title, desc]) => (
              <div
                key={n}
                style={{
                  display: "grid",
                  gridTemplateColumns: "100px 1fr 1.1fr",
                  gap: "clamp(20px, 3vw, 40px)",
                  alignItems: "baseline",
                  padding: "40px 0",
                  borderTop: `1px solid ${mk.rule}`,
                }}
                className="max-md:grid-cols-1 max-md:gap-3"
              >
                <div
                  style={{
                    fontFamily: mk.display,
                    fontSize: "clamp(48px, 6vw, 72px)",
                    fontWeight: 400,
                    fontStyle: "italic",
                    color: mk.accent,
                    lineHeight: 0.9,
                  }}
                >
                  {n}
                </div>
                <div
                  style={{
                    fontFamily: mk.display,
                    fontSize: "clamp(22px, 2.5vw, 34px)",
                    fontWeight: 500,
                    letterSpacing: "-0.015em",
                    lineHeight: 1.1,
                    color: mk.ink,
                  }}
                >
                  {title}
                </div>
                <div
                  style={{
                    fontFamily: mk.display,
                    fontWeight: 500,
                    fontSize: "clamp(16px, 1.6vw, 18px)",
                    lineHeight: 1.55,
                    color: mk.inkSoft,
                  }}
                >
                  {desc}
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ─── WHEN IT MATTERS — dark ──────────────────────────────── */}
      <section
        style={{
          background: mk.night,
          color: mk.cream,
          padding: `${vPad} ${hPad}`,
          position: "relative",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            position: "absolute",
            left: -120,
            top: 80,
            width: 420,
            height: 420,
            borderRadius: "50%",
            background: "radial-gradient(circle, rgba(193,73,42,0.14), transparent 70%)",
            pointerEvents: "none",
          }}
        />
        <div style={{ maxWidth: 1180, margin: "0 auto", position: "relative" }}>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 1fr",
              gap: "clamp(48px, 7vw, 96px)",
              alignItems: "center",
            }}
            className="max-lg:grid-cols-1"
          >
            <div>
              <Kicker>When it matters</Kicker>
              <h2
                style={{
                  fontFamily: mk.display,
                  fontSize: "clamp(36px, 5vw, 56px)",
                  fontWeight: 500,
                  letterSpacing: "-0.025em",
                  lineHeight: 1.04,
                  margin: 0,
                  color: mk.cream,
                }}
              >
                Your own words,
                <br />
                right when{" "}
                <span style={{ fontStyle: "italic", color: mk.accent }}>evidence fires.</span>
              </h2>
              <p
                style={{
                  fontFamily: mk.display,
                  fontWeight: 500,
                  fontSize: "clamp(17px, 1.7vw, 20px)",
                  lineHeight: 1.6,
                  color: mk.creamDim,
                  marginTop: 28,
                  maxWidth: 460,
                }}
              >
                Not a price alert. Not noise. The exit condition you wrote, put back in front of
                you the moment something starts to test it. Think it through. Don&apos;t react.
              </p>
            </div>

            <div>
              {/* 4-step progress strip */}
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  marginBottom: 24,
                  overflow: "hidden",
                }}
              >
                {(
                  [
                    ["Evidence", mk.accent],
                    ["Your reason", mk.sage],
                    ["You decide", mk.sage],
                    ["On record", mk.accent],
                  ] as const
                ).map(([label, dotColor], i) => (
                  <div
                    key={label}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      flex: i < 3 ? "1 1 0" : "0 0 auto",
                      minWidth: 0,
                    }}
                  >
                    <span
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 6,
                        flexShrink: 0,
                      }}
                    >
                      <span
                        style={{
                          width: 7,
                          height: 7,
                          borderRadius: 999,
                          background: dotColor,
                          flexShrink: 0,
                        }}
                      />
                      <span
                        style={{
                          fontFamily: mk.mono,
                          fontSize: 8,
                          letterSpacing: "0.12em",
                          textTransform: "uppercase",
                          color: mk.creamDim,
                          whiteSpace: "nowrap",
                        }}
                      >
                        {label}
                      </span>
                    </span>
                    {i < 3 && (
                      <span
                        style={{
                          flex: 1,
                          height: 1,
                          background: mk.nightLine,
                          margin: "0 8px",
                          minWidth: 8,
                        }}
                      />
                    )}
                  </div>
                ))}
              </div>
              <ConvictionDemo />
            </div>
          </div>
        </div>
      </section>

      {/* ─── A REAL STORY ────────────────────────────────────────── */}
      <section
        style={{
          padding: `${vPad} ${hPad}`,
          borderTop: `1px solid ${mk.rule}`,
        }}
      >
        <div style={{ maxWidth: 1180, margin: "0 auto" }}>
          <Kicker color={mk.pencil}>A real story</Kicker>
          <h2
            style={{
              fontFamily: mk.display,
              fontStyle: "italic",
              fontWeight: 400,
              fontSize: "clamp(36px, 5vw, 72px)",
              lineHeight: 0.97,
              letterSpacing: "-0.01em",
              margin: "0 0 clamp(10px, 2vw, 16px)",
            }}
          >
            One thesis.
            <br />
            <span style={{ color: mk.accent }}>Eight months.</span>
          </h2>
          <p
            style={{
              fontFamily: mk.sans,
              fontSize: "clamp(15px, 1.5vw, 18px)",
              color: mk.pencil,
              lineHeight: 1.6,
              maxWidth: 580,
              margin: "0 0 clamp(32px, 5vw, 48px)",
            }}
          >
            Someone bought TSLA in March 2024 with a specific reason. Here is exactly how the
            evidence moved, and the moment penKeep would have surfaced their own exit condition
            back to them.
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

      {/* ─── WHAT WE DON'T DO ────────────────────────────────────── */}
      <section
        style={{
          background: mk.paperHi,
          padding: `${vPad} ${hPad}`,
          borderTop: `1px solid ${mk.rule}`,
        }}
      >
        <div style={{ maxWidth: 1180, margin: "0 auto" }}>
          <Kicker>What we don&apos;t do</Kicker>
          <h2
            style={{
              fontFamily: mk.display,
              fontSize: "clamp(36px, 5vw, 56px)",
              fontWeight: 500,
              letterSpacing: "-0.025em",
              lineHeight: 1,
              margin: 0,
            }}
          >
            Built around your reason.{" "}
            <span style={{ fontStyle: "italic", color: mk.accent }}>Not their feed.</span>
          </h2>

          <div style={{ marginTop: 48 }}>
            {(
              [
                [
                  "Price alerts",
                  "A price can fall for a hundred reasons that have nothing to do with why you bought. We wait for the real evidence. An earnings line, a filing, a lost customer. That is what reaches you.",
                ],
                [
                  "A social feed",
                  "There’s no one else in here. The only portfolio we pay attention to is the one you actually own.",
                ],
                [
                  "Buy / sell signals",
                  "Every decision stays yours. When something tests your reason, we set your own words beside it and let you make the call.",
                ],
                [
                  "Daily engagement",
                  "Most days you won’t hear from us. We stay quiet until something touches a reason you wrote, then say so plainly. Once a week, a short digest.",
                ],
              ] as const
            ).map(([label, answer]) => (
              <div
                key={label}
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 1.7fr",
                  gap: "clamp(20px, 3vw, 40px)",
                  padding: "26px 0",
                  borderTop: `1px solid ${mk.rule}`,
                  alignItems: "baseline",
                }}
                className="max-md:grid-cols-1 max-md:gap-2"
              >
                <div
                  style={{
                    fontFamily: mk.display,
                    fontSize: "clamp(20px, 2.2vw, 28px)",
                    fontWeight: 500,
                    fontStyle: "italic",
                    color: mk.ink,
                  }}
                >
                  {label}
                </div>
                <div
                  style={{
                    fontFamily: mk.display,
                    fontWeight: 500,
                    fontSize: "clamp(16px, 1.6vw, 19px)",
                    lineHeight: 1.5,
                    color: mk.ink,
                  }}
                >
                  {answer}
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ─── THE BLIND SPOT — light ──────────────────────────────── */}
      <section style={{ background: mk.paperHi, padding: `${vPad} ${hPad}` }}>
        <div style={{ maxWidth: 1180, margin: "0 auto" }}>
          <Kicker>The part you didn&apos;t write down</Kicker>
          <div
            style={{
              fontFamily: mk.display,
              fontSize: "clamp(30px, 4.5vw, 56px)",
              fontWeight: 500,
              letterSpacing: "-0.025em",
              lineHeight: 1.05,
              maxWidth: 940,
              color: mk.ink,
            }}
          >
            The thing that sinks a stock is usually the one you&apos;d have felt{" "}
            <span style={{ fontStyle: "italic", color: mk.accent }}>silly writing down</span>.
          </div>
          <div
            style={{
              fontFamily: mk.display,
              fontWeight: 500,
              fontSize: "clamp(17px, 1.7vw, 20px)",
              lineHeight: 1.55,
              color: mk.inkSoft,
              maxWidth: 660,
              marginTop: 28,
            }}
          >
            You note what you believe, and we keep an eye on it. We also read for the rest.
            A big customer quietly building their own version. A rule change three countries
            away. A shift everyone calls obvious in hindsight. When one turns up, you hear
            about it early, while there&apos;s still something you can do.
          </div>
        </div>
      </section>

      {/* ─── NO THESIS YET — light ───────────────────────────────── */}
      <section style={{ background: mk.paper, padding: `${vPad} ${hPad}` }}>
        <div style={{ maxWidth: 1180, margin: "0 auto" }}>
          <Kicker>No reason yet?</Kicker>
          <div
            style={{
              fontFamily: mk.display,
              fontSize: "clamp(30px, 4.5vw, 56px)",
              fontWeight: 500,
              letterSpacing: "-0.025em",
              lineHeight: 1.05,
              maxWidth: 940,
              color: mk.ink,
            }}
          >
            Bought on a hunch?{" "}
            <span style={{ fontStyle: "italic", color: mk.accent }}>Start anyway.</span>
          </div>
          <div
            style={{
              fontFamily: mk.display,
              fontWeight: 500,
              fontSize: "clamp(17px, 1.7vw, 20px)",
              lineHeight: 1.55,
              color: mk.inkSoft,
              maxWidth: 660,
              marginTop: 28,
            }}
          >
            Maybe a friend wouldn&apos;t shut up about it. Maybe it was everywhere for a week
            and you didn&apos;t want to miss it. Tell us the ticker. We&apos;ll lay out the
            case against it, the things that could go wrong that never come up in the group
            chat, and turn the hunch into a few plain things worth watching. Then we watch
            them, and you&apos;ve got a real reason on paper instead of a vibe.
          </div>
        </div>
      </section>

      {/* ─── BIGGER PICTURE — dark ───────────────────────────────── */}
      <section
        style={{
          background: mk.night,
          color: mk.cream,
          padding: `${vPad} ${hPad}`,
          position: "relative",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            position: "absolute",
            right: -120,
            top: -120,
            width: 460,
            height: 460,
            borderRadius: "50%",
            background: "radial-gradient(circle, rgba(193,73,42,0.16), transparent 70%)",
            pointerEvents: "none",
          }}
        />
        <div style={{ maxWidth: 1180, margin: "0 auto", position: "relative" }}>
          <Kicker>What you&apos;re really building</Kicker>
          <div
            style={{
              fontFamily: mk.display,
              fontSize: "clamp(30px, 4.5vw, 58px)",
              fontWeight: 500,
              letterSpacing: "-0.025em",
              lineHeight: 1.04,
              maxWidth: 940,
              color: mk.cream,
            }}
          >
            Every reason you write is a record of{" "}
            <span style={{ fontStyle: "italic", color: mk.accent }}>how you think</span>. No feed
            will ever hand that back to you.
          </div>
          <div
            style={{
              fontFamily: mk.display,
              fontWeight: 500,
              fontSize: "clamp(17px, 1.7vw, 20px)",
              lineHeight: 1.55,
              color: mk.creamDim,
              maxWidth: 640,
              marginTop: 28,
            }}
          >
            Give it a year and you have an honest record of your own judgment: what you believed,
            what actually happened, and whether you got it right.
          </div>
        </div>
      </section>

      {/* ─── FAQ ─────────────────────────────────────────────────── */}
      <section
        id="faq"
        style={{
          background: mk.paperHi,
          padding: `${vPad} ${hPad}`,
          borderTop: `1px solid ${mk.rule}`,
        }}
      >
        <div style={{ maxWidth: 1180, margin: "0 auto" }}>
          <Kicker>Questions</Kicker>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 1fr",
              gap: "40px 64px",
              marginTop: 12,
            }}
            className="max-md:grid-cols-1"
          >
            {(
              [
                [
                  "Is this financial advice?",
                  "No. PenKeep never tells you to buy, hold or sell. It shows you what is happening to the reasons you wrote down, and every decision stays yours.",
                ],
                [
                  "Do you connect to my brokerage?",
                  "You can connect it read-only to track positions, or just add your holdings by hand. We never place trades and never touch your money.",
                ],
                [
                  "What does “watching” actually mean?",
                  "For each reason you write, we keep an eye on the things that could prove it wrong: earnings, filings, competitor moves. Everything else, we leave alone.",
                ],
                [
                  "Will I get spammed with alerts?",
                  "No. Most weeks you will hear from us once, in the Sunday digest. We only send a real-time alert when something directly tests one of your exit conditions.",
                ],
              ] as const
            ).map(([q, a]) => (
              <div key={q}>
                <h3
                  style={{
                    fontFamily: mk.display,
                    fontSize: "clamp(18px, 1.8vw, 24px)",
                    fontWeight: 500,
                    letterSpacing: "-0.01em",
                    margin: "0 0 12px",
                    color: mk.ink,
                  }}
                >
                  {q}
                </h3>
                <p
                  style={{
                    fontFamily: mk.display,
                    fontWeight: 500,
                    fontSize: "clamp(15px, 1.5vw, 17.5px)",
                    lineHeight: 1.55,
                    color: mk.inkSoft,
                    margin: 0,
                  }}
                >
                  {a}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ─── FINAL CTA — dark ────────────────────────────────────── */}
      <section
        id="signup"
        style={{
          background: mk.night,
          color: mk.cream,
          padding: `clamp(80px, 10vw, 130px) ${hPad}`,
          textAlign: "center",
          position: "relative",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            position: "absolute",
            left: "50%",
            top: "40%",
            transform: "translate(-50%,-50%)",
            width: 620,
            height: 620,
            borderRadius: "50%",
            background: "radial-gradient(circle, rgba(193,73,42,0.16), transparent 70%)",
            pointerEvents: "none",
          }}
        />
        <div style={{ maxWidth: 1180, margin: "0 auto", position: "relative" }}>
          <div
            style={{
              fontFamily: mk.mono,
              fontSize: 10.5,
              letterSpacing: "0.16em",
              textTransform: "uppercase",
              color: mk.accent,
              marginBottom: "clamp(20px, 3vw, 28px)",
            }}
          >
            Limited seats · private beta
          </div>
          <h2
            style={{
              fontFamily: mk.display,
              fontWeight: 500,
              fontSize: "clamp(48px, 7vw, 80px)",
              lineHeight: 1,
              letterSpacing: "-0.03em",
              margin: "0 0 clamp(20px, 3vw, 28px)",
              color: mk.cream,
            }}
          >
            Write your first
            <br />
            <span style={{ fontStyle: "italic", color: mk.accent }}>real reason.</span>
          </h2>
          <p
            style={{
              fontFamily: mk.display,
              fontWeight: 500,
              fontSize: "clamp(16px, 1.6vw, 20px)",
              color: mk.creamDim,
              margin: "0 auto clamp(28px, 4vw, 40px)",
              maxWidth: 520,
              lineHeight: 1.5,
            }}
          >
            Join the waitlist. We&apos;ll reach out before launch with early access and a say in what
            we build.
          </p>
          <div style={{ display: "flex", justifyContent: "center" }}>
            <WaitlistForm dark />
          </div>
        </div>
      </section>

      <MarketingFooter />
    </div>
  );
}
