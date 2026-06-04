import { mk } from "./tokens";

const pad = "clamp(22px, 4.5vw, 56px)";

/**
 * Shared shell + prose primitives for the legal pages (terms, privacy, refunds).
 * Keeps the three documents visually consistent and readable.
 */
export function LegalPage({
  kicker,
  title,
  updated,
  intro,
  children,
}: {
  kicker: string;
  title: React.ReactNode;
  updated: string;
  intro?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <>
      <section style={{ padding: `clamp(50px,8vw,100px) ${pad} clamp(24px,3vw,40px)` }}>
        <div
          style={{
            fontFamily: mk.mono,
            fontSize: 11,
            letterSpacing: "0.14em",
            textTransform: "uppercase",
            color: mk.pencil,
            marginBottom: 14,
          }}
        >
          {kicker}
        </div>
        <h1
          style={{
            fontFamily: mk.sans,
            fontWeight: 600,
            fontSize: "clamp(40px,6.5vw,76px)",
            lineHeight: 1.02,
            letterSpacing: "-0.035em",
            margin: 0,
          }}
        >
          {title}
        </h1>
        <div
          style={{
            fontFamily: mk.mono,
            fontSize: 12,
            color: mk.pencil,
            marginTop: 20,
            letterSpacing: "0.04em",
          }}
        >
          Last updated · {updated}
        </div>
        {intro && (
          <p
            style={{
              fontFamily: mk.sans,
              fontSize: "clamp(16px,1.7vw,19px)",
              lineHeight: 1.6,
              color: mk.inkSoft,
              marginTop: 24,
              maxWidth: 720,
            }}
          >
            {intro}
          </p>
        )}
      </section>

      <section
        style={{
          padding: `clamp(16px,2vw,28px) ${pad} clamp(60px,9vw,120px)`,
          maxWidth: 820,
        }}
      >
        {children}
      </section>
    </>
  );
}

export function LegalSection({
  n,
  title,
  children,
}: {
  n: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div style={{ marginTop: "clamp(36px,5vw,52px)" }}>
      <h2
        style={{
          fontFamily: mk.sans,
          fontSize: "clamp(20px,2.4vw,27px)",
          fontWeight: 600,
          letterSpacing: "-0.02em",
          lineHeight: 1.2,
          margin: 0,
          display: "flex",
          gap: 14,
          alignItems: "baseline",
        }}
      >
        <span style={{ fontFamily: mk.mono, fontSize: 14, color: mk.accent, fontWeight: 500 }}>
          {n}
        </span>
        <span>{title}</span>
      </h2>
      <div style={{ marginTop: 14 }}>{children}</div>
    </div>
  );
}

export function P({ children }: { children: React.ReactNode }) {
  return (
    <p
      style={{
        fontFamily: mk.sans,
        fontSize: "clamp(15px,1.5vw,16.5px)",
        lineHeight: 1.7,
        color: mk.inkSoft,
        margin: "0 0 16px",
      }}
    >
      {children}
    </p>
  );
}

export function L({ items }: { items: React.ReactNode[] }) {
  return (
    <ul style={{ margin: "0 0 16px", padding: 0, listStyle: "none", display: "flex", flexDirection: "column", gap: 10 }}>
      {items.map((it, i) => (
        <li
          key={i}
          style={{
            fontFamily: mk.sans,
            fontSize: "clamp(15px,1.5vw,16.5px)",
            lineHeight: 1.65,
            color: mk.inkSoft,
            paddingLeft: 22,
            position: "relative",
          }}
        >
          <span style={{ position: "absolute", left: 0, top: 0, color: mk.accent }}>—</span>
          {it}
        </li>
      ))}
    </ul>
  );
}

/** Inline placeholder for details the founder must fill before publishing. */
export function Fill({ children }: { children: React.ReactNode }) {
  return (
    <span
      style={{
        background: mk.accentSoft,
        color: mk.accentDeep,
        fontFamily: mk.mono,
        fontSize: "0.86em",
        padding: "1px 6px",
        borderRadius: 4,
        whiteSpace: "nowrap",
      }}
    >
      {children}
    </span>
  );
}

export function Strong({ children }: { children: React.ReactNode }) {
  return <strong style={{ color: mk.ink, fontWeight: 600 }}>{children}</strong>;
}
