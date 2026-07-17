"use client";

import { useState, useEffect, useRef } from "react";
import { mk } from "./tokens";
import { Sparkline } from "./sparkline";

const STARTERS = [
  {
    id: "NVDA",
    name: "NVIDIA",
    text: "AI infra is the next decade. NVDA is picks-and-shovels — Jensen is generational.",
    tags: ["AI infra", "Founder bet"],
    health: { label: "Healthy", score: 84 } as const,
    signals: [
      { i: "↑", t: "Hyperscaler capex guides ↑", trend: "up" },
      { i: "·", t: "NVDA data-center revenue", trend: "up" },
      { i: "·", t: "Jensen earnings-call tone", trend: "flat" },
    ],
  },
  {
    id: "TSLA",
    name: "Tesla",
    text: "Tesla is an EV story plus robotaxi optionality nobody is pricing.",
    tags: ["EV cycle", "Founder bet"],
    health: { label: "At Risk", score: 54 } as const,
    signals: [
      { i: "·", t: "Quarterly EV deliveries", trend: "bumpy" },
      { i: "·", t: "Robotaxi / FSD milestones", trend: "flat" },
      { i: "·", t: "Auto gross margin", trend: "down" },
    ],
  },
  {
    id: "RR.L",
    name: "Rolls-Royce",
    text: "Civil aero turnaround + defence backlog. 18-month horizon.",
    tags: ["Turnaround", "Defence + aero"],
    health: { label: "Healthy", score: 78 } as const,
    signals: [
      { i: "·", t: "Civil-aero margin trajectory", trend: "up" },
      { i: "·", t: "Defence order book", trend: "up" },
      { i: "·", t: "CFO commentary", trend: "flat" },
    ],
  },
  {
    id: "AAPL",
    name: "Apple",
    text: "Apple is a cash machine compounding through Services. A low-vol hold.",
    tags: ["Services flywheel"],
    health: { label: "Healthy", score: 76 } as const,
    signals: [
      { i: "↑", t: "Services revenue growth", trend: "up" },
      { i: "·", t: "Installed base / churn", trend: "flat" },
      { i: "·", t: "iPhone unit trajectory", trend: "flat" },
    ],
  },
] as const;

export function ThesisDemo() {
  const [pickedId, setPickedId] = useState<string>("NVDA");
  const [auto, setAuto] = useState(true);
  const [val, setVal] = useState<string>(STARTERS[0].text);
  const taRef = useRef<HTMLTextAreaElement>(null);

  const picked = STARTERS.find((s) => s.id === pickedId) ?? STARTERS[0];

  useEffect(() => {
    if (!auto) return;
    const id = setInterval(() => {
      setPickedId((prev) => {
        const i = STARTERS.findIndex((s) => s.id === prev);
        const next = STARTERS[(i + 1) % STARTERS.length];
        setVal(next.text);
        return next.id;
      });
    }, 5200);
    return () => clearInterval(id);
  }, [auto]);

  function pick(id: string) {
    setAuto(false);
    const s = STARTERS.find((x) => x.id === id);
    if (s) { setPickedId(id); setVal(s.text); }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14, fontFamily: mk.sans }}>
      {/* Starter chips */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
        <span style={{ fontFamily: mk.mono, fontSize: 11, letterSpacing: "0.12em", textTransform: "uppercase", color: mk.pencil }}>
          Try with →
        </span>
        {STARTERS.map((s) => {
          const active = s.id === pickedId;
          return (
            <button
              key={s.id}
              onClick={() => pick(s.id)}
              style={{
                padding: "6px 12px",
                borderRadius: 999,
                border: `1.4px solid ${active ? mk.ink : mk.pencilLight}`,
                background: active ? mk.ink : mk.card,
                color: active ? mk.paper : mk.ink,
                fontFamily: mk.sans,
                fontSize: 12,
                fontWeight: active ? 600 : 500,
                cursor: "pointer",
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                transition: "all 220ms ease",
              }}
            >
              <span style={{ fontFamily: mk.mono, fontWeight: 600 }}>{s.id}</span>
              <span style={{ color: active ? `${mk.paper}99` : mk.pencil }}>· {s.name}</span>
            </button>
          );
        })}
        {auto && (
          <span
            style={{
              marginLeft: "auto",
              fontFamily: mk.mono,
              fontSize: 11,
              color: mk.accent,
              display: "flex",
              alignItems: "center",
              gap: 6,
            }}
          >
            <span
              style={{
                width: 6,
                height: 6,
                borderRadius: 999,
                background: mk.accent,
                animation: "mkPulse 1.6s ease-in-out infinite",
                display: "inline-block",
              }}
            />
            auto-cycling
          </span>
        )}
      </div>

      {/* Demo card */}
      <div
        style={{
          background: mk.ink,
          borderRadius: 18,
          overflow: "hidden",
          boxShadow: "0 30px 80px -40px rgba(0,0,0,0.4)",
        }}
        className="grid grid-cols-1 sm:grid-cols-[1.05fr_1fr]"
      >
        {/* Input side */}
        <div
          style={{
            padding: "clamp(20px,3vw,28px)",
            background: mk.ink,
            color: mk.paper,
            display: "flex",
            flexDirection: "column",
            gap: 12,
            minHeight: 220,
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              fontFamily: mk.mono,
              fontSize: 11,
              color: "#999",
            }}
          >
            <span style={{ letterSpacing: "0.1em", textTransform: "uppercase" }}>
              Your thesis · {pickedId}
            </span>
            <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <span
                style={{
                  width: 6,
                  height: 6,
                  borderRadius: 999,
                  background: mk.accent,
                  animation: "mkPulse 1.6s ease-in-out infinite",
                  display: "inline-block",
                }}
              />
              live demo
            </span>
          </div>
          <textarea
            key={pickedId}
            ref={taRef}
            value={val}
            onChange={(e) => { setAuto(false); setVal(e.target.value); }}
            rows={4}
            style={{
              width: "100%",
              background: "transparent",
              color: mk.paper,
              border: "none",
              outline: "none",
              resize: "none",
              fontFamily: mk.sans,
              fontSize: "clamp(16px,2vw,21px)",
              lineHeight: 1.4,
              letterSpacing: "-0.01em",
              padding: 0,
              animation: "mkFadeIn 320ms ease-out",
              boxSizing: "border-box",
            }}
          />
          <div style={{ height: 1, background: "#ffffff14", margin: "4px 0" }} />
          <div
            style={{
              fontFamily: mk.mono,
              fontSize: 10,
              letterSpacing: "0.1em",
              textTransform: "uppercase",
              color: "#999",
            }}
          >
            edit me · or pick a starter →
          </div>
        </div>

        {/* Result side */}
        <div
          key={pickedId + "-r"}
          style={{
            padding: "clamp(20px,3vw,28px)",
            background: mk.card,
            display: "flex",
            flexDirection: "column",
            gap: 14,
            animation: "mkFadeIn 320ms ease-out",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10, flexWrap: "wrap" }}>
            <div
              style={{
                fontFamily: mk.mono,
                fontSize: 11,
                letterSpacing: "0.1em",
                textTransform: "uppercase",
                color: mk.pencil,
              }}
            >
              We extracted →
            </div>
            <span
              key={pickedId + "-health"}
              style={{
                padding: "4px 10px",
                borderRadius: 999,
                background: picked.health.label === "Healthy" ? mk.greenSoft : picked.health.label === "At Risk" ? mk.accentSoft : "#fce4d6",
                color: picked.health.label === "Healthy" ? mk.green : mk.accent,
                fontFamily: mk.mono,
                fontSize: 10,
                fontWeight: 600,
                letterSpacing: "0.06em",
                animation: "mkFadeIn 360ms ease-out",
              }}
            >
              {picked.health.label} · {picked.health.score}
            </span>
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6, minHeight: 28 }}>
            {picked.tags.map((t) => (
              <span
                key={t}
                style={{
                  padding: "5px 11px",
                  borderRadius: 999,
                  background: mk.accentSoft,
                  color: mk.accent,
                  border: `1px solid ${mk.accent}`,
                  fontSize: 12,
                  fontWeight: 500,
                  animation: "mkFadeIn 360ms ease-out",
                }}
              >
                {t}
              </span>
            ))}
          </div>
          <div
            style={{
              fontFamily: mk.mono,
              fontSize: 11,
              letterSpacing: "0.1em",
              textTransform: "uppercase",
              color: mk.pencil,
              marginTop: 4,
            }}
          >
            Put it on record →
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {picked.signals.map((s, i) => (
              <div
                key={s.t}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  padding: "8px 10px",
                  background: mk.cardSoft,
                  border: `1px solid ${mk.pencilLight}`,
                  borderRadius: 8,
                  animation: `mkSlideIn 420ms ease-out ${i * 60}ms backwards`,
                }}
              >
                <span
                  style={{
                    width: 18,
                    height: 18,
                    borderRadius: 999,
                    background: s.i === "↑" ? mk.green : mk.pencil,
                    color: mk.paper,
                    display: "inline-flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: 11,
                    fontWeight: 700,
                    flex: "0 0 18px",
                  }}
                >
                  {s.i}
                </span>
                <span style={{ fontSize: 13, color: mk.ink, lineHeight: 1.3, flex: 1 }}>{s.t}</span>
                <Sparkline
                  trend={s.trend}
                  width={48}
                  height={16}
                  color={s.i === "↑" ? mk.green : mk.pencil}
                />
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
