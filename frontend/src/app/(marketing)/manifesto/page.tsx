import { WaitlistForm } from "../../_mkt/waitlist-form";
import { mk } from "../../_mkt/tokens";

export default function ManifestoPage() {
  const pad = "clamp(22px, 4.5vw, 56px)";
  return (
    <>
      {/* Header */}
      <section style={{ padding: `clamp(60px,10vw,120px) ${pad} clamp(40px,5vw,70px)` }}>
        <div style={{ fontFamily: mk.mono, fontSize: 11, letterSpacing: "0.14em", textTransform: "uppercase", color: mk.pencil, marginBottom: 14 }}>
          Manifesto · 2026
        </div>
        <h1
          style={{
            fontFamily: mk.sans,
            fontWeight: 600,
            fontSize: "clamp(44px,8vw,96px)",
            lineHeight: 0.98,
            letterSpacing: "-0.04em",
            margin: 0,
            maxWidth: 1000,
          }}
        >
          We built<br />
          the app we<br />
          <span style={{ color: mk.accent }}>wished we&apos;d had</span><br />
          ten years ago.
        </h1>
      </section>

      {/* Body */}
      <section
        style={{
          padding: `0 ${pad} clamp(70px,8vw,120px)`,
          maxWidth: `calc(820px + clamp(44px,9vw,112px))`,
          display: "flex",
          flexDirection: "column",
          gap: "clamp(24px,3vw,32px)",
        }}
      >
        <p
          style={{
            fontFamily: mk.sans,
            fontSize: "clamp(20px,2.5vw,28px)",
            fontWeight: 500,
            lineHeight: 1.35,
            letterSpacing: "-0.012em",
            margin: 0,
          }}
        >
          The honest reason most retail investors lose money is not because they&apos;re stupid.
          It&apos;s because they bought a stock for a reason that{" "}
          <em style={{ color: mk.accent }}>made sense at the time</em>, and then never wrote it down.
        </p>

        <div style={{ fontFamily: mk.sans, fontSize: "clamp(16px,1.8vw,18px)", lineHeight: 1.7, color: mk.inkSoft, display: "flex", flexDirection: "column", gap: 16 }}>
          <p style={{ margin: 0 }}>
            Six months later, you check the price. It&apos;s down. Or up. You feel something. You
            tell yourself a story: &ldquo;the market doesn&apos;t understand it yet&rdquo; or &ldquo;I should
            have sold.&rdquo; The story has nothing to do with the original reason you bought,
            because the original reason is gone.
          </p>
          <p style={{ margin: 0 }}>
            We&apos;ve all done this. We built penKeep because we kept doing it ourselves, despite
            knowing better, and despite every single existing tool being available to help.
          </p>
        </div>

        {/* Pull card */}
        <div
          style={{
            padding: "clamp(20px,3vw,36px)",
            background: mk.cardSoft,
            border: `1px solid ${mk.pencilLight}`,
            borderRadius: 16,
            fontFamily: mk.sans,
            fontSize: "clamp(20px,2.5vw,28px)",
            fontWeight: 500,
            lineHeight: 1.3,
            letterSpacing: "-0.015em",
          }}
        >
          The tools we had were trying to help us <em style={{ color: mk.accent }}>trade</em>.
          We wanted to <em style={{ color: mk.accent }}>invest</em>.
        </div>

        <div style={{ fontFamily: mk.sans, fontSize: "clamp(16px,1.8vw,18px)", lineHeight: 1.7, color: mk.inkSoft, display: "flex", flexDirection: "column", gap: 16 }}>
          <p style={{ margin: 0 }}>
            A trader watches the price. An investor watches the reason. Brokers are built for
            traders. Trackers are built for traders. The default loop of modern fintech is to
            open the app, see green or red, and feel something. That&apos;s not investing. That&apos;s
            being entertained by your own savings.
          </p>
          <p style={{ margin: 0 }}>
            So we set out to build the opposite. An app that asks you, gently, on a Sunday,
            why you own each thing. An app that&apos;s quiet for a quarter. Then, when something
            you actually care about moves, one short note. No buy buttons. No &ldquo;you&apos;re up
            0.4%.&rdquo; No charts you stare at while waiting for the train.
          </p>
        </div>

        {/* Principles */}
        <div
          style={{ marginTop: "clamp(20px,3vw,40px)", display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 14 }}
          className="max-md:grid-cols-1"
        >
          {[
            ["Words beat numbers", "Your reason is a sentence, not a score. You can read it back and argue with it."],
            ["Silence is a feature", "We don't fill a feed when nothing happened. Most weeks we say nothing."],
            ["Evidence, not opinion", "Every signal has sources you can click. We don't say sell."],
          ].map(([h, b]) => (
            <div key={h} style={{ background: mk.card, border: `1px solid ${mk.pencilLight}`, borderRadius: 14, padding: 20 }}>
              <div style={{ fontFamily: mk.sans, fontSize: 19, fontWeight: 600, letterSpacing: "-0.015em", lineHeight: 1.2 }}>{h}</div>
              <div style={{ fontFamily: mk.sans, fontSize: 14, lineHeight: 1.55, color: mk.pencil, marginTop: 8 }}>{b}</div>
            </div>
          ))}
        </div>

        <div style={{ fontFamily: mk.sans, fontSize: "clamp(16px,1.8vw,18px)", lineHeight: 1.7, color: mk.inkSoft, display: "flex", flexDirection: "column", gap: 16, marginTop: 16 }}>
          <p style={{ margin: 0 }}>
            If you&apos;ve ever bought a stock and forgotten why, penKeep is for you. If you&apos;ve ever
            held on past the reason being broken, or sold a winner because of noise, penKeep
            is for you. If you&apos;d rather check your app once a month than ten times a day, we
            built this for you.
          </p>
          <p style={{ margin: 0, fontStyle: "italic", color: mk.ink }}>
            Never forget why you bought. Know when the reason changes. That&apos;s the whole thing.
          </p>
        </div>

        {/* Signature */}
        <div
          style={{
            marginTop: "clamp(20px,3vw,32px)",
            padding: "20px 0",
            borderTop: `1px solid ${mk.pencilLight}`,
            display: "flex",
            alignItems: "center",
            gap: 14,
          }}
        >
          <div
            style={{
              width: 44,
              height: 44,
              borderRadius: 999,
              background: mk.accentSoft,
              border: `1px solid ${mk.accent}`,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontFamily: mk.sans,
              fontWeight: 600,
              color: mk.accent,
              fontSize: 17,
              flex: "0 0 44px",
            }}
          >
            C
          </div>
          <div>
            <div style={{ fontFamily: mk.sans, fontSize: 16, fontWeight: 600 }}>The penKeep team</div>
            <div style={{ fontFamily: mk.mono, fontSize: 11, color: mk.pencil, letterSpacing: "0.06em", marginTop: 2 }}>founders</div>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section
        style={{
          padding: `clamp(50px,8vw,100px) ${pad}`,
          background: mk.cardSoft,
          borderTop: `1px solid ${mk.pencilLight}`,
        }}
      >
        <h2 style={{ fontFamily: mk.sans, fontSize: "clamp(36px,5vw,56px)", fontWeight: 600, margin: 0, lineHeight: 1, letterSpacing: "-0.03em", maxWidth: 800 }}>
          Build the app with us.<br /><span style={{ color: mk.accent }}>Join the waitlist.</span>
        </h2>
        <p style={{ fontFamily: mk.sans, fontSize: "clamp(16px,1.8vw,18px)", color: mk.pencil, marginTop: 14, maxWidth: 580 }}>
          We&apos;re shipping with a small group of early users first. If you want to be one,
          drop your email below.
        </p>
        <div style={{ marginTop: "clamp(22px,3vw,32px)" }}>
          <WaitlistForm />
        </div>
      </section>
    </>
  );
}
