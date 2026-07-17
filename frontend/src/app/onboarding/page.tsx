"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import { AuthGuard } from "@/components/layout/auth-guard";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { getErrorMessage } from "@/lib/errors";
import type { Holding, HoldingContext, Thesis } from "@/types";

type Step = "QUESTION_1" | "QUESTION_2";
type InvestorProfile = "thesis_driven" | "hearsay_driven";

const PROFILE_CONTENT: Record<
  InvestorProfile,
  {
    q1: string;
    q2: string;
    q1Placeholder: string;
    q2Placeholder: string;
  }
> = {
  thesis_driven: {
    q1: "What is the core thesis behind owning this position?",
    q2: "What specific evidence would tell you that thesis is breaking?",
    q1Placeholder:
      "e.g. This is an AI infrastructure leader with pricing power, durable demand, and a software moat that should keep returns above peers…",
    q2Placeholder:
      "e.g. Data center demand weakens, gross margins compress for multiple quarters, or a credible competitor breaks the software lock-in…",
  },
  hearsay_driven: {
    q1: "What made this stock interesting enough to buy in the first place?",
    q2: "What would make you admit the original idea is no longer working?",
    q1Placeholder:
      "e.g. Everyone was talking about AI demand, the numbers looked strong, and it felt like this company was in the right place at the right time…",
    q2Placeholder:
      "e.g. Revenue growth cools sharply, management guidance weakens, or the whole story starts depending more on hype than business results…",
  },
};

const STORAGE_KEY = "copilot_onboarding_wizard";
const STEPS: Step[] = ["QUESTION_1", "QUESTION_2"];

interface WizardState {
  holdingId: string | null;
  investorProfile: InvestorProfile;
  answer1: string;
  answer2: string;
}

const emptyState: WizardState = {
  holdingId: null,
  investorProfile: "thesis_driven",
  answer1: "",
  answer2: "",
};

function loadState(): WizardState {
  if (typeof window === "undefined") return emptyState;
  try {
    const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "{}") as Partial<WizardState>;
    return {
      holdingId: typeof parsed.holdingId === "string" ? parsed.holdingId : null,
      investorProfile: parsed.investorProfile === "hearsay_driven" ? "hearsay_driven" : "thesis_driven",
      answer1: typeof parsed.answer1 === "string" ? parsed.answer1 : "",
      answer2: typeof parsed.answer2 === "string" ? parsed.answer2 : "",
    };
  } catch {
    return emptyState;
  }
}

function saveState(state: WizardState) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {}
}

function clearState() {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {}
}

function inferInitialStep(state: WizardState): Step {
  return state.answer1.trim() ? "QUESTION_2" : "QUESTION_1";
}

const stepVariants = {
  enter: { opacity: 0, y: 18 },
  center: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -12 },
};

function WizardInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryHoldingId = searchParams.get("holding_id");
  const initialState = (() => {
    const stored = loadState();
    return queryHoldingId ? { ...stored, holdingId: queryHoldingId } : stored;
  })();

  const [step, setStep] = useState<Step>(() => inferInitialStep(initialState));
  const [wizardState, setWizardState] = useState<WizardState>(initialState);
  const [holding, setHolding] = useState<HoldingContext | null>(null);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [drafting, setDrafting] = useState(false);

  const profileContent = PROFILE_CONTENT[wizardState.investorProfile];
  const currentStepIndex = STEPS.indexOf(step);

  useEffect(() => {
    saveState(wizardState);
  }, [wizardState]);

  useEffect(() => {
    api
      .get<{ investor_profile: InvestorProfile | null }>("/api/onboarding/state")
      .then((state) => {
        if (state.investor_profile) {
          setWizardState((previous) => ({ ...previous, investorProfile: state.investor_profile! }));
        }
      })
      .catch(() => null);
  }, []);

  useEffect(() => {
    if (wizardState.holdingId) return;
    Promise.all([
      api.get<Holding[]>("/api/portfolio/holdings"),
      api.get<Thesis[]>("/api/theses/current"),
    ])
      .then(([holdings, theses]) => {
        const draftedHoldingIds = new Set(theses.map((thesis) => thesis.holding_id));
        const nextHolding = holdings
          .filter((item) => !draftedHoldingIds.has(item.id))
          .sort((a, b) => (b.current_value ?? 0) - (a.current_value ?? 0))[0];

        if (!nextHolding) {
          router.replace("/dashboard");
          return;
        }
        setWizardState((previous) => ({ ...previous, holdingId: nextHolding.id }));
      })
      .catch(() => router.replace("/dashboard"));
  }, [router, wizardState.holdingId]);

  useEffect(() => {
    if (!wizardState.holdingId) return;
    api
      .get<HoldingContext>(`/api/onboarding/context/${wizardState.holdingId}`)
      .then(setHolding)
      .catch((cause) => {
        if (cause instanceof Error && cause.message === "Holding not found") {
          setHolding(null);
          setStep("QUESTION_1");
          setWizardState((previous) => ({
            ...previous,
            holdingId: null,
            answer1: "",
            answer2: "",
          }));
        }
      });
  }, [wizardState.holdingId]);

  const goTo = (nextStep: Step) => {
    setError("");
    setStep(nextStep);
  };

  const handleSkip = async () => {
    await api.post("/api/onboarding/skip").catch(() => null);
    clearState();
    router.push("/dashboard");
  };

  const handleSave = async () => {
    if (!wizardState.holdingId || !holding) return;
    if (wizardState.answer1.trim().length < 5 || wizardState.answer2.trim().length < 5) return;

    setSaving(true);
    setError("");
    try {
      await api.post<Thesis>("/api/theses", {
        holding_id: wizardState.holdingId,
        thesis_kind: "company",
        why_own_it: wizardState.answer1.trim(),
        must_remain_true: null,
        what_would_change_my_mind: wizardState.answer2.trim(),
        status: "active",
        confidence: "medium",
        review_cadence_days: 30,
        source: "user",
      });
      await api.post("/api/onboarding/complete").catch(() => null);
      clearState();
      router.push(`/dashboard/positions/${holding.ticker}?source=onboarding`);
    } catch (cause) {
      setError(getErrorMessage(cause, "We couldn't save this record yet. Please try again."));
    } finally {
      setSaving(false);
    }
  };

  const handleDraftForMe = async () => {
    if (!holding) return;
    setDrafting(true);
    setError("");
    try {
      const draft = await api.post<{ why_own_it: string; what_would_change_my_mind: string }>(
        "/api/theses/draft",
        { ticker: holding.ticker },
      );
      setWizardState((previous) => ({
        ...previous,
        answer1: previous.answer1.trim() ? previous.answer1 : draft.why_own_it,
        answer2: previous.answer2.trim() ? previous.answer2 : draft.what_would_change_my_mind,
      }));
    } catch (cause) {
      setError(getErrorMessage(cause, "Couldn't draft a starting point — write a line yourself to continue."));
    } finally {
      setDrafting(false);
    }
  };

  const renderQuestion = (
    key: "answer1" | "answer2",
    question: string,
    placeholder: string,
    onNext: () => void,
  ) => (
    <motion.div
      key={key}
      variants={stepVariants}
      initial="enter"
      animate="center"
      exit="exit"
      transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
      className="space-y-8"
    >
      <div className="space-y-3">
        <span className="font-mono text-[10px] uppercase tracking-[0.3em] text-primary">
          Question {key === "answer1" ? "01" : "02"}{holding ? ` — ${holding.ticker}` : ""}
        </span>
        <h1 className="font-display italic text-[1.9rem] leading-[1.2] text-foreground tracking-tight">
          {question}
        </h1>
      </div>

      <div className="border border-border/70 bg-background/55 p-4 sm:p-5">
        <textarea
          value={wizardState[key]}
          onChange={(event) => setWizardState((previous) => ({ ...previous, [key]: event.target.value }))}
          placeholder={placeholder}
          rows={6}
          autoFocus
          className="w-full resize-none bg-transparent text-base leading-relaxed text-foreground outline-none placeholder:text-muted-foreground/50 font-sans"
        />
        <div className="mt-3 flex items-center justify-between gap-4 border-t border-border/50 pt-3">
          <span className="font-sans text-xs text-muted-foreground">
            Write the version you would want to defend later.
          </span>
          <span className="font-mono text-[10px] text-muted-foreground/40">
            {wizardState[key].length} chars
          </span>
        </div>
      </div>

      {error && <p className="font-mono text-sm text-red-600">{error}</p>}

      <div className="space-y-3">
        <div className="flex items-center gap-4">
          <Button
            onClick={onNext}
            disabled={!holding || wizardState[key].trim().length < 5}
            loading={key === "answer2" && saving}
          >
            {key === "answer2" ? "Save record" : "Continue"}
          </Button>
          <button
            onClick={handleSkip}
            className="font-mono text-xs text-muted-foreground underline underline-offset-4 transition-colors hover:text-foreground"
          >
            Skip for now
          </button>
        </div>
        {wizardState[key].trim().length < 10 && (
          <button
            onClick={handleDraftForMe}
            disabled={drafting || !holding}
            className="flex items-center gap-2 font-mono text-sm text-primary transition-colors hover:text-primary/80 disabled:opacity-50"
          >
            <span className="text-base leading-none">↳</span>
            {drafting ? "Drafting a starting point…" : "Not sure where to start? Draft one for me"}
          </button>
        )}
      </div>
    </motion.div>
  );

  const holdingValueLabel = holding?.current_value
    ? `£${holding.current_value.toLocaleString("en-GB", { maximumFractionDigits: 0 })}`
    : "Value unavailable";
  const sidebarCards = step === "QUESTION_1"
    ? [
        {
          eyebrow: holding ? `${holding.ticker} · ${holdingValueLabel}` : "Your position",
          title: "Write the positive case in your own words.",
          body: holding ? `${holding.name}${holding.sector ? ` · ${holding.sector}` : ""}` : "Loading position…",
        },
        {
          eyebrow: "Tip",
          title: "Direction beats polish.",
          body: "Get the real idea down first. You can sharpen the sentence later.",
        },
      ]
    : [
        {
          eyebrow: "Question 2",
          title: "Define what would break the case.",
          body: "This is the part that keeps the record useful once the stock starts moving.",
        },
      ];

  return (
    <div className="product-shell">
      <div className="product-shell-glow" />
      <div className="product-main min-h-screen px-4 py-6 sm:px-8">
        <div className="mx-auto max-w-5xl space-y-5">
          <div className="product-panel product-panel-muted flex items-center justify-between gap-4 px-4 py-3 sm:px-5">
            <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
              penKeep
            </span>
            <div className="flex items-center gap-4">
              <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground tabular-nums">
                0{currentStepIndex + 1} / 0{STEPS.length}
              </span>
              <div className="flex gap-1">
                {STEPS.map((item, index) => (
                  <div key={item} className={`h-1 w-6 ${index <= currentStepIndex ? "bg-primary" : "bg-border"}`} />
                ))}
              </div>
            </div>
          </div>

          <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_18rem]">
            <section className="min-w-0">
              <div className="product-panel product-panel-muted p-6 sm:p-8">
                <AnimatePresence mode="wait">
                  {step === "QUESTION_1"
                    ? renderQuestion(
                        "answer1",
                        profileContent.q1,
                        profileContent.q1Placeholder,
                        () => goTo("QUESTION_2"),
                      )
                    : renderQuestion(
                        "answer2",
                        profileContent.q2,
                        profileContent.q2Placeholder,
                        handleSave,
                      )}
                </AnimatePresence>
              </div>
            </section>

            <aside className="space-y-4">
              {sidebarCards.map((card) => (
                <SidebarPanel key={card.title} {...card} />
              ))}
            </aside>
          </div>
        </div>
      </div>
    </div>
  );
}

function SidebarPanel({ eyebrow, title, body }: { eyebrow: string; title: string; body: string }) {
  return (
    <div className="product-panel p-5">
      <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">{eyebrow}</p>
      <p className="mt-2 font-display text-[1.3rem] italic leading-tight text-foreground">{title}</p>
      <p className="mt-2 font-sans text-sm leading-relaxed text-muted-foreground">{body}</p>
    </div>
  );
}

export default function OnboardingPage() {
  return (
    <AuthGuard>
      <Suspense>
        <WizardInner />
      </Suspense>
    </AuthGuard>
  );
}
