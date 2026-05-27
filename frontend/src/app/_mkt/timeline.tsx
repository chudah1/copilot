"use client";

import { useState, useEffect } from "react";
import { mk } from "./tokens";

const STEPS = [
  { date: "Mar 12", label: "Bought TSLA",     kind: "thesis", text: "EV growth + robotaxi optionality nobody is pricing." },
  { date: "Apr 22", label: "Q1 deliveries",   kind: "up",     text: "Q1 deliveries beat consensus by 3%." },
  { date: "May 14", label: "Cybertruck ramp", kind: "flat",   text: "Cybertruck production hits modest scale." },
  { date: "Jul 02", label: "Q2 deliveries",   kind: "down",   text: "Q2 deliveries -4.8% YoY — a small wobble." },
  { date: "Aug 10", label: "Margin guide",    kind: "down",   text: "Auto gross margin compresses to 14.6%." },
  { date: "Oct 10", label: "Robotaxi event",  kind: "alert",  text: '"Underwhelming" — 7 of 9 analysts.' },
  { date: "Oct 18", label: "Q3 deliveries",   kind: "alert",  text: "Q3 deliveries -8.4% YoY." },
  { date: "Oct 23", label: "penKeep alert",   kind: "mail",   text: "Your reason for owning TSLA may have moved." },
] as const;

function statusForStep(s: number) {
  if (s < 3) return { label: "✓ on thesis",      bg: mk.greenSoft,  fg: mk.green  };
  if (s < 5) return { label: "· watching",        bg: mk.cardSoft,   fg: mk.pencil };
  return         { label: "! reason changed",  bg: mk.accentSoft, fg: mk.accent };
}

export function WatchThesisChange() {
  const [step, setStep] = useState(0);
  const [playing, setPlaying] = useState(true);

  useEffect(() => {
    if (!playing) return;
    const id = setInterval(() => {
      setStep((s) => {
        if (s >= STEPS.length - 1) {
          setTimeout(() => setStep(0), 2200);
          return s;
        }
        return s + 1;
      });
    }, 1500);
    return () => clearInterval(id);
  }, [playing]);

  const status = statusForStep(step);
  const isAlert = STEPS[step].kind === "alert" || STEPS[step].kind === "mail";

  return (
    <div
      style={{
        background: mk.card,
        borderRadius: 18,
        border: `1px solid ${mk.pencilLight}`,
        padding: "clamp(20px,3vw,32px)",
        display: "flex",
        flexDirection: "column",
        gap: 18,
        boxShadow: "0 30px 80px -50px rgba(0,0,0,0.3)",
        fontFamily: mk.sans,
      }}
    >
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap" }}>
        <div
          style={{
            width: 44,
            height: 44,
            borderRadius: 10,
            background: mk.cardSoft,
            border: `1.4px solid ${mk.pencilLight}`,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontFamily: mk.sans,
            fontWeight: 600,
            fontSize: 18,
            letterSpacing: "-0.02em",
            flex: "0 0 44px",
          }}
        >
          T
        </div>
        <div>
          <div style={{ fontFamily: mk.sans, fontSize: 22, fontWeight: 600, letterSpacing: "-0.015em", lineHeight: 1.1 }}>
            TSLA · Tesla
          </div>
          <div style={{ fontFamily: mk.mono, fontSize: 11, color: mk.pencil, letterSpacing: "0.06em", marginTop: 2 }}>
            Bought Mar 2024 · {STEPS[step].date}, 2024
          </div>
        </div>
        <span
          style={{
            marginLeft: "auto",
            padding: "5px 12px",
            borderRadius: 999,
            background: status.bg,
            color: status.fg,
            fontFamily: mk.mono,
            fontSize: 11,
            fontWeight: 600,
            letterSpacing: "0.04em",
            whiteSpace: "nowrap",
            transition: "all 400ms ease",
          }}
        >
          {status.label}
        </span>
      </div>

      {/* Thesis bubble */}
      <div
        style={{
          background: mk.cardSoft,
          border: `1px dashed ${mk.pencilLight}`,
          borderRadius: 12,
          padding: "14px 16px",
          display: "flex",
          flexDirection: "column",
          gap: 6,
        }}
      >
        <div style={{ fontFamily: mk.mono, fontSize: 10, letterSpacing: "0.1em", textTransform: "uppercase", color: mk.pencil }}>
          What you wrote · Mar 12
        </div>
        <div style={{ fontFamily: mk.sans, fontSize: 17, lineHeight: 1.4, color: mk.ink, fontStyle: "italic" }}>
          &ldquo;EV growth + robotaxi optionality nobody is pricing.&rdquo;
        </div>
      </div>

      {/* Timeline rail */}
      <div style={{ position: "relative", height: 56, marginTop: 4 }}>
        <div
          style={{
            position: "absolute",
            top: 16,
            left: 0,
            right: 0,
            height: 2,
            background: mk.pencilLight,
            borderRadius: 1,
          }}
        />
        <div
          style={{
            position: "absolute",
            top: 16,
            left: 0,
            height: 2,
            width: `${(step / (STEPS.length - 1)) * 100}%`,
            background: step < 3 ? mk.green : step < 5 ? mk.pencil : mk.accent,
            borderRadius: 1,
            transition: "all 700ms cubic-bezier(.4,0,.2,1), background 400ms ease",
          }}
        />
        {STEPS.map((e, i) => {
          const passed = i <= step;
          const dotAlert = e.kind === "alert" || e.kind === "mail";
          const dotColor = !passed ? mk.pencilLight : dotAlert ? mk.accent : e.kind === "up" ? mk.green : mk.pencil;
          return (
            <div
              key={i}
              onClick={() => { setPlaying(false); setStep(i); }}
              style={{
                position: "absolute",
                left: `${(i / (STEPS.length - 1)) * 100}%`,
                top: 8,
                transform: "translateX(-50%)",
                cursor: "pointer",
              }}
            >
              <div
                style={{
                  width: i === step ? 18 : 12,
                  height: i === step ? 18 : 12,
                  borderRadius: 999,
                  background: dotColor,
                  border: `2px solid ${mk.card}`,
                  boxShadow: i === step ? `0 0 0 6px ${dotColor}33` : "none",
                  transition: "all 350ms ease",
                  marginTop: i === step ? 0 : 3,
                }}
              />
              <div
                style={{
                  position: "absolute",
                  top: 24,
                  left: "50%",
                  transform: "translateX(-50%)",
                  fontFamily: mk.mono,
                  fontSize: 10,
                  letterSpacing: "0.04em",
                  color: passed ? mk.ink : mk.pencil,
                  whiteSpace: "nowrap",
                  textAlign: "center",
                }}
                className="hidden sm:block"
              >
                {e.date}
              </div>
            </div>
          );
        })}
      </div>

      {/* Controls */}
      <div style={{ display: "flex", gap: 12, alignItems: "flex-start" }}>
        <button
          onClick={() => setPlaying((p) => !p)}
          style={{
            width: 38,
            height: 38,
            borderRadius: 999,
            background: mk.ink,
            color: mk.paper,
            border: "none",
            fontSize: 13,
            cursor: "pointer",
            flex: "0 0 38px",
          }}
          aria-label={playing ? "Pause" : "Play"}
        >
          {playing ? "⏸" : "▶"}
        </button>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontFamily: mk.mono, fontSize: 10, letterSpacing: "0.1em", textTransform: "uppercase", color: mk.pencil, marginBottom: 2 }}>
            {STEPS[step].date} · {STEPS[step].label}
          </div>
          <div
            key={step}
            style={{
              fontFamily: mk.sans,
              fontSize: "clamp(16px,2vw,19px)",
              fontWeight: 500,
              lineHeight: 1.3,
              letterSpacing: "-0.01em",
              color: isAlert ? mk.accent : mk.ink,
              animation: "mkFadeIn 300ms ease-out",
            }}
          >
            {STEPS[step].text}
          </div>
        </div>
      </div>

      {/* Alert email mock */}
      {step >= STEPS.length - 1 && (
        <div
          style={{
            background: mk.ink,
            color: mk.paper,
            borderRadius: 12,
            padding: "16px 18px",
            display: "flex",
            flexDirection: "column",
            gap: 10,
            animation: "mkSlideIn 480ms ease-out",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              fontFamily: mk.mono,
              fontSize: 10,
              letterSpacing: "0.08em",
              textTransform: "uppercase",
              color: "#aaa",
            }}
          >
            <span>From: penKeep</span>
            <span>Oct 23, 14:02</span>
          </div>
          <div style={{ fontFamily: mk.sans, fontSize: "clamp(17px,2vw,21px)", fontWeight: 600, lineHeight: 1.2, letterSpacing: "-0.015em" }}>
            Your reason for owning <span style={{ color: mk.accent }}>Tesla</span> may have moved.
          </div>
          <div style={{ fontSize: 13, color: "#bbb", lineHeight: 1.5 }}>
            You said you bought for <em>&ldquo;EV growth + robotaxi optionality.&rdquo;</em> Both got dinged this week:
            Q3 deliveries -8.4%, and the robotaxi event was called &ldquo;underwhelming&rdquo; by most of the analysts you follow.
          </div>
          <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
            <button
              style={{
                padding: "7px 13px",
                background: mk.accent,
                color: mk.paper,
                border: "none",
                borderRadius: 6,
                fontFamily: mk.sans,
                fontSize: 12,
                fontWeight: 500,
                cursor: "pointer",
              }}
            >
              Open thesis →
            </button>
            <button
              style={{
                padding: "7px 13px",
                background: "transparent",
                color: mk.paper,
                border: `1px solid ${mk.paper}40`,
                borderRadius: 6,
                fontFamily: mk.sans,
                fontSize: 12,
                cursor: "pointer",
              }}
            >
              I still believe
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
