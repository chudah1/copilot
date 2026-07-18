import { ImageResponse } from "next/og";

export const socialImageSize = {
  width: 1200,
  height: 630,
};

function PenKeepMark() {
  return (
    <svg viewBox="0 0 32 36" width="42" height="47" fill="none">
      <path
        d="M3 36V14Q3 3 16 3t13 11v22Z"
        stroke="#1E5C3A"
        strokeWidth="2"
        strokeLinejoin="round"
      />
      <path d="m16 9 3.5 11-3.5 4-3.5-4Z" fill="#1E5C3A" />
      <line x1="16" y1="15" x2="16" y2="24" stroke="#ECE7DB" strokeWidth="1" />
      <circle cx="16" cy="24" r="1" fill="#1E5C3A" />
    </svg>
  );
}

export function renderSocialCard() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          background: "#ECE7DB",
          color: "#161510",
          padding: "54px 64px 46px",
          borderTop: "12px solid #1E5C3A",
          fontFamily: "Arial, sans-serif",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <PenKeepMark />
          <div style={{ display: "flex", alignItems: "baseline", gap: 18 }}>
            <span style={{ fontSize: 33, fontWeight: 700, letterSpacing: "-0.04em" }}>penKeep</span>
            <span
              style={{
                fontSize: 14,
                color: "#726C60",
                letterSpacing: "0.18em",
                textTransform: "uppercase",
              }}
            >
              Decision memory for investors
            </span>
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", maxWidth: 1000 }}>
          <div
            style={{
              display: "flex",
              fontFamily: "Georgia, serif",
              fontSize: 67,
              lineHeight: 1.03,
              letterSpacing: "-0.045em",
            }}
          >
            Your broker records the trade.
          </div>
          <div
            style={{
              display: "flex",
              color: "#1E5C3A",
              fontFamily: "Georgia, serif",
              fontSize: 67,
              fontStyle: "italic",
              lineHeight: 1.03,
              letterSpacing: "-0.045em",
            }}
          >
            penKeep remembers the decision.
          </div>
          <div
            style={{
              display: "flex",
              marginTop: 30,
              maxWidth: 830,
              color: "#3A3833",
              fontSize: 24,
              lineHeight: 1.4,
            }}
          >
            Write down why you bought. See those notes again when something important changes.
          </div>
        </div>

        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            paddingTop: 22,
            borderTop: "1px solid #D2CBBB",
            color: "#726C60",
            fontSize: 16,
          }}
        >
          <span style={{ color: "#1E5C3A", fontWeight: 700 }}>penkeep.io</span>
          <span>Private · read-only tracking · not financial advice</span>
        </div>
      </div>
    ),
    socialImageSize,
  );
}
