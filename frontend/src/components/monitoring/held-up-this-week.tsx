import type { SupportingItem } from "@/types";

interface Props {
  items: SupportingItem[];
  className?: string;
}

function timeAgo(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const diffSec = Math.max(0, Math.floor((Date.now() - then) / 1000));
  if (diffSec < 3600) return "just now";
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`;
  const days = Math.floor(diffSec / 86400);
  if (days <= 1) return "yesterday";
  return `${days}d ago`;
}

/**
 * Supporting evidence — signals the pipeline judged as validating the
 * thesis rather than threatening it. Rendered distinctly from the events
 * list so a positive read never gets mixed in with threat cards, which is
 * the design point: users should sometimes feel "my thesis was validated"
 * rather than only "my thesis is under attack."
 *
 * Intentionally quiet visually. The whole feature loses its emotional
 * balance if it turns into a green highlight reel.
 */
export function HeldUpThisWeek({ items, className = "" }: Props) {
  if (!items || items.length === 0) return null;

  return (
    <section
      className={`border-l-2 border-emerald-500/60 bg-emerald-500/5 px-4 py-3.5 space-y-3 ${className}`}
    >
      <div className="space-y-1">
        <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-emerald-700">
          Held up this week
        </p>
        <p className="font-sans text-xs text-foreground/80 leading-relaxed">
          Signals we saw that reinforced your thesis rather than challenged it.
        </p>
      </div>

      <ul className="space-y-3">
        {items.map((item) => {
          const meta = [item.assumption_label, timeAgo(item.created_at)]
            .filter(Boolean)
            .join(" · ");
          const takeaway =
            item.evidence_summary || item.ai_analysis || item.summary || "";
          return (
            <li key={item.event_id} className="space-y-1">
              <p className="font-sans text-sm text-foreground leading-snug">
                {item.title}
              </p>
              {takeaway && (
                <p className="font-sans text-xs text-muted-foreground leading-relaxed">
                  {takeaway.length > 240 ? `${takeaway.slice(0, 240)}…` : takeaway}
                </p>
              )}
              {meta && (
                <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground/70">
                  {meta}
                </p>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
