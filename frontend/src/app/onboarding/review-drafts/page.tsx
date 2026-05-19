"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { motion } from "framer-motion";
import { AuthGuard } from "@/components/layout/auth-guard";
import { api } from "@/lib/api";
import type { DraftItem, DraftStatus } from "@/types";

interface DraftWithState extends DraftItem {
  activating: boolean;
  dismissing: boolean;
}

export default function ReviewDraftsPage() {
  const router = useRouter();
  const [drafts, setDrafts] = useState<DraftWithState[]>([]);
  const [pageLoading, setPageLoading] = useState(true);

  useEffect(() => {
    api
      .get<DraftStatus>("/api/portfolio/draft-status")
      .then((ds) => {
        const reviewable = ds.drafts
          .filter((d) => d.status === "ready" && d.thesis_id)
          .map((d) => ({ ...d, activating: false, dismissing: false }));
        setDrafts(reviewable);
      })
      .catch(() => {})
      .finally(() => setPageLoading(false));
  }, []);

  const updateDraft = (draft_id: string, patch: Partial<DraftWithState>) =>
    setDrafts((prev) => prev.map((d) => (d.draft_id === draft_id ? { ...d, ...patch } : d)));

  const handleActivate = async (d: DraftWithState) => {
    if (!d.thesis_id) return;
    updateDraft(d.draft_id, { activating: true });
    try {
      await api.put(`/api/theses/${d.thesis_id}`, { status: "active" });
      updateDraft(d.draft_id, { status: "reviewed", activating: false });
    } catch {
      updateDraft(d.draft_id, { activating: false });
    }
  };

  const handleDismiss = async (d: DraftWithState) => {
    if (!d.thesis_id) return;
    updateDraft(d.draft_id, { dismissing: true });
    try {
      await api.post(`/api/theses/${d.thesis_id}/invalidate`, {
        reason: "Dismissed during onboarding review",
      });
      updateDraft(d.draft_id, { status: "reviewed", dismissing: false });
    } catch {
      updateDraft(d.draft_id, { dismissing: false });
    }
  };

  const activeDrafts = drafts.filter((d) => d.status === "ready");
  const reviewedCount = drafts.filter((d) => d.status === "reviewed").length;
  const allDone = activeDrafts.length === 0 && drafts.length > 0;

  return (
    <AuthGuard>
      <div className="min-h-screen bg-background">
        <div className="border-b border-border/60 px-6 py-4 flex items-center justify-between">
          <span className="font-mono text-xs text-muted-foreground tracking-wide">
            Copilot Investor
          </span>
          <Link
            href="/dashboard"
            className="font-mono text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            Skip to dashboard →
          </Link>
        </div>

        <div className="max-w-2xl mx-auto px-6 pt-14 pb-24">
          <div className="mb-10 border-b border-foreground/10 pb-8">
            <span className="font-mono text-[10px] uppercase tracking-[0.3em] text-primary block mb-3">
              Draft theses
            </span>
            <h1 className="font-display italic text-[2.25rem] leading-tight text-foreground tracking-tight">
              AI drafted these while<br />you were setting up.
            </h1>
            <p className="text-muted-foreground text-sm mt-3 leading-relaxed max-w-md">
              Review each one. Accept what feels right — you can always edit the details on the
              position page.
            </p>
          </div>

          {pageLoading && (
            <div className="space-y-4">
              {[1, 2, 3].map((i) => (
                <div key={i} className="border border-border h-40 animate-pulse bg-muted/30" />
              ))}
            </div>
          )}

          {!pageLoading && drafts.length === 0 && (
            <div className="text-center py-16 space-y-4">
              <p className="text-muted-foreground font-mono text-sm">No drafts ready yet.</p>
              <p className="text-muted-foreground/60 text-xs">
                Drafts are generated in the background after import — check back shortly.
              </p>
              <Link
                href="/dashboard"
                className="inline-block mt-4 bg-primary text-primary-foreground px-6 py-2.5 text-sm font-mono hover:bg-primary/90 transition-colors"
              >
                Go to dashboard →
              </Link>
            </div>
          )}

          <div className="space-y-5">
            {activeDrafts.map((d, i) => (
              <motion.div
                key={d.draft_id}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.08, duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
              >
                <DraftCard
                  draft={d}
                  onActivate={() => handleActivate(d)}
                  onDismiss={() => handleDismiss(d)}
                  onEdit={() => router.push(`/dashboard/positions/${d.ticker}`)}
                />
              </motion.div>
            ))}
          </div>

          {allDone && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4 }}
              className="mt-10 border-t border-border/60 pt-8 space-y-6"
            >
              <div className="space-y-1">
                <span className="font-mono text-[10px] uppercase tracking-[0.3em] text-primary">
                  Done
                </span>
                <p className="font-display italic text-xl text-foreground">
                  {reviewedCount === 1
                    ? "1 position has a thesis now."
                    : `${reviewedCount} positions have theses now.`}
                </p>
                <p className="text-sm text-muted-foreground">
                  Monitoring starts tonight. You&rsquo;ll get a digest on Sunday.
                </p>
              </div>
              <Link
                href="/dashboard"
                className="inline-block bg-primary text-primary-foreground px-8 py-3 text-sm font-mono tracking-wide hover:bg-primary/90 transition-colors"
              >
                Go to dashboard →
              </Link>
            </motion.div>
          )}

          {reviewedCount > 0 && !allDone && (
            <div className="mt-8 border-t border-border/40 pt-6">
              <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                Reviewed ({reviewedCount})
              </p>
            </div>
          )}
        </div>
      </div>
    </AuthGuard>
  );
}

function DraftCard({
  draft,
  onActivate,
  onDismiss,
  onEdit,
}: {
  draft: DraftWithState;
  onActivate: () => void;
  onDismiss: () => void;
  onEdit: () => void;
}) {
  return (
    <div className="border border-border">
      <div className="border-b border-border/60 px-5 py-3 flex items-center justify-between bg-muted/20">
        <div className="flex items-baseline gap-2.5">
          <span className="font-display text-xl font-bold text-foreground">{draft.ticker}</span>
          <span className="text-muted-foreground text-xs">{draft.name}</span>
        </div>
        <span className="font-mono text-[9px] uppercase tracking-[0.2em] text-primary border border-primary/30 px-2 py-0.5">
          AI draft
        </span>
      </div>

      <div className="px-5 py-4 space-y-4">
        {draft.why_own_it ? (
          <>
            <ThesisField label="Why you own it" text={draft.why_own_it} />
            {draft.must_remain_true && (
              <ThesisField label="Must remain true" text={draft.must_remain_true} />
            )}
            {draft.what_would_change_my_mind && (
              <ThesisField label="What would change my mind" text={draft.what_would_change_my_mind} />
            )}
          </>
        ) : (
          <div className="h-16 flex items-center">
            <span className="font-mono text-xs text-muted-foreground animate-pulse">
              Loading thesis…
            </span>
          </div>
        )}
      </div>

      <div className="border-t border-border/60 px-5 py-3 flex items-center gap-4 bg-muted/10">
        <button
          onClick={onActivate}
          disabled={draft.activating || draft.dismissing}
          className="bg-primary text-primary-foreground px-5 py-2 text-xs font-mono tracking-wide hover:bg-primary/90 transition-colors disabled:opacity-40"
        >
          {draft.activating ? "Activating…" : "Accept →"}
        </button>
        <button
          onClick={onEdit}
          className="text-xs font-mono text-foreground/70 hover:text-foreground transition-colors underline underline-offset-4"
        >
          Edit on position page
        </button>
        <button
          onClick={onDismiss}
          disabled={draft.activating || draft.dismissing}
          className="ml-auto text-xs font-mono text-muted-foreground hover:text-foreground transition-colors disabled:opacity-40"
        >
          {draft.dismissing ? "Dismissing…" : "Dismiss"}
        </button>
      </div>
    </div>
  );
}

function ThesisField({ label, text }: { label: string; text: string }) {
  return (
    <div className="space-y-0.5">
      <div className="font-mono text-[9px] uppercase tracking-[0.2em] text-muted-foreground">
        {label}
      </div>
      <p className="text-sm text-foreground leading-relaxed">{text}</p>
    </div>
  );
}
