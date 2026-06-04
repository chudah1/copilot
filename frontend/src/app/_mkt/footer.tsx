import Link from "next/link";
import { mk } from "./tokens";
import { PenKeepMark } from "./mark";

export function MarketingFooter() {
  const sections = [
    {
      title: "Product",
      links: [
        { label: "How it works", href: "/#how-it-works" },
        { label: "Pricing", href: "/pricing" },
        { label: "FAQ", href: "/faq" },
      ],
    },
    {
      title: "Use penKeep",
      links: [
        { label: "Join waitlist", href: "/#signup" },
        { label: "Go to app", href: "/dashboard" },
        { label: "Security", href: "/security" },
      ],
    },
  ] as const;

  return (
    <footer
      style={{
        borderTop: `1px solid ${mk.pencilLight}`,
        padding: "clamp(26px, 4vw, 40px) clamp(22px, 4.5vw, 56px)",
        fontFamily: mk.sans,
        background: mk.paper,
      }}
    >
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "minmax(0, 1.2fr) minmax(0, 0.8fr) minmax(0, 0.8fr)",
          gap: 28,
        }}
        className="max-lg:grid-cols-1"
      >
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <PenKeepMark size={18} color={mk.pencil} />
            <span style={{ fontWeight: 600, fontSize: 14, color: mk.ink }}>penKeep</span>
            <span style={{ fontSize: 13, color: mk.pencil }}>© 2026</span>
          </div>
          <p style={{ margin: 0, maxWidth: 420, fontSize: 14, lineHeight: 1.55, color: mk.pencil }}>
            Write the reason you own it. Revisit it when the evidence changes. Stay quiet the rest of the time.
          </p>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap", paddingTop: 4 }}>
            <Link
              href="/blog"
              style={{
                color: mk.ink,
                textDecoration: "none",
                fontSize: 14,
                fontWeight: 500,
              }}
            >
              Read the story
            </Link>
            <Link
              href="/security"
              style={{
                color: mk.pencil,
                textDecoration: "none",
                fontSize: 14,
              }}
            >
              How we handle trust
            </Link>
          </div>
          <div style={{ fontFamily: mk.mono, fontSize: 11, color: mk.pencil, letterSpacing: "0.08em", paddingTop: 2 }}>
            read-only tracking, not financial advice
          </div>
        </div>

        {sections.map((section) => (
          <div key={section.title} style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <div
              style={{
                fontFamily: mk.mono,
                fontSize: 10,
                letterSpacing: "0.14em",
                textTransform: "uppercase",
                color: mk.pencil,
              }}
            >
              {section.title}
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {section.links.map(({ label, href }) => (
                <Link
                  key={label}
                  href={href}
                  style={{
                    color: mk.pencil,
                    textDecoration: "none",
                    fontSize: 14,
                    lineHeight: 1.4,
                  }}
                >
                  {label}
                </Link>
              ))}
            </div>
          </div>
        ))}
      </div>
    </footer>
  );
}
