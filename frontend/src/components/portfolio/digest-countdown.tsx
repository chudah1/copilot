"use client";

export function DigestCountdown({ nextDigestAt }: { nextDigestAt: string | null }) {
  if (!nextDigestAt) return null;

  const next = new Date(nextDigestAt);
  const now = new Date();
  const diffMs = next.getTime() - now.getTime();

  if (diffMs <= 0) return null;

  const hours = Math.floor(diffMs / (1000 * 60 * 60));

  const todayMidnight = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const nextMidnight = new Date(next.getFullYear(), next.getMonth(), next.getDate());
  const calendarDays = Math.round((nextMidnight.getTime() - todayMidnight.getTime()) / (1000 * 60 * 60 * 24));

  let countdown: string;
  if (calendarDays === 0) {
    countdown = `${hours}h`;
  } else if (calendarDays === 1) {
    countdown = "Tomorrow";
  } else {
    countdown = `${calendarDays}d`;
  }

  const dateLabel = next.toLocaleDateString("en-GB", {
    weekday: "short",
    hour: "2-digit",
    minute: "2-digit",
  });

  return (
    <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
      <span className="font-mono text-[13px] font-medium text-primary tabular-nums">
        {countdown}
      </span>
      <span className="font-sans text-xs text-foreground/78">
        until the next review digest
      </span>
      <span className="font-mono text-[10px] text-muted-foreground/70">
        {dateLabel}
      </span>
    </div>
  );
}
