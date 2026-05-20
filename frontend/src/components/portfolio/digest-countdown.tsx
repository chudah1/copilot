"use client";

export function DigestCountdown({ nextDigestAt }: { nextDigestAt: string | null }) {
  if (!nextDigestAt) return null;

  const next = new Date(nextDigestAt);
  const now = new Date();
  const diffMs = next.getTime() - now.getTime();

  if (diffMs <= 0) return null;

  const days = Math.floor(diffMs / (1000 * 60 * 60 * 24));
  const hours = Math.floor((diffMs % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));

  let countdown: string;
  if (days === 0) {
    countdown = `${hours}h`;
  } else if (days === 1) {
    countdown = "Tomorrow";
  } else {
    countdown = `${days}d`;
  }

  const dateLabel = next.toLocaleDateString("en-GB", {
    weekday: "short",
    hour: "2-digit",
    minute: "2-digit",
  });

  return (
    <div className="inline-flex items-center gap-3 border border-border px-4 py-1.5">
      <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
        Next digest
      </span>
      <span className="w-px h-3 bg-border" />
      <span className="font-mono text-[11px] font-medium text-primary tabular-nums">
        {countdown}
      </span>
      <span className="font-mono text-[10px] text-muted-foreground/70">
        {dateLabel}
      </span>
    </div>
  );
}
