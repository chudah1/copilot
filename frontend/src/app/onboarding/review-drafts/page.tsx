"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { motion } from "framer-motion";
import { AuthGuard } from "@/components/layout/auth-guard";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import type { DraftItem, DraftStatus, OnboardingState } from "@/types";

interface DraftWithState extends DraftItem {
  activating: boolean;
  dismissing: boolean;
  reviewOutcome?: "kept" | "dismissed" | null;
}

export default function ReviewDraftsPage() {
  const router = useRouter();
  const [drafts, setDrafts] = useState<DraftWithState[]>([]);
  const [draftStatus, setDraftStatus] = useState<DraftStatus | null>(null);
  const [pageLoading, setPageLoading] = useState(true);
  const [onboardingState, setOnboardingState] = useState<OnboardingState | null>(null);
  const pendingDraftCount = draftStatus?.pending ?? 0;
  const failedDraftCount = draftStatus?.failed ?? 0;

  const applyDraftStatus = (ds: DraftStatus) => {
    setDraftStatus(ds);
    const reviewable = ds.drafts
      .filter((d) => d.status === "ready" && d.thesis_id)
      .map((d) => ({ ...d, activating: false, dismissing: false, reviewOutcome: null }));
    setDrafts(reviewable);
  };

  useEffect(() => {
    api.get<OnboardingState>("/api/onboarding/state").then(setOnboardingState).catch(() => null);
    api
      .get<DraftStatus>("/api/portfolio/draft-status")
      .then(applyDraftStatus)
      .catch(() => {})
      .finally(() => setPageLoading(false));
  }, []);

  useEffect(() => {
    if (pendingDraftCount === 0) return;

    const intervalId = window.setInterval(() => {
      void api.get<DraftStatus>("/api/portfolio/draft-status").then(applyDraftStatus).catch(() => null);
    }, 15000);

    return () => window.clearInterval(intervalId);
  }, [pendingDraftCount]);

  const investorProfile = onboardingState?.investor_profile ?? null;
  const copy = investorProfile === "thesis_driven"
      ? {
          titleLine1: "AI drafted these while",
          titleLine2: "you were setting up.",
        subtitle: "Keep it if the shape is right. Fix it on the position page if it is not.",
        emptyTitle: "No drafts ready yet.",
        emptyBody: "Draft theses are still generating.",
        pendingTitle: "Drafts are on the way.",
        pendingBody: "We’re still turning imported holdings into draft theses.",
        missingTitle: "Nothing is ready for review yet.",
        missingBody: "Add or import holdings first.",
        connectedMissingBody: "Nothing is waiting for review right now. Write the first thesis from the dashboard.",
        failedTitle: "Drafting needs a manual pass.",
        failedBody: "We couldn’t draft these automatically. Write the first thesis from the dashboard.",
        doneLine: "Monitoring starts tonight.",
        accept: "Keep as working thesis →",
        edit: "Reshape on position page",
        dismiss: "Reject this thesis",
      }
    : investorProfile === "hearsay_driven"
      ? {
          titleLine1: "We turned the first story",
          titleLine2: "into draft reasons.",
        subtitle: "Keep it if it feels true. Fix it on the position page if it does not.",
        emptyTitle: "No drafts ready yet.",
        emptyBody: "Draft reasons are still generating.",
        pendingTitle: "Draft reasons are on the way.",
        pendingBody: "We’re still turning imported holdings into draft reasons.",
        missingTitle: "Nothing is ready for review yet.",
        missingBody: "Add or import holdings first.",
        connectedMissingBody: "Nothing is waiting for review right now. Write the first reason from the dashboard.",
        failedTitle: "Drafting needs a manual pass.",
        failedBody: "We couldn’t draft these automatically. Write the first reason from the dashboard.",
        doneLine: "Monitoring starts tonight.",
        accept: "Keep as working reason →",
        edit: "Reshape on position page",
        dismiss: "Reject this story",
      }
      : {
          titleLine1: "AI drafted these while",
          titleLine2: "you were setting up.",
        subtitle: "Keep it if the shape is right. Fix it on the position page if it is not.",
        emptyTitle: "No drafts ready yet.",
        emptyBody: "Drafts are still generating.",
        pendingTitle: "Drafts are on the way.",
        pendingBody: "We’re still preparing the first drafts.",
        missingTitle: "Nothing is ready for review yet.",
        missingBody: "Add or import holdings first.",
        connectedMissingBody: "Nothing is waiting for review right now. Write the first reason from the dashboard.",
        failedTitle: "Drafting needs a manual pass.",
        failedBody: "We couldn’t draft these automatically. Write the first one from the dashboard.",
        doneLine: "Monitoring starts tonight.",
        accept: "Keep this draft →",
        edit: "Reshape on position page",
        dismiss: "Reject this draft",
      };

  const updateDraft = (draft_id: string, patch: Partial<DraftWithState>) =>
    setDrafts((prev) => prev.map((d) => (d.draft_id === draft_id ? { ...d, ...patch } : d)));

  const handleActivate = async (d: DraftWithState) => {
    if (!d.thesis_id) return;
    updateDraft(d.draft_id, { activating: true });
    try {
      await api.post(`/api/onboarding/drafts/${d.draft_id}/review`, { action: "keep" });
      updateDraft(d.draft_id, { status: "reviewed", activating: false, reviewOutcome: "kept" });
    } catch {
      updateDraft(d.draft_id, { activating: false });
    }
  };

  const handleDismiss = async (d: DraftWithState) => {
    if (!d.thesis_id) return;
    updateDraft(d.draft_id, { dismissing: true });
    try {
      await api.post(`/api/onboarding/drafts/${d.draft_id}/review`, { action: "dismiss" });
      updateDraft(d.draft_id, { status: "reviewed", dismissing: false, reviewOutcome: "dismissed" });
    } catch {
      updateDraft(d.draft_id, { dismissing: false });
    }
  };

  const activeDrafts = drafts.filter((d) => d.status === "ready");
  const reviewedCount = drafts.filter((d) => d.status === "reviewed").length;
  const allDone = activeDrafts.length === 0 && drafts.length > 0;
  const keptDrafts = drafts.filter((d) => d.status === "reviewed" && d.reviewOutcome === "kept");
  const firstKeptDraft = keptDrafts[0] ?? null;
  const emptyStateVariant = pendingDraftCount > 0 ? "pending" : failedDraftCount > 0 ? "failed" : "missing";
  const portfolioConnected = onboardingState?.portfolio_connected ?? false;

  return (
    <AuthGuard>
      <div className="product-shell">
        <div className="product-shell-glow" />
        <div className="product-main min-h-screen px-4 py-6 sm:px-8">
          <div className="mx-auto max-w-5xl space-y-5">
            <div className="product-panel flex items-center justify-between gap-4 border border-border/60 bg-background/82 px-4 py-3 sm:px-5">
              <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                penKeep
              </span>
              <Link
                href="/dashboard"
                className="inline-flex items-center border border-border/60 bg-background/72 px-3 py-2 font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground transition-colors hover:border-border hover:text-foreground"
              >
                Skip to dashboard
              </Link>
            </div>

            <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_18rem]">
              <section className="space-y-5">
                <div className="product-panel border border-border/70 bg-[linear-gradient(180deg,rgba(163,126,79,0.06),rgba(255,255,255,0.96))] p-6 sm:p-8">
                  <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_15rem]">
                    <div className="space-y-3">
                      <span className="font-mono text-[10px] uppercase tracking-[0.24em] text-primary block">
                        Draft review
                      </span>
                      <h1 className="font-display italic text-[2.3rem] leading-tight text-foreground tracking-tight">
                        {copy.titleLine1}<br />{copy.titleLine2}
                      </h1>
                      <p className="max-w-xl text-sm leading-relaxed text-muted-foreground">
                        {copy.subtitle}
                      </p>
                    </div>

                    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1">
                      <div className="border border-border/60 bg-background/70 p-4">
                        <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                          Ready now
                        </p>
                        <p className="mt-2 font-display text-[1.5rem] italic leading-none text-foreground">
                          {activeDrafts.length}
                        </p>
                      </div>
                      <div className="border border-border/60 bg-background/70 p-4">
                        <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                          {pendingDraftCount > 0 ? "Generating" : "Reviewed"}
                        </p>
                        <p className="mt-2 font-display text-[1.5rem] italic leading-none text-foreground">
                          {pendingDraftCount > 0 ? pendingDraftCount : reviewedCount}
                        </p>
                      </div>
                    </div>
                  </div>
                </div>

                {pageLoading && (
                  <div className="space-y-4">
                    {[1, 2, 3].map((i) => (
                      <div key={i} className="product-panel h-44 animate-pulse bg-muted/20" />
                    ))}
                  </div>
                )}

                {!pageLoading && drafts.length === 0 && (
                  <div className="product-panel border border-border/60 bg-background/82 p-8 text-center space-y-4">
                    <p className="font-display italic text-[1.5rem] leading-tight text-foreground">
                      {emptyStateVariant === "pending"
                        ? copy.pendingTitle
                        : emptyStateVariant === "failed"
                          ? copy.failedTitle
                          : copy.missingTitle}
                    </p>
                    <p className="mx-auto max-w-md text-sm leading-relaxed text-muted-foreground">
                      {emptyStateVariant === "pending"
                        ? copy.pendingBody
                        : emptyStateVariant === "failed"
                          ? copy.failedBody
                          : portfolioConnected
                            ? copy.connectedMissingBody
                            : copy.missingBody}
                    </p>
                    {pendingDraftCount > 0 && (
                      <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground/70">
                        Refreshes automatically
                      </p>
                    )}
                    <div className="flex flex-wrap items-center justify-center gap-3 pt-1">
                      <Link
                        href="/dashboard?source=review_drafts"
                        className="inline-block bg-primary text-primary-foreground px-6 py-2.5 text-sm font-mono hover:bg-primary/90 transition-colors"
                      >
                        Open dashboard
                      </Link>
                      {emptyStateVariant !== "pending" && !portfolioConnected && (
                        <Link
                          href="/connect"
                          className="inline-block border border-border px-6 py-2.5 text-sm font-mono text-foreground/70 hover:text-foreground hover:border-foreground/30 transition-colors"
                        >
                          Import holdings
                        </Link>
                      )}
                    </div>
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
                        acceptLabel={copy.accept}
                        editLabel={copy.edit}
                        dismissLabel={copy.dismiss}
                        onActivate={() => handleActivate(d)}
                        onDismiss={() => handleDismiss(d)}
                        onEdit={() => router.push(`/dashboard/positions/${d.ticker}?source=review_drafts`)}
                      />
                    </motion.div>
                  ))}
                </div>

                {allDone && (
                  <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.4 }}
                    className="product-panel border border-emerald-500/20 bg-[linear-gradient(180deg,rgba(16,185,129,0.08),rgba(255,255,255,0.95))] p-6 sm:p-7 space-y-6"
                  >
                    <div className="space-y-1">
                      <span className="font-mono text-[10px] uppercase tracking-[0.24em] text-primary">
                        Done
                      </span>
                      <p className="font-display italic text-[1.6rem] leading-tight text-foreground">
                        {reviewedCount === 1
                          ? "1 position now has a working case."
                          : `${reviewedCount} positions now have working cases.`}
                      </p>
                      <p className="text-sm text-muted-foreground">
                        {copy.doneLine}
                      </p>
                    </div>
                    <div className="flex flex-wrap items-center gap-3">
                      {firstKeptDraft && (
                        <Link
                          href={`/dashboard/positions/${firstKeptDraft.ticker}?source=review_drafts`}
                          className="inline-block bg-primary text-primary-foreground px-8 py-3 text-sm font-mono tracking-wide hover:bg-primary/90 transition-colors"
                        >
                          See {firstKeptDraft.ticker} first
                        </Link>
                      )}
                      <Link
                        href="/dashboard?source=review_drafts"
                        className="inline-block border border-border px-6 py-3 text-sm font-mono tracking-wide text-foreground/70 hover:text-foreground hover:border-foreground/30 transition-colors"
                      >
                        Open dashboard
                      </Link>
                    </div>
                  </motion.div>
                )}

                {reviewedCount > 0 && !allDone && (
                  <div className="pt-1">
                    <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                      Reviewed ({reviewedCount})
                    </p>
                  </div>
                )}
              </section>

              <aside className="space-y-4">
                <div className="product-panel border border-border/60 bg-background/82 p-5">
                  <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                    What you are deciding
                  </p>
                  <p className="mt-2 font-sans text-sm leading-relaxed text-foreground/80">
                    Keep the draft if the shape is right. Fix it on the position page if it is not.
                  </p>
                </div>
                <div className="product-panel border border-border/60 bg-background/82 p-5">
                  <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                    Goal
                  </p>
                  <p className="mt-2 font-sans text-sm leading-relaxed text-foreground/80">
                    Get each important position to a workable case quickly.
                  </p>
                </div>
              </aside>
            </div>
          </div>
        </div>
      </div>
    </AuthGuard>
  );
}

function DraftCard({
  draft,
  acceptLabel,
  editLabel,
  dismissLabel,
  onActivate,
  onDismiss,
  onEdit,
}: {
  draft: DraftWithState;
  acceptLabel: string;
  editLabel: string;
  dismissLabel: string;
  onActivate: () => void;
  onDismiss: () => void;
  onEdit: () => void;
}) {
  return (
    <div className="product-panel overflow-hidden">
      <div className="border-b border-border/60 px-5 py-4 flex items-center justify-between gap-4 bg-muted/25">
        <div className="flex items-baseline gap-2.5">
          <span className="font-display text-xl font-bold text-foreground">{draft.ticker}</span>
          <span className="text-muted-foreground text-xs">{draft.name}</span>
        </div>
        <span className="font-mono text-[9px] uppercase tracking-[0.2em] text-primary border border-primary/30 px-2 py-0.5">
          AI draft
        </span>
      </div>

      <div className="px-5 py-5 space-y-4">
        <div className="border border-border/60 bg-muted/20 px-3 py-2.5">
          <p className="font-mono text-[9px] uppercase tracking-[0.18em] text-muted-foreground">
            Review standard
          </p>
          <p className="mt-1 text-sm text-foreground/80 leading-relaxed">
            Keep this if the shape is right. Rewrite it on the position page if it is not.
          </p>
        </div>
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

      <div className="border-t border-border/60 px-5 py-4 flex flex-wrap items-center gap-3 bg-background/60">
        <Button
          onClick={onActivate}
          disabled={draft.activating || draft.dismissing}
          className="min-w-[13rem]"
        >
          {draft.activating ? "Activating…" : acceptLabel}
        </Button>
        <button
          onClick={onEdit}
          className="inline-flex items-center border border-border/60 bg-background/72 px-3 py-2 font-mono text-[10px] uppercase tracking-[0.14em] text-foreground/72 transition-colors hover:border-border hover:text-foreground"
        >
          {editLabel}
        </button>
        <button
          onClick={onDismiss}
          disabled={draft.activating || draft.dismissing}
          className="inline-flex items-center border border-border/60 bg-background/72 px-3 py-2 font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground transition-colors hover:border-border hover:text-foreground disabled:opacity-40 sm:ml-auto"
        >
          {draft.dismissing ? "Dismissing…" : dismissLabel}
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
