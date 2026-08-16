"use client";

export interface PreActionCheckpointDraft {
  ticker: string;
  why_own_it: string;
  must_remain_true: string;
  what_would_change_my_mind: string;
  created_at: string;
}

function normalizeTicker(ticker: string) {
  return ticker.trim().toUpperCase();
}

function storageKey(ticker: string) {
  return `penkeep_pre_action_checkpoint:${normalizeTicker(ticker)}`;
}

export function savePreActionCheckpointDraft(draft: PreActionCheckpointDraft) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(storageKey(draft.ticker), JSON.stringify(draft));
}

export function loadPreActionCheckpointDraft(ticker: string): PreActionCheckpointDraft | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(storageKey(ticker));
  if (!raw) return null;

  try {
    const parsed = JSON.parse(raw) as Partial<PreActionCheckpointDraft>;
    if (
      typeof parsed.ticker !== "string" ||
      typeof parsed.why_own_it !== "string" ||
      typeof parsed.must_remain_true !== "string" ||
      typeof parsed.what_would_change_my_mind !== "string" ||
      typeof parsed.created_at !== "string"
    ) {
      return null;
    }
    return {
      ticker: normalizeTicker(parsed.ticker),
      why_own_it: parsed.why_own_it,
      must_remain_true: parsed.must_remain_true,
      what_would_change_my_mind: parsed.what_would_change_my_mind,
      created_at: parsed.created_at,
    };
  } catch {
    return null;
  }
}

export function clearPreActionCheckpointDraft(ticker: string) {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(storageKey(ticker));
}

export function buildPreActionCheckpointNote(args: {
  ticker: string;
  why_own_it: string;
  must_remain_true: string;
  what_would_change_my_mind: string;
}) {
  const lines = [
    `Added to ${normalizeTicker(args.ticker)} after a pre-trade checkpoint.`,
    `Why now: ${args.why_own_it.trim()}`,
  ];

  if (args.must_remain_true.trim()) {
    lines.push(`Must remain true: ${args.must_remain_true.trim()}`);
  }

  lines.push(`This add is wrong if: ${args.what_would_change_my_mind.trim()}`);
  return lines.join("\n");
}
