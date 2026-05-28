"use client";

import { useState, useEffect } from "react";
import { mk } from "./tokens";

const SCENARIOS = [
  {
    stock: "TSLA",
    company: "Tesla",
    event: "Q3 deliveries -8.4% YoY. Robotaxi event called 'underwhelming' by 7 of 9 analysts.",
    severity: "high",
    exitCondition: "If EV demand growth reverses or robotaxi misses a credible timeline.",
    decision: "invalidated" as const,
    decisionLabel: "Thesis invalidated",
    decisionColor: "text-red",
    note: "Story changed. Moving on.",
    outcome: "broke" as const,
  },
  {
    stock: "NVDA",
    company: "NVIDIA",
    event: "Hyperscaler capex guidance revised upward. H100 allocations still 6-month backlog.",
    severity: "medium",
    exitCondition: "If hyperscaler AI capex plateaus or a credible alternative to CUDA emerges.",
    decision: "reaffirmed" as const,
    decisionLabel: "Thesis reaffirmed",
    decisionColor: "text-green",
    note: "Picks-and-shovels story is intact.",
    outcome: "held" as const,
  },
  {
    stock: "RR.L",
    company: "Rolls-Royce",
    event: "Civil aero gross margin expands 2.4pp. Defence order book hits £8.7B.",
    severity: "low",
    exitCondition: "If turnaround margins stall or the CFO revises the target for a second time.",
    decision: "reaffirmed" as const,
    decisionLabel: "Thesis reaffirmed",
    decisionColor: "text-green",
    note: "Turnaround is on track.",
    outcome: "held" as const,
  },
];

type Phase = "event" | "exit" | "decide" | "recorded";

const PHASE_DELAY = 1400;

export function ConvictionDemo() {
  const [idx, setIdx] = useState(0);
  const [phase, setPhase] = useState<Phase>("event");
  const [paused, setPaused] = useState(false);

  const s = SCENARIOS[idx];

  useEffect(() => {
    if (paused) return;
    const phases: Phase[] = ["event", "exit", "decide", "recorded"];
    let p = phases.indexOf(phase);
    const t = setTimeout(() => {
      p++;
      if (p >= phases.length) {
        setPhase("event");
        setIdx((i) => (i + 1) % SCENARIOS.length);
      } else {
        setPhase(phases[p]);
      }
    }, p === phases.length - 1 ? PHASE_DELAY * 2.2 : PHASE_DELAY);
    return () => clearTimeout(t);
  }, [phase, paused, idx]);

  const severityColor =
    s.severity === "high" ? mk.accent : s.severity === "medium" ? "oklch(0.72 0.15 65)" : mk.pencil;

  return (
    <div
      style={{ fontFamily: mk.sans, display: "flex", flexDirection: "column", gap: 0 }}
      onClick={() => setPaused((p) => !p)}
    >
      {/* Step labels */}
      <div style={{ display: "flex", gap: 0, marginBottom: 16 }}>
        {(["event", "exit", "decide", "recorded"] as Phase[]).map((p, i) => {
          const active = phase === p;
          const past =
            ["event", "exit", "decide", "recorded"].indexOf(phase) >
            ["event", "exit", "decide", "recorded"].indexOf(p);
          const labels = ["Evidence fires", "Your condition", "You decide", "Logged forever"];
          return (
            <div
              key={p}
              style={{
                flex: 1,
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                gap: 6,
                position: "relative",
              }}
            >
              <div
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: 999,
                  background: active ? mk.accent : past ? mk.green : "#ffffff25",
                  transition: "background 400ms ease",
                  position: "relative",
                  zIndex: 1,
                }}
              />
              {i < 3 && (
                <div
                  style={{
                    position: "absolute",
                    top: 3.5,
                    left: "50%",
                    width: "100%",
                    height: 1,
                    background: past ? mk.green : "#ffffff18",
                    transition: "background 400ms ease",
                    zIndex: 0,
                  }}
                />
              )}
              <span
                style={{
                  fontFamily: mk.mono,
                  fontSize: 9,
                  letterSpacing: "0.1em",
                  textTransform: "uppercase",
                  color: active ? "#fff" : past ? `${mk.green}cc` : "#ffffff45",
                  textAlign: "center",
                  transition: "color 400ms ease",
                  whiteSpace: "nowrap",
                }}
              >
                {labels[i]}
              </span>
            </div>
          );
        })}
      </div>

      {/* Main card */}
      <div
        style={{
          background: "#1a1916",
          border: "1px solid #ffffff14",
          borderRadius: 14,
          overflow: "hidden",
          minHeight: 240,
        }}
      >
        {/* Stock header */}
        <div
          style={{
            padding: "14px 18px",
            borderBottom: "1px solid #ffffff0e",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 10,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span
              style={{
                fontFamily: mk.mono,
                fontSize: 12,
                fontWeight: 700,
                color: "#fff",
                letterSpacing: "0.1em",
              }}
            >
              {s.stock}
            </span>
            <span style={{ fontFamily: mk.sans, fontSize: 13, color: "#aaa" }}>
              {s.company}
            </span>
          </div>
          <span
            style={{
              fontFamily: mk.mono,
              fontSize: 9,
              letterSpacing: "0.12em",
              textTransform: "uppercase",
              color: paused ? mk.accent : "#aaa",
            }}
          >
            {paused ? "paused" : "live"}
          </span>
        </div>

        <div style={{ padding: "18px 18px", display: "flex", flexDirection: "column", gap: 14 }}>
          {/* Phase: event */}
          {phase === "event" && (
            <div style={{ animation: "mkFadeIn 350ms ease-out" }}>
              <div
                style={{
                  fontFamily: mk.mono,
                  fontSize: 9,
                  letterSpacing: "0.14em",
                  textTransform: "uppercase",
                  color: severityColor,
                  marginBottom: 8,
                }}
              >
                {s.severity} signal · penKeep detected
              </div>
              <p
                style={{
                  fontFamily: mk.sans,
                  fontSize: "clamp(14px,1.8vw,17px)",
                  color: "#e8e4dc",
                  lineHeight: 1.45,
                  margin: 0,
                }}
              >
                {s.event}
              </p>
            </div>
          )}

          {/* Phase: exit */}
          {phase === "exit" && (
            <div style={{ animation: "mkFadeIn 350ms ease-out" }}>
              <div
                style={{
                  fontFamily: mk.mono,
                  fontSize: 9,
                  letterSpacing: "0.14em",
                  textTransform: "uppercase",
                  color: "#aaa",
                  marginBottom: 8,
                }}
              >
                Your exit condition · written when you bought
              </div>
              <blockquote
                style={{
                  margin: 0,
                  paddingLeft: 14,
                  borderLeft: `2px solid ${mk.accent}`,
                  fontFamily: mk.sans,
                  fontSize: "clamp(14px,1.8vw,17px)",
                  fontStyle: "italic",
                  color: "#e8e4dc",
                  lineHeight: 1.45,
                }}
              >
                &ldquo;{s.exitCondition}&rdquo;
              </blockquote>
            </div>
          )}

          {/* Phase: decide */}
          {phase === "decide" && (
            <div style={{ animation: "mkFadeIn 350ms ease-out", display: "flex", flexDirection: "column", gap: 12 }}>
              <div
                style={{
                  fontFamily: mk.mono,
                  fontSize: 9,
                  letterSpacing: "0.14em",
                  textTransform: "uppercase",
                  color: "#aaa",
                }}
              >
                Your turn to decide
              </div>
              <div style={{ display: "flex", gap: 8 }}>
                <button
                  style={{
                    padding: "9px 16px",
                    background: s.decision === "reaffirmed" ? mk.green : "transparent",
                    color: s.decision === "reaffirmed" ? "#fff" : "#666",
                    border: `1px solid ${s.decision === "reaffirmed" ? mk.green : "#ffffff18"}`,
                    borderRadius: 8,
                    fontFamily: mk.sans,
                    fontSize: 13,
                    cursor: "pointer",
                    fontWeight: s.decision === "reaffirmed" ? 600 : 400,
                    transition: "all 200ms",
                  }}
                >
                  Still believe →
                </button>
                <button
                  style={{
                    padding: "9px 16px",
                    background: s.decision === "invalidated" ? mk.accent : "transparent",
                    color: s.decision === "invalidated" ? "#fff" : "#666",
                    border: `1px solid ${s.decision === "invalidated" ? mk.accent : "#ffffff18"}`,
                    borderRadius: 8,
                    fontFamily: mk.sans,
                    fontSize: 13,
                    cursor: "pointer",
                    fontWeight: s.decision === "invalidated" ? 600 : 400,
                    transition: "all 200ms",
                  }}
                >
                  Story changed →
                </button>
              </div>
              <p style={{ fontFamily: mk.sans, fontSize: 12, color: "#555", margin: 0, lineHeight: 1.4 }}>
                Either answer is correct. One thing is not: not deciding.
              </p>
            </div>
          )}

          {/* Phase: recorded */}
          {phase === "recorded" && (
            <div style={{ animation: "mkFadeIn 350ms ease-out", display: "flex", flexDirection: "column", gap: 10 }}>
              <div
                style={{
                  fontFamily: mk.mono,
                  fontSize: 9,
                  letterSpacing: "0.14em",
                  textTransform: "uppercase",
                  color: s.outcome === "broke" ? mk.accent : mk.green,
                  marginBottom: 2,
                }}
              >
                Decision logged · {s.decisionLabel}
              </div>
              <div
                style={{
                  display: "flex",
                  gap: 10,
                  padding: "12px 14px",
                  background: "#ffffff08",
                  borderRadius: 10,
                  border: "1px solid #ffffff0e",
                }}
              >
                <span
                  style={{
                    width: 8,
                    height: 8,
                    borderRadius: 999,
                    background: s.outcome === "broke" ? mk.accent : mk.green,
                    flexShrink: 0,
                    marginTop: 5,
                  }}
                />
                <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
                  <span
                    style={{
                      fontFamily: mk.sans,
                      fontSize: 14,
                      color: "#e8e4dc",
                      fontWeight: 500,
                    }}
                  >
                    {s.note}
                  </span>
                  <span style={{ fontFamily: mk.mono, fontSize: 10, color: "#555", letterSpacing: "0.06em" }}>
                    {s.exitCondition.slice(0, 52)}…
                  </span>
                </div>
                <span
                  style={{
                    marginLeft: "auto",
                    alignSelf: "flex-start",
                    fontFamily: mk.mono,
                    fontSize: 9,
                    letterSpacing: "0.14em",
                    textTransform: "uppercase",
                    padding: "3px 8px",
                    border: `1px solid ${s.outcome === "broke" ? mk.accent + "60" : mk.green + "60"}`,
                    color: s.outcome === "broke" ? mk.accent : mk.green,
                    borderRadius: 4,
                    whiteSpace: "nowrap",
                  }}
                >
                  {s.outcome === "broke" ? "Thesis broke" : "Holding"}
                </span>
              </div>
              <p style={{ fontFamily: mk.sans, fontSize: 12, color: "#555", margin: 0, lineHeight: 1.4 }}>
                Six months from now, you&apos;ll know whether you were right. penKeep will remember.
              </p>
            </div>
          )}
        </div>
      </div>

      <p
        style={{
          fontFamily: mk.mono,
          fontSize: 10,
          color: "#ffffff30",
          textAlign: "center",
          marginTop: 10,
          letterSpacing: "0.06em",
        }}
      >
        click to {paused ? "resume" : "pause"} · auto-cycling
      </p>
    </div>
  );
}
