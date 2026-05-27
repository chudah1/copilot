import { mk } from "../../_mkt/tokens";

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
          We&apos;ve built penKeep around one promise — we know what you own, but we never act on it.
          Below is what that means in practice.
        </p>
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
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "clamp(28px,5vw,60px)" }} className="max-md:grid-cols-1">
          <div>
            <div style={{ fontFamily: mk.mono, fontSize: 11, letterSpacing: "0.14em", textTransform: "uppercase", color: mk.green, marginBottom: 14 }}>
              ✓ What we store
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              {[
                ["Your thesis notes", "Encrypted at rest. Scoped to your account. Never read for ads or training without your explicit opt-in."],
                ["Your tickers and rough sizing", "Used to decide which signals are relevant to you."],
                ["Your alert preferences", "Tone, delivery, quiet hours."],
                ["Email + sign-in", "Standard auth. We use a passkey-first flow."],
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
                ["Payment / banking info", "We never see it. Stripe handles checkout when you upgrade."],
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

      {/* Technical details */}
      <section style={{ padding: `clamp(50px,8vw,90px) ${pad}` }}>
        <div style={{ fontFamily: mk.mono, fontSize: 11, letterSpacing: "0.14em", textTransform: "uppercase", color: mk.pencil, marginBottom: 14 }}>
          The details
        </div>
        <h2 style={{ fontFamily: mk.sans, fontSize: "clamp(32px,4vw,48px)", fontWeight: 600, margin: 0, lineHeight: 1.05, letterSpacing: "-0.025em" }}>
          What&apos;s under the hood.
        </h2>
        <div
          style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 14, marginTop: "clamp(28px,3vw,40px)" }}
          className="max-md:grid-cols-1"
        >
          {[
            ["Encryption", "AES-256 at rest. TLS 1.3 in transit. Per-tenant data keys."],
            ["Hosting", "Railway on AWS. EU users default to EU region."],
            ["Backups", "Daily snapshots, 30-day retention, point-in-time restore."],
            ["Access controls", "Engineer access to production data is logged, audited, and requires a written reason."],
            ["Vulnerability program", "Responsible disclosure at security@penkeep.com. Quarterly reviews."],
            ["Dependencies", "Minimal surface area. Dependency audit on every release."],
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
          style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12, marginTop: "clamp(24px,3vw,36px)" }}
          className="max-md:grid-cols-1"
        >
          {[
            ["Export", "Download all your thesis notes as Markdown, or your full history as JSON."],
            ["Delete", "One button in settings. Full account & note deletion, retained only in encrypted backups for 30 days."],
            ["Subject-access requests", "Email privacy@penkeep.com and we reply within 14 days, free."],
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
        <p style={{ fontFamily: mk.sans, fontStyle: "italic", color: mk.pencil, fontSize: "clamp(15px,1.8vw,18px)", lineHeight: 1.6, maxWidth: 720, margin: 0 }}>
          We are a small team. We will make mistakes. When we do, we will tell you, fix them, and write
          publicly about what we learned. That&apos;s the deal.
        </p>
        <div style={{ marginTop: 24, fontFamily: mk.mono, fontSize: 11, color: mk.pencil, letterSpacing: "0.08em" }}>
          Security questions → <span style={{ color: mk.ink }}>security@penkeep.com</span>
        </div>
      </section>
    </>
  );
}
