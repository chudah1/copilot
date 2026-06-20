import { mk } from "../../_mkt/tokens";

const TOP_POINTS = [
  ["Read-only by design", "Broker links can read positions, never place trades."],
  ["Notes stay scoped", "Your thesis notes are kept to your account and not sold."],
  ["Human response", "Security and privacy requests go to real people, not a black hole."],
];

const SECURITY_PROMISES = [
  {
    eyebrow: "Product design",
    title: "We do not need your trade history to do the job.",
    body: "penKeep is built around why you own something now, not around storing every historical transaction you ever made.",
  },
  {
    eyebrow: "Incentives",
    title: "We never act on the positions we can see.",
    body: "The product exists to help you think more clearly, not to turn your account into an execution surface.",
  },
  {
    eyebrow: "Failure mode",
    title: "If we make a mistake, we tell you plainly.",
    body: "Security trust is not just prevention. It is also how directly and quickly a team responds when something goes wrong.",
  },
];

export default function SecurityPage() {
  const pad = "clamp(22px, 4.5vw, 56px)";
  return (
    <>
      {/* Header */}
      <section style={{ padding: `clamp(50px,8vw,110px) ${pad} clamp(32px,4vw,60px)` }}>
        <div style={{ fontFamily: mk.mono, fontSize: 11, letterSpacing: "0.14em", textTransform: "uppercase", color: mk.pencil, marginBottom: 14 }}>
          Security &amp; privacy
        </div>
        <h1
          style={{
            fontFamily: mk.sans,
            fontWeight: 600,
            fontSize: "clamp(44px,7vw,88px)",
            lineHeight: 1,
            letterSpacing: "-0.035em",
            margin: 0,
          }}
        >
          Your reasons<br />stay your reasons.
        </h1>
        <p style={{ fontFamily: mk.sans, fontSize: "clamp(17px,1.8vw,20px)", lineHeight: 1.55, color: mk.pencil, marginTop: "clamp(18px,2vw,28px)", maxWidth: 680 }}>
          We&apos;ve built penKeep around one promise: we know what you own, but we never act on it.
          Below is what that means in practice.
        </p>

        <div
          style={{
            gap: 12,
            marginTop: "clamp(24px,3vw,32px)",
            maxWidth: 980,
          }}
          className="grid grid-cols-1 md:grid-cols-3"
        >
          {TOP_POINTS.map(([label, value]) => (
            <div
              key={label}
              style={{
                background: mk.card,
                border: `1px solid ${mk.pencilLight}`,
                borderRadius: 16,
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

      {/* What we store / don't */}
      <section
        style={{
          padding: `clamp(40px,6vw,70px) ${pad}`,
          background: mk.cardSoft,
          borderTop: `1px solid ${mk.pencilLight}`,
          borderBottom: `1px solid ${mk.pencilLight}`,
        }}
      >
        <div style={{ gap: "clamp(28px,5vw,60px)" }} className="grid grid-cols-1 md:grid-cols-2">
          <div>
            <div style={{ fontFamily: mk.mono, fontSize: 11, letterSpacing: "0.14em", textTransform: "uppercase", color: mk.green, marginBottom: 14 }}>
              ✓ What we store
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              {[
                ["Your thesis notes", "Encrypted at rest. Scoped to your account. Never read for ads or training without your explicit opt-in."],
                ["Your tickers and rough sizing", "Used to decide which signals are relevant to you."],
                ["Your alert preferences", "Tone, delivery, quiet hours."],
                ["Email + sign-in", "Standard email and password auth with JWT sessions."],
              ].map(([h, b]) => (
                <div key={h}>
                  <div style={{ fontFamily: mk.sans, fontSize: 17, fontWeight: 600, letterSpacing: "-0.01em" }}>{h}</div>
                  <div style={{ fontFamily: mk.sans, fontSize: 14, lineHeight: 1.55, color: mk.pencil, marginTop: 4 }}>{b}</div>
                </div>
              ))}
            </div>
          </div>
          <div>
            <div style={{ fontFamily: mk.mono, fontSize: 11, letterSpacing: "0.14em", textTransform: "uppercase", color: mk.accent, marginBottom: 14 }}>
              ✕ What we don&apos;t
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              {[
                ["Your trade history", "We don't ingest it. You don't need to share it. The broker connection only reads positions, not transactions."],
                ["Payment / banking info", "We never see it. Billing for any future premium tier will be handled by a third-party processor."],
                ["Your real-time positions for trading", "We poll positions on a schedule. We don't subscribe to a tick stream, because we don't need one."],
                ["Sharing with third parties", "We don't sell or share your thesis notes. Period."],
              ].map(([h, b]) => (
                <div key={h}>
                  <div style={{ fontFamily: mk.sans, fontSize: 17, fontWeight: 600, letterSpacing: "-0.01em" }}>{h}</div>
                  <div style={{ fontFamily: mk.sans, fontSize: 14, lineHeight: 1.55, color: mk.pencil, marginTop: 4 }}>{b}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section style={{ padding: `clamp(50px,8vw,90px) ${pad}` }}>
        <div style={{ marginBottom: 22 }}>
          <div style={{ fontFamily: mk.mono, fontSize: 11, letterSpacing: "0.14em", textTransform: "uppercase", color: mk.pencil, marginBottom: 10 }}>
            How we think about trust
          </div>
          <h2 style={{ fontFamily: mk.sans, fontSize: "clamp(30px,4vw,46px)", fontWeight: 600, margin: 0, lineHeight: 1.05, letterSpacing: "-0.025em", maxWidth: 760 }}>
            The security model follows the product model.
          </h2>
        </div>

        <div
          style={{ gap: 14 }}
          className="grid grid-cols-1 md:grid-cols-3"
        >
          {SECURITY_PROMISES.map((item) => (
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
              <div style={{ fontFamily: mk.sans, fontSize: 21, fontWeight: 600, lineHeight: 1.15, letterSpacing: "-0.02em", color: mk.ink, marginTop: 10 }}>
                {item.title}
              </div>
              <div style={{ fontFamily: mk.sans, fontSize: 15, lineHeight: 1.55, color: mk.pencil, marginTop: 10 }}>
                {item.body}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Technical details */}
      <section style={{ padding: `clamp(50px,8vw,90px) ${pad}` }}>
        <div style={{ fontFamily: mk.mono, fontSize: 11, letterSpacing: "0.14em", textTransform: "uppercase", color: mk.pencil, marginBottom: 14 }}>
          The details
        </div>
        <h2 style={{ fontFamily: mk.sans, fontSize: "clamp(32px,4vw,48px)", fontWeight: 600, margin: 0, lineHeight: 1.05, letterSpacing: "-0.025em" }}>
          What&apos;s under the hood.
        </h2>
        <p style={{ fontFamily: mk.sans, fontSize: 16, lineHeight: 1.6, color: mk.pencil, margin: "14px 0 0", maxWidth: 700 }}>
          This is the practical layer: how credentials, hosting, access, and disclosure are handled around the core product.
        </p>
        <div
          style={{ gap: 14, marginTop: "clamp(28px,3vw,40px)" }}
          className="grid grid-cols-1 md:grid-cols-2"
        >
          {[
            ["Encryption", "Broker API keys encrypted at rest (Fernet AES). TLS in transit."],
            ["Hosting", "Railway cloud hosting. Database backups managed by the platform."],
            ["Access controls", "We keep engineer access to production data minimal."],
            ["Vulnerability program", "Responsible disclosure at security@penkeep.io."],
            ["Dependencies", "Minimal dependency surface area."],
          ].map(([h, b]) => (
            <div key={h} style={{ background: mk.card, border: `1px solid ${mk.pencilLight}`, borderRadius: 14, padding: 20 }}>
              <div style={{ fontFamily: mk.sans, fontSize: 18, fontWeight: 600, letterSpacing: "-0.01em" }}>{h}</div>
              <div style={{ fontFamily: mk.sans, fontSize: 14, lineHeight: 1.55, color: mk.pencil, marginTop: 6 }}>{b}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Rights */}
      <section
        style={{
          padding: `clamp(40px,6vw,70px) ${pad}`,
          background: mk.cardSoft,
          borderTop: `1px solid ${mk.pencilLight}`,
          borderBottom: `1px solid ${mk.pencilLight}`,
        }}
      >
        <div style={{ fontFamily: mk.mono, fontSize: 11, letterSpacing: "0.14em", textTransform: "uppercase", color: mk.pencil, marginBottom: 14 }}>
          Your rights
        </div>
        <h2 style={{ fontFamily: mk.sans, fontSize: "clamp(28px,4vw,40px)", fontWeight: 600, margin: 0, lineHeight: 1.1, letterSpacing: "-0.02em", maxWidth: 800 }}>
          Export everything. Delete anything. <span style={{ color: mk.accent }}>It&apos;s yours.</span>
        </h2>
        <div
          style={{ gap: 12, marginTop: "clamp(24px,3vw,36px)" }}
          className="grid grid-cols-1 md:grid-cols-3"
        >
          {[
            ["Export", "We're building export to Markdown and JSON. Contact us if you need your data before that ships."],
            ["Delete", "Email privacy@penkeep.io to delete your account and data. We'll confirm within 7 days."],
            ["Subject-access requests", "Email privacy@penkeep.io and we reply within 14 days, free."],
          ].map(([h, b]) => (
            <div key={h} style={{ background: mk.card, border: `1px solid ${mk.pencilLight}`, borderRadius: 14, padding: 18 }}>
              <div style={{ fontFamily: mk.sans, fontSize: 17, fontWeight: 600 }}>{h}</div>
              <div style={{ fontFamily: mk.sans, fontSize: 13.5, lineHeight: 1.55, color: mk.pencil, marginTop: 6 }}>{b}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Footnote */}
      <section style={{ padding: `clamp(50px,8vw,90px) ${pad}` }}>
        <div
          style={{
            background: mk.card,
            border: `1px solid ${mk.pencilLight}`,
            borderRadius: 18,
            padding: "22px 22px 24px",
            maxWidth: 860,
          }}
        >
          <div style={{ fontFamily: mk.mono, fontSize: 11, letterSpacing: "0.14em", textTransform: "uppercase", color: mk.pencil, marginBottom: 12 }}>
            Incident posture
          </div>
          <p style={{ fontFamily: mk.sans, fontStyle: "italic", color: mk.pencil, fontSize: "clamp(15px,1.8vw,18px)", lineHeight: 1.6, maxWidth: 720, margin: 0 }}>
            We are a small team. We will make mistakes. When we do, we will tell you, fix them, and write
            publicly about what we learned. That&apos;s the deal.
          </p>
          <div style={{ marginTop: 18, fontFamily: mk.mono, fontSize: 11, color: mk.pencil, letterSpacing: "0.08em" }}>
            Security questions → <span style={{ color: mk.ink }}>security@penkeep.io</span>
          </div>
        </div>
      </section>
    </>
  );
}
