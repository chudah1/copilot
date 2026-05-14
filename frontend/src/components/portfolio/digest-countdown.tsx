"use client";

export function DigestCountdown({ nextDigestAt }: { nextDigestAt: string | null }) {
  if (!nextDigestAt) return null;

  const next = new Date(nextDigestAt);
  const now = new Date();
  const diffMs = next.getTime() - now.getTime();

  if (diffMs <= 0) return null;

  const days = Math.floor(diffMs / (1000 * 60 * 60 * 24));
  const hours = Math.floor((diffMs % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));

  let label: string;
  if (days === 0) {
    label = `${hours}h`;
  } else if (days === 1) {
    label = "Tomorrow";
  } else {
    label = `${days} days`;
  }

  return (
    <div className="flex items-center gap-2 rounded-md border px-3 py-2 text-sm">
      <span className="text-muted-foreground">Next digest:</span>
      <span className="font-medium">{label}</span>
      <span className="text-xs text-muted-foreground">
        {next.toLocaleDateString("en-GB", { weekday: "short", hour: "2-digit", minute: "2-digit" })}
      </span>
    </div>
  );
}
