import type { HoldingPulse } from "@/types";

interface Props {
  pulse: HoldingPulse | undefined;
  hasThesis: boolean;
  className?: string;
}

function timeAgo(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "just now";
  const diffSec = Math.max(0, Math.floor((Date.now() - then) / 1000));
  if (diffSec < 60) return "just now";
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`;
  const days = Math.floor(diffSec / 86400);
  if (days < 30) return `${days}d ago`;
  const months = Math.floor(days / 30);
  return `${months}mo ago`;
}

function stateWords(status: HoldingPulse["pulse_status"], hasThesis: boolean) {
  if (!hasThesis) return { text: "no thesis yet", color: "text-muted-foreground/70" };
  if (status === "review") return { text: "worth reviewing", color: "text-red-700" };
  if (status === "watch") return { text: "watching closely", color: "text-amber-700" };
  return { text: "thesis intact", color: "text-emerald-700" };
}

/**
 * Small always-on line proving the app has been looking, even when nothing
 * fired. Reads: "Checked 2h ago · 4 sources · thesis intact". The whole
 * point is that a quiet dashboard is only reassuring when the user can see
 * the watchfulness — this component is that receipt.
 */
export function WatchReceipt({ pulse, hasThesis, className = "" }: Props) {
  const base = "font-mono text-[10px] tracking-[0.08em] leading-relaxed";
  const muted = "text-muted-foreground/70";

  // No thesis → don't offer a fake "checked" reassurance; there's no thesis
  // to check against. The CTA to add one lives elsewhere on the card.
  if (!hasThesis) return null;

  // Thesis exists but no pass has run yet — first pulse is in flight.
  if (!pulse?.last_checked_at) {
    return (
      <p className={`${base} ${muted} ${className}`}>
        Monitoring in progress…
      </p>
    );
  }

  const state = stateWords(pulse.pulse_status, hasThesis);
  const sources = pulse.sources_count;

  return (
    <p className={`${base} ${muted} ${className}`}>
      <span>Checked {timeAgo(pulse.last_checked_at)}</span>
      {typeof sources === "number" && sources > 0 && (
        <>
          <span className="opacity-60 mx-1.5">·</span>
          <span>
            {sources} {sources === 1 ? "source" : "sources"}
          </span>
        </>
      )}
      <span className="opacity-60 mx-1.5">·</span>
      <span className={state.color}>{state.text}</span>
    </p>
  );
}
