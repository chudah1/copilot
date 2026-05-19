"use client";

import { useEffect, useState, useCallback, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import { AuthGuard } from "@/components/layout/auth-guard";
import { api } from "@/lib/api";
import { getErrorMessage } from "@/lib/errors";
import type { DraftStatus, HoldingContext, SynthesisResponse } from "@/types";

// ---------------------------------------------------------------------------
// Step machine
// ---------------------------------------------------------------------------

type Step =
  | "WELCOME"
  | "POSITION_FOCUS"
  | "QUESTION_1"
  | "QUESTION_2"
  | "SYNTHESISING"
  | "REVIEW"
  | "DONE";

const QUESTIONS = {
  q1: "Why did you buy it? What's the main reason you own this position?",
  q2: "What would have to happen for you to sell it?",
};

const STORAGE_KEY = "copilot_onboarding_wizard";

interface WizardState {
  holdingId: string | null;
  answer1: string;
  answer2: string;
  synthesisResult: SynthesisResponse | null;
}

function loadState(): WizardState {
  if (typeof window === "undefined")
    return { holdingId: null, answer1: "", answer2: "", synthesisResult: null };
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return JSON.parse(raw);
  } catch {}
  return { holdingId: null, answer1: "", answer2: "", synthesisResult: null };
}

function saveState(s: WizardState) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(s));
  } catch {}
}

function clearState() {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {}
}

// ---------------------------------------------------------------------------
// Step counter display
// ---------------------------------------------------------------------------

const STEP_ORDER: Step[] = [
  "WELCOME",
  "POSITION_FOCUS",
  "QUESTION_1",
  "QUESTION_2",
  "SYNTHESISING",
  "REVIEW",
  "DONE",
];
const VISIBLE_STEPS = ["POSITION_FOCUS", "QUESTION_1", "QUESTION_2"] as const;

// ---------------------------------------------------------------------------
// Transition variants
// ---------------------------------------------------------------------------

const stepVariants = {
  enter: { opacity: 0, y: 18 },
  center: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -12 },
};

// ---------------------------------------------------------------------------
// Inner wizard (needs useSearchParams)
// ---------------------------------------------------------------------------

function WizardInner() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [step, setStep] = useState<Step>("WELCOME");
  const [wizardState, setWizardState] = useState<WizardState>(() => loadState());
  const [holding, setHolding] = useState<HoldingContext | null>(null);
  const [error, setError] = useState("");
  const [loadingHolding, setLoadingHolding] = useState(false);

  // Sync wizardState to localStorage
  useEffect(() => {
    saveState(wizardState);
  }, [wizardState]);

  // On mount: determine starting holding
  useEffect(() => {
    const qHoldingId = searchParams.get("holding_id");
    const source = searchParams.get("source");

    if (qHoldingId) {
      setWizardState((prev) => ({ ...prev, holdingId: qHoldingId }));
    } else if (!wizardState.holdingId) {
      // Pick the top undrafted holding from draft status
      api
        .get<DraftStatus>("/api/portfolio/draft-status")
        .then((ds) => {
          const ready = ds.drafts.find((d) => d.status === "ready");
          const pending = ds.drafts.find((d) => d.status === "pending");
          const chosen = ready || pending;
          if (chosen) {
            setWizardState((prev) => ({ ...prev, holdingId: chosen.holding_id }));
          } else {
            // No drafts at all — redirect to dashboard
            router.replace("/dashboard");
          }
        })
        .catch(() => router.replace("/dashboard"));
    }

    // Resume to the furthest completed step
    if (wizardState.synthesisResult) {
      setStep("REVIEW");
    } else if (wizardState.answer2 || wizardState.answer1) {
      setStep("QUESTION_2");
    }
    // Run once on mount — wizardState initialised synchronously from localStorage
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Fetch holding context whenever holdingId is set
  useEffect(() => {
    if (!wizardState.holdingId) return;
    setLoadingHolding(true);
    api
      .get<HoldingContext>(`/api/onboarding/context/${wizardState.holdingId}`)
      .then((h) => setHolding(h))
      .catch(() => {})
      .finally(() => setLoadingHolding(false));
  }, [wizardState.holdingId]);

  const goTo = (s: Step) => {
    setError("");
    setStep(s);
  };

  const handleSkip = async () => {
    try {
      await api.post("/api/onboarding/skip");
    } catch {}
    clearState();
    router.push("/dashboard");
  };

  const handleSynthesize = async () => {
    if (!wizardState.holdingId || !holding) return;
    goTo("SYNTHESISING");
    setError("");
    try {
      const result = await api.post<SynthesisResponse>("/api/onboarding/synthesize", {
        holding_id: wizardState.holdingId,
        question1: QUESTIONS.q1,
        answer1: wizardState.answer1,
        question2: QUESTIONS.q2,
        answer2: wizardState.answer2,
      });
      setWizardState((prev) => ({ ...prev, synthesisResult: result }));
      goTo("REVIEW");
    } catch (e) {
      setError(getErrorMessage(e, "Something went wrong. Please try again."));
      goTo("QUESTION_2");
    }
  };

  const handleComplete = async () => {
    try {
      await api.post("/api/onboarding/complete");
    } catch {}
    clearState();
    router.push("/dashboard");
  };

  const visibleStep = VISIBLE_STEPS.indexOf(step as (typeof VISIBLE_STEPS)[number]);
  const stepDisplay =
    visibleStep >= 0 ? `0${visibleStep + 1} / 0${VISIBLE_STEPS.length}` : null;

  // ---------------------------------------------------------------------------
  // Step renders
  // ---------------------------------------------------------------------------

  const renderWelcome = () => (
    <motion.div
      key="welcome"
      variants={stepVariants}
      initial="enter"
      animate="center"
      exit="exit"
      transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
      className="space-y-10"
    >
      <div className="space-y-4">
        <span className="font-mono text-[10px] uppercase tracking-[0.3em] text-primary">
          Getting started
        </span>
        <h1 className="font-display italic text-[2.75rem] leading-[1.1] text-foreground tracking-tight">
          Let&rsquo;s talk about<br />why you invest.
        </h1>
        <p className="text-base text-muted-foreground leading-relaxed max-w-sm">
          We&rsquo;ll ask you two simple questions about one of your positions.
          Your answers become a thesis — something we can monitor and review with you.
        </p>
      </div>

      <div className="space-y-3 border-l-2 border-primary/30 pl-4">
        {[
          "One position, two questions — takes 2 minutes.",
          "AI turns your answers into a structured thesis.",
          "We monitor it. You get a digest every week.",
        ].map((line, i) => (
          <p key={i} className="text-sm text-foreground/70 font-mono">
            {line}
          </p>
        ))}
      </div>

      <div className="flex items-center gap-6 pt-2">
        <button
          onClick={() => goTo("POSITION_FOCUS")}
          className="bg-primary text-primary-foreground px-8 py-3 text-sm font-mono tracking-wide hover:bg-primary/90 transition-colors"
        >
          Begin →
        </button>
        <button
          onClick={handleSkip}
          className="text-xs text-muted-foreground hover:text-foreground transition-colors font-mono underline underline-offset-4"
        >
          Skip for now
        </button>
      </div>
    </motion.div>
  );

  const renderPositionFocus = () => (
    <motion.div
      key="position"
      variants={stepVariants}
      initial="enter"
      animate="center"
      exit="exit"
      transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
      className="space-y-8"
    >
      <div className="space-y-2">
        <span className="font-mono text-[10px] uppercase tracking-[0.3em] text-primary">
          Position focus
        </span>
        <h2 className="font-display italic text-[2rem] leading-tight text-foreground">
          Let&rsquo;s talk about this position.
        </h2>
      </div>

      {loadingHolding ? (
        <div className="h-24 flex items-center">
          <span className="font-mono text-xs text-muted-foreground animate-pulse">
            Loading position…
          </span>
        </div>
      ) : holding ? (
        <div className="border border-border p-6 space-y-4">
          <div className="flex items-baseline gap-3">
            <span className="font-display text-[2.5rem] font-bold text-foreground leading-none">
              {holding.ticker}
            </span>
            <span className="text-muted-foreground text-sm">{holding.name}</span>
          </div>
          <div className="grid grid-cols-3 gap-px border border-border">
            {[
              {
                label: "Value",
                value: holding.current_value
                  ? `£${holding.current_value.toLocaleString("en-GB", { maximumFractionDigits: 0 })}`
                  : "—",
              },
              {
                label: "Shares",
                value: holding.quantity.toFixed(4),
              },
              {
                label: "Sector",
                value: holding.sector || "—",
              },
            ].map(({ label, value }) => (
              <div key={label} className="bg-muted/40 p-3">
                <div className="font-mono text-[9px] uppercase tracking-[0.2em] text-muted-foreground mb-1">
                  {label}
                </div>
                <div className="text-sm font-medium text-foreground">{value}</div>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      <div className="flex items-center gap-6">
        <button
          onClick={() => goTo("QUESTION_1")}
          disabled={!holding}
          className="bg-primary text-primary-foreground px-8 py-3 text-sm font-mono tracking-wide hover:bg-primary/90 transition-colors disabled:opacity-40"
        >
          Continue →
        </button>
        <button
          onClick={handleSkip}
          className="text-xs text-muted-foreground hover:text-foreground transition-colors font-mono underline underline-offset-4"
        >
          Skip
        </button>
      </div>
    </motion.div>
  );

  const renderQuestion = (
    qKey: "answer1" | "answer2",
    question: string,
    placeholder: string,
    onNext: () => void,
    stepLabel: string
  ) => (
    <motion.div
      key={qKey}
      variants={stepVariants}
      initial="enter"
      animate="center"
      exit="exit"
      transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
      className="space-y-8"
    >
      <div className="space-y-3">
        <span className="font-mono text-[10px] uppercase tracking-[0.3em] text-primary">
          {stepLabel}
          {holding ? ` — ${holding.ticker}` : ""}
        </span>
        <h2 className="font-display italic text-[1.9rem] leading-[1.2] text-foreground tracking-tight">
          {question}
        </h2>
      </div>

      <div className="relative">
        <textarea
          value={wizardState[qKey]}
          onChange={(e) =>
            setWizardState((prev) => ({ ...prev, [qKey]: e.target.value }))
          }
          placeholder={placeholder}
          rows={5}
          autoFocus
          className="w-full bg-transparent border-0 border-b-2 border-foreground/20 focus:border-primary outline-none resize-none text-foreground placeholder:text-muted-foreground/50 text-base leading-relaxed py-3 transition-colors font-sans"
        />
        <div className="absolute bottom-0 right-0 pb-1">
          <span className="font-mono text-[10px] text-muted-foreground/40">
            {wizardState[qKey].length} chars
          </span>
        </div>
      </div>

      {error && (
        <p className="text-sm text-red-600 font-mono">{error}</p>
      )}

      <div className="flex items-center gap-6">
        <button
          onClick={onNext}
          disabled={wizardState[qKey].trim().length < 5}
          className="bg-primary text-primary-foreground px-8 py-3 text-sm font-mono tracking-wide hover:bg-primary/90 transition-colors disabled:opacity-40"
        >
          Continue →
        </button>
        <button
          onClick={handleSkip}
          className="text-xs text-muted-foreground hover:text-foreground transition-colors font-mono underline underline-offset-4"
        >
          Skip for now
        </button>
      </div>
    </motion.div>
  );

  const renderSynthesising = () => (
    <motion.div
      key="synthesising"
      variants={stepVariants}
      initial="enter"
      animate="center"
      exit="exit"
      transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
      className="space-y-6"
    >
      <div className="space-y-3">
        <span className="font-mono text-[10px] uppercase tracking-[0.3em] text-primary animate-pulse">
          Building your thesis…
        </span>
        <h2 className="font-display italic text-[2rem] leading-tight text-foreground">
          Reading your answers.
        </h2>
        <p className="text-muted-foreground text-sm max-w-sm leading-relaxed">
          Turning what you said into a structured investment thesis
          {holding ? ` for ${holding.ticker}` : ""}.
        </p>
      </div>

      <div className="flex gap-1 pt-2">
        {[0, 1, 2, 3, 4].map((i) => (
          <motion.div
            key={i}
            className="h-0.5 w-8 bg-primary"
            animate={{ opacity: [0.2, 1, 0.2] }}
            transition={{
              duration: 1.2,
              repeat: Infinity,
              delay: i * 0.2,
              ease: "easeInOut",
            }}
          />
        ))}
      </div>
    </motion.div>
  );

  const renderReview = () => {
    const result = wizardState.synthesisResult;
    if (!result) return null;
    return (
      <motion.div
        key="review"
        variants={stepVariants}
        initial="enter"
        animate="center"
        exit="exit"
        transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
        className="space-y-8"
      >
        <div className="space-y-2">
          <span className="font-mono text-[10px] uppercase tracking-[0.3em] text-primary">
            Your thesis
            {holding ? ` — ${holding.ticker}` : ""}
          </span>
          <h2 className="font-display italic text-[2rem] leading-tight text-foreground">
            Here&rsquo;s what we captured.
          </h2>
          <p className="text-muted-foreground text-sm">
            This becomes your investment thesis. You can edit it any time on the position page.
          </p>
        </div>

        <div className="space-y-4">
          <ThesisBlock label="Why you own it" text={result.why_own_it} />
          <ThesisBlock label="Must remain true" text={result.must_remain_true} />
          <ThesisBlock label="What would change your mind" text={result.what_would_change_my_mind} />
        </div>

        {result.ai_summary && (
          <div className="border-l-2 border-primary/40 pl-4">
            <p className="text-sm text-foreground/70 italic font-sans leading-relaxed">
              &ldquo;{result.ai_summary}&rdquo;
            </p>
          </div>
        )}

        <div className="flex items-center gap-6 pt-2">
          <button
            onClick={handleComplete}
            className="bg-primary text-primary-foreground px-8 py-3 text-sm font-mono tracking-wide hover:bg-primary/90 transition-colors"
          >
            Go to dashboard →
          </button>
          <button
            onClick={() => router.push(`/api/onboarding/review-drafts`)}
            className="text-xs text-muted-foreground hover:text-foreground transition-colors font-mono underline underline-offset-4"
          >
            Review all drafts
          </button>
        </div>
      </motion.div>
    );
  };

  // ---------------------------------------------------------------------------
  // Layout
  // ---------------------------------------------------------------------------

  return (
    <div className="min-h-screen bg-background">
      {/* Header rule */}
      <div className="border-b border-border/60 px-6 py-4 flex items-center justify-between">
        <span className="font-mono text-xs text-muted-foreground tracking-wide">
          Copilot Investor
        </span>
        <div className="flex items-center gap-4">
          {stepDisplay && (
            <span className="font-mono text-xs text-muted-foreground tabular-nums">
              {stepDisplay}
            </span>
          )}
          {/* Step pills */}
          {step !== "WELCOME" && step !== "DONE" && (
            <div className="flex gap-1">
              {VISIBLE_STEPS.map((s) => (
                <div
                  key={s}
                  className={`h-1 w-6 transition-colors ${
                    STEP_ORDER.indexOf(step) >= STEP_ORDER.indexOf(s)
                      ? "bg-primary"
                      : "bg-border"
                  }`}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Main content */}
      <div className="flex items-start justify-center pt-16 pb-24 px-6">
        <div className="w-full max-w-lg">
          <AnimatePresence mode="wait">
            {step === "WELCOME" && renderWelcome()}
            {step === "POSITION_FOCUS" && renderPositionFocus()}
            {step === "QUESTION_1" &&
              renderQuestion(
                "answer1",
                QUESTIONS.q1,
                "e.g. Strong AI infrastructure play, growing enterprise software segment with high switching costs…",
                () => goTo("QUESTION_2"),
                "Question 01"
              )}
            {step === "QUESTION_2" &&
              renderQuestion(
                "answer2",
                QUESTIONS.q2,
                "e.g. Revenue growth falls below 15% for two consecutive quarters, or a major competitor breaks their moat…",
                handleSynthesize,
                "Question 02"
              )}
            {step === "SYNTHESISING" && renderSynthesising()}
            {step === "REVIEW" && renderReview()}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Small sub-component
// ---------------------------------------------------------------------------

function ThesisBlock({ label, text }: { label: string; text: string }) {
  return (
    <div className="border border-border p-4 space-y-1">
      <div className="font-mono text-[9px] uppercase tracking-[0.25em] text-muted-foreground">
        {label}
      </div>
      <p className="text-sm text-foreground leading-relaxed">{text}</p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Exported page with Suspense (useSearchParams requires it in Next.js 15+)
// ---------------------------------------------------------------------------

export default function OnboardingPage() {
  return (
    <AuthGuard>
      <Suspense>
        <WizardInner />
      </Suspense>
    </AuthGuard>
  );
}
