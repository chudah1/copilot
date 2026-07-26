import Link from "next/link";
import { MarketingNav } from "./_mkt/nav";
import { MarketingFooter } from "./_mkt/footer";
import { LaunchActions } from "./_mkt/launch-actions";
import { ThesisDemo } from "./_mkt/thesis-demo";
import { WatchThesisChange } from "./_mkt/timeline";
import { ConvictionDemo } from "./_mkt/conviction-demo";
import { mk } from "./_mkt/tokens";
import { InfoTip } from "@/components/ui/info-tip";
import { StressTestSearch } from "./_mkt/stress-test-search";

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
        <span style={{ display: "inline-flex", alignItems: "center", gap: 3 }}>
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
            NEEDS REVIEW
          </span>
          <InfoTip
            label="Needs review"
            align="end"
            iconClassName="text-[#b9afa2] hover:text-white"
          >
            This evidence directly relates to a condition the investor wrote. It is not a buy or sell signal.
          </InfoTip>
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

      <div style={{ display: "flex", alignItems: "center", gap: 3, marginBottom: 12 }}>
        <div
          style={{
            fontFamily: mk.mono,
            fontSize: 9.5,
            letterSpacing: "0.16em",
            textTransform: "uppercase",
            color: mk.accent,
          }}
        >
          WHAT WOULD CHANGE YOUR MIND · WRITTEN JAN 9
        </div>
        <InfoTip
          label="What would change your mind"
          iconClassName="text-[#b9afa2] hover:text-white"
        >
          The specific result or event that would make the investor reconsider owning the position.
        </InfoTip>
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
          Reason still holds →
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
          Reason no longer holds →
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
              gap: "clamp(40px, 5vw, 56px)",
              alignItems: "center",
              minHeight: 720,
              paddingTop: 36,
              paddingBottom: 36,
            }}
            className="grid grid-cols-1 lg:grid-cols-[1.02fr_0.98fr]"
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
              </div>

              <h1
                style={{
                  fontFamily: mk.display,
                  fontWeight: 500,
                  fontSize: "clamp(44px, 5.8vw, 72px)",
                  lineHeight: 1.05,
                  letterSpacing: "-0.025em",
                  margin: "0 0 clamp(16px, 2vw, 22px)",
                  color: mk.ink,
                }}
              >
                Your broker records the trade. penKeep remembers the decision.
              </h1>

              <p
                style={{
                  fontFamily: mk.display,
                  fontWeight: 500,
                  fontSize: "clamp(24px, 3vw, 36px)",
                  lineHeight: 1.2,
                  letterSpacing: "-0.015em",
                  color: mk.inkSoft,
                  margin: "0 0 clamp(28px, 4vw, 40px)",
                }}
              >
                Write down why you bought. If something important changes, penKeep brings those
                notes back so you can decide what to do.
              </p>

              <p
                style={{
                  fontFamily: mk.sans,
                  fontSize: "clamp(13px, 1.3vw, 15px)",
                  color: mk.pencil,
                  letterSpacing: "0.01em",
                  margin: "0 0 clamp(28px, 4vw, 40px)",
                }}
              >
                Your original notes, the relevant filings and news, and the decisions you made
                afterward, kept together in one place.
              </p>

              <div style={{ display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap" }}>
                <Link
                  href="/register"
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
                  Record your first decision →
                </Link>
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

              <StressTestSearch />
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
            <Kicker>The missing record</Kicker>
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
              The market remembers the price.
              <br />
              <span style={{ fontStyle: "italic", color: mk.accent }}>
                It does not remember your reasoning.
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
                Six months later, every decision has a neat explanation. The original uncertainty,
                the warning you dismissed, and the condition you promised to watch have disappeared.
              </p>
              <p style={{ margin: 0, color: mk.inkSoft }}>
                A gain can hide a poor decision. A loss does not always mean the thinking was bad.
                Without the original notes, it is hard to learn much from either one.
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
            Write one reason you own a stock.
            <br />
            <span style={{ color: mk.accent }}>See the facts penKeep would check.</span>
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
            Write it down. Keep watch.{" "}
            <span style={{ fontStyle: "italic", color: mk.accent }}>
              That is the whole thing.
            </span>
          </h2>

          <div style={{ marginTop: 56 }}>
            {(
              [
                [
                  "01",
                  "Record the decision",
                  "Write why you own it and what would change your mind. Do it now, while you still remember what you were thinking.",
                ],
                [
                  "02",
                  "Watch the evidence",
                  "penKeep reads the earnings, filings and news, then ignores everything that does not touch a condition you put on record.",
                ],
                [
                  "03",
                  "Revisit the call",
                  "If one of those conditions changes, penKeep shows you what you wrote and what happened. You decide what to do next.",
                ],
              ] as const
            ).map(([n, title, desc]) => (
              <div
                key={n}
                style={{
                  gap: "clamp(20px, 3vw, 40px)",
                  alignItems: "baseline",
                  padding: "40px 0",
                  borderTop: `1px solid ${mk.rule}`,
                }}
                className="grid grid-cols-1 md:grid-cols-[100px_1fr_1.1fr]"
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
              gap: "clamp(48px, 7vw, 96px)",
              alignItems: "center",
            }}
            className="grid grid-cols-1 lg:grid-cols-2"
          >
            <div>
              <Kicker>At the decision point</Kicker>
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
                Your original decision,
                <br />
                returned with{" "}
                <span style={{ fontStyle: "italic", color: mk.accent }}>the evidence.</span>
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
                Not an AI recommendation. Just the condition you wrote, the new information, and
                the decision you made afterward, kept together.
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
            One decision.
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
            One TSLA decision, followed from the original belief to its first real test. The record
            preserves what the investor knew, when the evidence changed, and the call made next.
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
          <Kicker>What makes the record useful</Kicker>
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
            A decision record{" "}
            <InfoTip label="Decision record" align="center">
              Your original reason, relevant evidence, and the decision you made afterward, kept together with dates.
            </InfoTip>
            , not{" "}
            <span style={{ fontStyle: "italic", color: mk.accent }}>another investing feed</span>.
          </h2>

          <div style={{ marginTop: 48 }}>
            {(
              [
                [
                  "Not just alerts",
                  "An alert tells you what happened today. penKeep also shows what you wrote before it happened and keeps the decision you made next.",
                ],
                [
                  "Not a social feed",
                  "There is no crowd to perform for and no hot-stock loop. This is a private record of the portfolio and decisions that are actually yours.",
                ],
                [
                  "No buy or sell calls",
                  "penKeep shows you the notes and the new information. It does not make the decision for you.",
                ],
                [
                  "Not daily engagement",
                  "Most days the record stays quiet. It returns only when evidence matches a condition you wrote or an earlier decision is ready for review.",
                ],
              ] as const
            ).map(([label, answer]) => (
              <div
                key={label}
                style={{
                  gap: "clamp(20px, 3vw, 40px)",
                  padding: "26px 0",
                  borderTop: `1px solid ${mk.rule}`,
                  alignItems: "baseline",
                }}
                className="grid grid-cols-1 md:grid-cols-[1fr_1.7fr]"
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
            penKeep also checks for major customer, competitor, regulatory and management changes
            that could affect your reason, even when you did not name them. If one matters, it shows
            you the source and the part of your reason that may need another look.
          </div>
        </div>
      </section>

      {/* ─── NO THESIS YET — light ───────────────────────────────── */}
      <section style={{ background: mk.paper, padding: `${vPad} ${hPad}` }}>
        <div style={{ maxWidth: 1180, margin: "0 auto" }}>
          <Kicker>Before the decision</Kicker>
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
            Make the bear case part of{" "}
            <span style={{ fontStyle: "italic", color: mk.accent }}>the record.</span>
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
            Before you buy, run the ticker through the counter-thesis{" "}
            <InfoTip label="Counter-thesis" align="center">
              The strongest argument against owning the stock, plus risks and specific conditions you can check later.
            </InfoTip>
            . penKeep gives you the strongest argument against it, risks you may have missed, and
            specific conditions to watch.
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
          <Kicker>After a year</Kicker>
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
            Build a private track record of{" "}
            <span style={{ fontStyle: "italic", color: mk.accent }}>how you decide</span>.
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
            You can look back at which assumptions held, which warnings you ignored, and what you
            were thinking when you chose to hold, trim, or sell.
          </div>
          <div
            style={{
              fontFamily: mk.mono,
              fontSize: "clamp(13px, 1.3vw, 15px)",
              lineHeight: 1.7,
              color: mk.creamDim,
              maxWidth: 640,
              marginTop: 22,
            }}
          >
            After each hold, trim or exit decision, penKeep records what happened next. Quarterly
            reviews show which warnings you acted on, which you dismissed, and whether those calls
            held up.
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
              gap: "40px 64px",
              marginTop: 12,
            }}
            className="grid grid-cols-1 md:grid-cols-2"
          >
            {(
              [
                [
                  "Is this financial advice?",
                  "No. penKeep never tells you to buy, hold or sell. It shows you what is happening to the reasons you wrote down, and every decision stays yours.",
                ],
                [
                  "Do you connect to my brokerage?",
                  "You can connect it read-only to track positions, or just add your holdings by hand. We never place trades and never touch your money.",
                ],
                [
                  "How is this different from another alert app?",
                  "Alerts disappear after telling you what happened. penKeep ties evidence to the belief you recorded, captures the decision you made, and returns it later when the outcome can be reviewed.",
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
            Your notes stay private · free to start
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
            Put your first decision
            <br />
            <span style={{ fontStyle: "italic", color: mk.accent }}>on the record.</span>
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
            Start with a position you already own, or run the bear case before the next one.
          </p>
          <div style={{ display: "flex", justifyContent: "center" }}>
            <LaunchActions dark />
          </div>
        </div>
      </section>

      <MarketingFooter />
    </div>
  );
}
