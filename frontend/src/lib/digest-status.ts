import type { Digest } from "@/types";

export function digestStatusLabel(digest: Digest) {
  if (digest.sent_at || digest.status === "sent") return "Emailed";
  if (digest.content.html) return "Saved in app";
  if (digest.status === "draft" || digest.status === "pending") return "Preparing";
  return "Unavailable";
}

export function digestStatusTone(digest: Digest) {
  const label = digestStatusLabel(digest);
  if (label === "Emailed" || label === "Saved in app") return "text-emerald-700";
  if (label === "Preparing") return "text-amber-700";
  return "text-muted-foreground";
}
