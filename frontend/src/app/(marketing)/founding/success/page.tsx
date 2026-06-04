import Link from "next/link";
import { mk } from "../../../_mkt/tokens";

const pad = "clamp(22px, 4.5vw, 56px)";

export default function FoundingSuccessPage() {
  return (
    <section
      style={{
        padding: `clamp(70px,11vw,150px) ${pad}`,
        maxWidth: 720,
        margin: "0 auto",
        textAlign: "center",
      }}
    >
      <div
        style={{
          fontFamily: mk.mono,
          fontSize: 11,
          letterSpacing: "0.16em",
          textTransform: "uppercase",
          color: mk.accent,
          marginBottom: 22,
        }}
      >
        You&apos;re a founding member
      </div>

      <h1
        style={{
          fontFamily: mk.display,
          fontWeight: 500,
          fontSize: "clamp(40px,7vw,72px)",
          lineHeight: 1.02,
          letterSpacing: "-0.03em",
          margin: "0 0 24px",
          color: mk.ink,
        }}
      >
        Your founding price is{" "}
        <span style={{ fontStyle: "italic", color: mk.accent }}>locked.</span>
      </h1>

      <p
        style={{
          fontFamily: mk.display,
          fontWeight: 500,
          fontSize: "clamp(17px,1.9vw,21px)",
          lineHeight: 1.55,
          color: mk.inkSoft,
          maxWidth: 520,
          margin: "0 auto 18px",
        }}
      >
        Payment received — thank you. We&apos;ll email you the moment your account is
        ready, before the public launch. Check your inbox for the receipt.
      </p>

      <p
        style={{
          fontFamily: mk.sans,
          fontSize: 15,
          color: mk.pencil,
          maxWidth: 520,
          margin: "0 auto 40px",
          lineHeight: 1.6,
        }}
      >
        As a founding member you get a direct line into what we build next — just reply
        to that email any time.
      </p>

      <Link
        href="/research"
        style={{
          display: "inline-block",
          padding: "14px 30px",
          background: mk.ink,
          color: mk.paper,
          borderRadius: 999,
          fontFamily: mk.sans,
          fontWeight: 500,
          fontSize: 15,
          textDecoration: "none",
        }}
      >
        Stress-test a stock while you wait →
      </Link>
    </section>
  );
}
