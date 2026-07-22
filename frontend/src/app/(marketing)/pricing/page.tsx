import Link from "next/link";
import { FoundingForm } from "../../_mkt/founding-form";
import { mk } from "../../_mkt/tokens";

const FREE_FEATURES = [
  {
    label: "Up to 5 active theses",
    info: "Keep five positions under active review at once. A thesis records why you own a position, what must remain true, and what would break the case.",
  },
  {
    label: "A structured record of your reasoning and decisions",
    info: "The original case, the evidence that later tested it, and the decision you made are kept together instead of scattered across notes and alerts.",
  },
  {
    label: "Core evidence: earnings, filings, news, insider transactions",
    info: "penKeep checks these public sources against the conditions in your written case. Evidence that does not touch your case stays out of the decision inbox.",
  },
  {
    label: "Thesis health score (Healthy / At Risk / Broken)",
    info: "A summary of how the evidence is affecting your written case. It is a prompt to review your reasoning, not a buy or sell signal.",
  },
  {
    label: "Weekly digest email",
    info: "A Sunday email summarises the new evidence checked that week and points out anything that needs your attention.",
  },
  {
    label: "12 months of decision history",
    info: "Look back over a year of written cases, evidence, decisions, and follow-up reviews.",
  },
];

const PREMIUM_FEATURES = [
  {
    label: "Unlimited theses",
    info: "Keep every position under active review without the five-thesis limit.",
  },
  {
    label: "Broker connection (Trading 212 + more)",
    info: "Import positions through a read-only connection where supported. penKeep cannot place or change trades.",
  },
  {
    label: "Counter-thesis assistant",
    info: "Pressure-test the positive case by surfacing credible risks, missing assumptions, and measurable conditions worth watching.",
  },
  {
    label: "Full decision history, unlimited",
    info: "Keep the complete record of each written case, evidence review, decision, and outcome for as long as the account remains active.",
  },
  {
    label: "Decision follow-through: what happened after your call",
    info: "Return to an earlier hold, reduce, add, or exit decision and record whether the outcome matched the reasoning behind it.",
  },
  {
    label: "Pre-earnings nudges and post-earnings review",
    info: "Re-read the case before results, then compare the reported evidence with what you expected after the release.",
  },
  {
    label: "Quarterly decision-pattern review",
    info: "A periodic review of repeated habits across your decisions, such as moving a break condition or dismissing the same kind of warning.",
  },
  {
    label: "Everything in Free",
    info: "Includes the free record, monitoring, weekly digest, and twelve-month history, with the premium limits and tools added.",
  },
];

const SHARED_PROMISES = [
  {
    eyebrow: "No recommendations",
    title: "No tier gives buy or sell calls.",
    body: "penKeep preserves the context and challenges the reasoning. The decision remains yours.",
  },
  {
    eyebrow: "Full history",
    title: "Keep the earlier notes.",
    body: "See what you wrote, what changed, and what you decided afterward.",
  },
  {
    eyebrow: "Your data",
    title: "Your notes stay yours.",
    body: "The product still acts like a decision record, not a social feed or recommendation engine.",
  },
];

function Check({ premium }: { premium?: boolean }) {
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        width: 20,
        height: 20,
        borderRadius: 999,
        background: premium ? mk.accent : mk.greenSoft,
        color: premium ? mk.paper : mk.green,
        fontSize: 11,
        fontWeight: 700,
        flex: "0 0 20px",
      }}
    >
      ✓
    </span>
  );
}

function FeatureInfo({ label, text, premium }: { label: string; text: string; premium?: boolean }) {
  return (
    <details className="pk-feature-info" style={{ position: "relative", flex: "0 0 auto" }}>
      <summary
        aria-label={`Explain ${label}`}
        style={{
          width: 20,
          height: 20,
          borderRadius: 999,
          border: `1px solid ${premium ? "rgba(255,255,255,0.28)" : mk.pencilLight}`,
          color: premium ? "#bdb5ad" : mk.pencil,
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          fontFamily: mk.sans,
          fontSize: 12,
          fontWeight: 600,
          lineHeight: 1,
          cursor: "pointer",
          listStyle: "none",
        }}
      >
        <span aria-hidden="true">i</span>
      </summary>
      <div
        role="note"
        style={{
          position: "absolute",
          zIndex: 20,
          right: 0,
          top: 28,
          width: "min(290px, calc(100vw - 64px))",
          padding: "12px 14px",
          borderRadius: 10,
          border: `1px solid ${premium ? "rgba(255,255,255,0.16)" : mk.pencilLight}`,
          background: premium ? "#292621" : mk.paperHi,
          color: premium ? "#e0dad3" : mk.inkSoft,
          boxShadow: "0 14px 34px rgba(36, 29, 22, 0.16)",
          fontFamily: mk.sans,
          fontSize: 13,
          lineHeight: 1.5,
        }}
      >
        {text}
      </div>
    </details>
  );
}

export default function PricingPage() {
  const pad = "clamp(22px, 4.5vw, 56px)";
  return (
    <>
      <style>{`.pk-feature-info > summary::-webkit-details-marker { display: none; }`}</style>
      {/* Header */}
      <section style={{ padding: `clamp(50px,8vw,110px) ${pad} clamp(32px,4vw,60px)` }}>
        <div style={{ fontFamily: mk.mono, fontSize: 11, letterSpacing: "0.14em", textTransform: "uppercase", color: mk.pencil, marginBottom: 14 }}>
          Pricing
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
          Start the record free.<br />
          <span style={{ color: mk.accent }}>Keep the whole history.</span>
        </h1>
        <p style={{ fontFamily: mk.sans, fontSize: "clamp(17px,1.8vw,19px)", lineHeight: 1.55, color: mk.pencil, marginTop: "clamp(18px,2vw,24px)", maxWidth: 600 }}>
          Start with the free account. Founding membership adds unlimited positions, full history,
          and follow-up reviews. The annual rate stays the same while you remain a member.
        </p>

        <div
          style={{
            gap: 12,
            marginTop: "clamp(24px,3vw,32px)",
            maxWidth: 860,
          }}
          className="grid grid-cols-1 md:grid-cols-3"
        >
          {[
            ["Start", "Record up to 5 active theses free"],
            ["Build", "Evidence and decisions stay connected"],
            ["Review", "Look back at what you wrote and decided"],
          ].map(([label, value]) => (
            <div
              key={label}
              style={{
                border: `1px solid ${mk.pencilLight}`,
                borderRadius: 16,
                background: mk.card,
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

      {/* Tier cards */}
      <section style={{ padding: `0 ${pad} clamp(60px,8vw,100px)` }}>
        <div
          style={{
            gap: 16,
            maxWidth: 900,
          }}
          className="grid grid-cols-1 md:grid-cols-2"
        >
          {/* Free */}
          <div
            style={{
              background: mk.card,
              border: `1px solid ${mk.pencilLight}`,
              borderRadius: 20,
              padding: "clamp(24px,3vw,36px)",
              display: "flex",
              flexDirection: "column",
              gap: 20,
            }}
          >
            <div>
              <div style={{ fontFamily: mk.mono, fontSize: 11, letterSpacing: "0.14em", textTransform: "uppercase", color: mk.pencil, marginBottom: 10 }}>
                Free
              </div>
              <div style={{ fontFamily: mk.sans, fontSize: "clamp(36px,5vw,52px)", fontWeight: 600, letterSpacing: "-0.03em", lineHeight: 1 }}>
                £0
              </div>
              <div style={{ fontFamily: mk.sans, fontSize: 14, color: mk.pencil, marginTop: 6 }}>
                Free now. No catch.
              </div>
            </div>

            <div
              style={{
                background: mk.cardSoft,
                border: `1px solid ${mk.pencilLight}`,
                borderRadius: 14,
                padding: "14px 16px",
              }}
            >
              <div style={{ fontFamily: mk.mono, fontSize: 10, letterSpacing: "0.14em", textTransform: "uppercase", color: mk.pencil }}>
                Best for
              </div>
              <div style={{ fontFamily: mk.sans, fontSize: 15, lineHeight: 1.45, color: mk.inkSoft, marginTop: 8 }}>
                Putting real decisions on record and seeing whether the review loop changes how you respond to new evidence.
              </div>
            </div>

            <div style={{ height: 1, background: mk.pencilLight }} />

            <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: 12 }}>
              {FREE_FEATURES.map((feature) => (
                <li key={feature.label} style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
                  <Check />
                  <span style={{ flex: 1, fontFamily: mk.sans, fontSize: 15, color: mk.inkSoft, lineHeight: 1.45 }}>
                    {feature.label}
                  </span>
                  <FeatureInfo label={feature.label} text={feature.info} />
                </li>
              ))}
            </ul>

            <div style={{ marginTop: "auto", paddingTop: 8 }}>
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                <Link
                  href="/register"
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    justifyContent: "center",
                    padding: "14px 18px",
                    borderRadius: 999,
                    background: mk.ink,
                    color: mk.paper,
                    fontFamily: mk.sans,
                    fontSize: 15,
                    fontWeight: 500,
                    textDecoration: "none",
                    whiteSpace: "nowrap",
                  }}
                >
                  Create free account →
                </Link>
                <div
                  style={{
                    fontFamily: mk.mono,
                    fontSize: 11,
                    color: mk.pencil,
                    letterSpacing: "0.03em",
                    textAlign: "center",
                  }}
                >
                  No card · up to 5 active theses
                </div>
              </div>
            </div>
          </div>

          {/* Premium */}
          <div
            style={{
              background: mk.ink,
              color: mk.paper,
              border: `1px solid ${mk.ink}`,
              borderRadius: 20,
              padding: "clamp(24px,3vw,36px)",
              display: "flex",
              flexDirection: "column",
              gap: 20,
            }}
          >
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
                <div style={{ fontFamily: mk.mono, fontSize: 11, letterSpacing: "0.14em", textTransform: "uppercase", color: "#999" }}>
                  Founding Membership
                </div>
                <span
                  style={{
                    padding: "3px 9px",
                    borderRadius: 999,
                    background: mk.accentSoft,
                    color: mk.accent,
                    fontFamily: mk.mono,
                    fontSize: 10,
                    fontWeight: 600,
                    letterSpacing: "0.06em",
                  }}
                >
                  LIMITED SEATS
                </span>
              </div>
              <div style={{ fontFamily: mk.sans, fontSize: "clamp(36px,5vw,52px)", fontWeight: 600, letterSpacing: "-0.03em", lineHeight: 1 }}>
                £99/year
              </div>
              <div style={{ fontFamily: mk.sans, fontSize: 14, color: "#aaa", marginTop: 6 }}>
                Founding rate, locked while active.
              </div>
            </div>

            <div
              style={{
                background: "rgba(255,255,255,0.04)",
                border: "1px solid rgba(255,255,255,0.1)",
                borderRadius: 14,
                padding: "14px 16px",
              }}
            >
              <div style={{ fontFamily: mk.mono, fontSize: 10, letterSpacing: "0.14em", textTransform: "uppercase", color: "#999" }}>
                Best for
              </div>
              <div style={{ fontFamily: mk.sans, fontSize: 15, lineHeight: 1.45, color: "#d3cdc6", marginTop: 8 }}>
                Investors who want a permanent, searchable record of what they believed, decided, and learned.
              </div>
            </div>

            <div style={{ height: 1, background: "rgba(255,255,255,0.12)" }} />

            <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: 12 }}>
              {PREMIUM_FEATURES.map((feature) => (
                <li key={feature.label} style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
                  <Check premium />
                  <span style={{ flex: 1, fontFamily: mk.sans, fontSize: 15, color: "#ccc", lineHeight: 1.45 }}>
                    {feature.label}
                  </span>
                  <FeatureInfo label={feature.label} text={feature.info} premium />
                </li>
              ))}
            </ul>

            <div style={{ marginTop: "auto", paddingTop: 8 }}>
              <FoundingForm dark />
            </div>
          </div>
        </div>
      </section>

      <section style={{ padding: `0 ${pad} clamp(60px,8vw,100px)` }}>
        <div style={{ marginBottom: 22 }}>
          <div style={{ fontFamily: mk.mono, fontSize: 11, letterSpacing: "0.14em", textTransform: "uppercase", color: mk.pencil, marginBottom: 10 }}>
            Shared promise
          </div>
          <h2
            style={{
              fontFamily: mk.sans,
              fontSize: "clamp(28px,3.5vw,42px)",
              fontWeight: 600,
              lineHeight: 1.05,
              letterSpacing: "-0.025em",
              margin: 0,
              color: mk.ink,
            }}
          >
            Pay for more positions and history. The decisions stay yours.
          </h2>
        </div>

        <div
          style={{
            gap: 14,
            maxWidth: 980,
          }}
          className="grid grid-cols-1 md:grid-cols-3"
        >
          {SHARED_PROMISES.map((item) => (
            <div
              key={item.title}
              style={{
                background: mk.card,
                border: `1px solid ${mk.pencilLight}`,
                borderRadius: 18,
                padding: "20px 20px 22px",
              }}
            >
              <div style={{ fontFamily: mk.mono, fontSize: 10, letterSpacing: "0.14em", textTransform: "uppercase", color: mk.accent }}>
                {item.eyebrow}
              </div>
              <div
                style={{
                  fontFamily: mk.sans,
                  fontSize: 22,
                  fontWeight: 600,
                  lineHeight: 1.15,
                  letterSpacing: "-0.02em",
                  color: mk.ink,
                  marginTop: 10,
                }}
              >
                {item.title}
              </div>
              <div style={{ fontFamily: mk.sans, fontSize: 15, lineHeight: 1.55, color: mk.pencil, marginTop: 10 }}>
                {item.body}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Not advice strip */}
      <section
        style={{
          padding: `clamp(36px,5vw,60px) ${pad}`,
          background: mk.cardSoft,
          borderTop: `1px solid ${mk.pencilLight}`,
          borderBottom: `1px solid ${mk.pencilLight}`,
          display: "flex",
          flexDirection: "column",
          gap: 10,
        }}
      >
        <div style={{ fontFamily: mk.mono, fontSize: 11, letterSpacing: "0.14em", textTransform: "uppercase", color: mk.pencil }}>
          A note on what we are
        </div>
        <p style={{ fontFamily: mk.sans, fontSize: "clamp(16px,1.8vw,19px)", lineHeight: 1.6, color: mk.inkSoft, maxWidth: 720, margin: 0 }}>
          penKeep is a research and journaling tool, not an investment advisor or broker-dealer.
          No tier, free or premium, gives you buy or sell recommendations.
          Thesis health scores are a prompt to re-read what you wrote, not an instruction to act.
        </p>
      </section>

      {/* FAQ callout */}
      <section style={{ padding: `clamp(50px,7vw,90px) ${pad}`, textAlign: "center" }}>
        <h2 style={{ fontFamily: mk.sans, fontSize: "clamp(28px,3.5vw,44px)", fontWeight: 600, letterSpacing: "-0.025em", margin: "0 0 14px" }}>
          Still have questions?
        </h2>
        <p style={{ fontFamily: mk.sans, fontSize: "clamp(15px,1.6vw,17px)", color: mk.pencil, margin: "0 0 24px" }}>
          The FAQ covers signals, broker connections, data, and more.
        </p>
        <a
          href="/faq"
          style={{
            display: "inline-block",
            padding: "12px 28px",
            background: mk.ink,
            color: mk.paper,
            borderRadius: 999,
            fontFamily: mk.sans,
            fontWeight: 500,
            fontSize: 15,
            textDecoration: "none",
          }}
        >
          Read the FAQ →
        </a>
      </section>
    </>
  );
}
