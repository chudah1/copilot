"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { AuthGuard } from "@/components/layout/auth-guard";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { getErrorMessage } from "@/lib/errors";
import { formatCurrency } from "@/lib/utils";
import {
  EMPTY_WIZARD_STATE,
  resolveInitialWizardState,
  selectLargestUncoveredHolding,
  type InvestorProfile,
  type WizardState,
} from "@/lib/onboarding-wizard";
import type { Holding, HoldingContext, Thesis } from "@/types";

type Step = "QUESTION_1" | "QUESTION_2" | "ON_RECORD";

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

function loadState(): WizardState {
  if (typeof window === "undefined") return EMPTY_WIZARD_STATE;
  try {
    const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "{}") as Partial<WizardState>;
    return {
      holdingId: typeof parsed.holdingId === "string" ? parsed.holdingId : null,
      investorProfile: parsed.investorProfile === "hearsay_driven" ? "hearsay_driven" : "thesis_driven",
      answer1: typeof parsed.answer1 === "string" ? parsed.answer1 : "",
      answer2: typeof parsed.answer2 === "string" ? parsed.answer2 : "",
    };
  } catch {
    return EMPTY_WIZARD_STATE;
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

function WizardInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryHoldingId = searchParams.get("holding_id");
  const freshImport = searchParams.get("source") === "import";
  const initialState = resolveInitialWizardState(loadState(), {
    queryHoldingId,
    freshImport,
  });

  const [step, setStep] = useState<Step>(() => inferInitialStep(initialState));
  const [wizardState, setWizardState] = useState<WizardState>(initialState);
  const [holding, setHolding] = useState<HoldingContext | null>(null);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [drafting, setDrafting] = useState(false);
  const [displayName, setDisplayName] = useState("");
  const [leaving, setLeaving] = useState(false);

  const profileContent = PROFILE_CONTENT[wizardState.investorProfile];
  const currentStepIndex = step === "ON_RECORD" ? STEPS.length - 1 : STEPS.indexOf(step);

  useEffect(() => {
    saveState(wizardState);
  }, [wizardState]);

  useEffect(() => {
    if (!freshImport) return;
    const nextParams = new URLSearchParams(searchParams.toString());
    nextParams.delete("source");
    const query = nextParams.toString();
    router.replace(`/onboarding${query ? `?${query}` : ""}`, { scroll: false });
  }, [freshImport, router, searchParams]);

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
        const nextHolding = selectLargestUncoveredHolding(holdings, theses);

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
      setStep("ON_RECORD");
    } catch (cause) {
      setError(getErrorMessage(cause, "We couldn't save this record yet. Please try again."));
    } finally {
      setSaving(false);
    }
  };

  const handleEnterProduct = async () => {
    if (!holding) return;
    setLeaving(true);
    const name = displayName.trim();
    if (name) {
      // Best-effort — the greeting is a nicety, never a blocker.
      await api.put("/api/settings", { display_name: name }).catch(() => null);
    }
    router.push(`/dashboard/positions/${holding.ticker}?source=onboarding`);
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
    onNext: () => void | Promise<void>,
  ) => (
    <form
      key={key}
      onSubmit={(event) => {
        event.preventDefault();
        void onNext();
      }}
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
            type="submit"
            disabled={!holding || wizardState[key].trim().length < 5}
            loading={key === "answer2" && saving}
          >
            {key === "answer2" ? "Save record" : "Continue"}
          </Button>
          <button
            type="button"
            onClick={handleSkip}
            className="font-mono text-xs text-muted-foreground underline underline-offset-4 transition-colors hover:text-foreground"
          >
            Skip for now
          </button>
        </div>
        {wizardState[key].trim().length < 10 && (
          <button
            type="button"
            onClick={handleDraftForMe}
            disabled={drafting || !holding}
            className="flex items-center gap-2 font-mono text-sm text-primary transition-colors hover:text-primary/80 disabled:opacity-50"
          >
            <span className="text-base leading-none">↳</span>
            {drafting ? "Drafting a starting point…" : "Not sure where to start? Draft one for me"}
          </button>
        )}
      </div>
    </form>
  );

  const onRecordNextSteps =
    wizardState.investorProfile === "thesis_driven"
      ? [
          { label: "Reads the evidence", body: `Filings, news, and earnings for ${holding?.ticker ?? "your position"} get checked against the thesis you just wrote.` },
          { label: "Stays quiet", body: "No pings on ordinary price noise. You hear from us when an assumption is actually tested." },
          { label: "Keeps the record", body: "Every review and decision is kept next to the original thesis, so hindsight can't rewrite it." },
        ]
      : [
          { label: "Reads the evidence", body: `Filings, news, and earnings for ${holding?.ticker ?? "your position"} get checked against the reason you just wrote.` },
          { label: "Stays quiet", body: "No pings on ordinary price noise. You hear from us when the story is actually tested." },
          { label: "Keeps the record", body: "Every review and decision is kept next to the original reason, so hindsight can't rewrite it." },
        ];

  const renderOnRecord = () => (
    <div className="space-y-8">
      <div className="space-y-3">
        <span className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.3em] text-emerald-700">
          <span className="relative flex h-1.5 w-1.5">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-500 opacity-60" />
            <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-emerald-600" />
          </span>
          On record
        </span>
        <h1 className="font-display italic text-[1.9rem] leading-[1.2] text-foreground tracking-tight">
          {holding ? `Your reason for ${holding.ticker} is on record.` : "Your first reason is on record."}
        </h1>
        <p className="max-w-xl font-sans text-sm leading-relaxed text-foreground/75">
          penKeep is turning it into monitoring checks now. From here, three things happen:
        </p>
      </div>

      <div className="space-y-0 border-y border-border/50">
        {onRecordNextSteps.map((item, index) => (
          <div key={item.label} className="flex items-start gap-4 border-b border-border/40 py-4 last:border-b-0">
            <span className="font-mono text-[10px] text-muted-foreground/50 tabular-nums mt-0.5">
              0{index + 1}
            </span>
            <div className="min-w-0">
              <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                {item.label}
              </p>
              <p className="mt-1 font-sans text-sm leading-relaxed text-foreground/85">{item.body}</p>
            </div>
          </div>
        ))}
      </div>

      <div className="border border-border/70 bg-background/55 p-4 sm:p-5">
        <label htmlFor="display-name" className="font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground block">
          What should we call you? <span className="text-muted-foreground/50 normal-case tracking-normal">— optional</span>
        </label>
        <input
          id="display-name"
          type="text"
          value={displayName}
          onChange={(event) => setDisplayName(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") void handleEnterProduct();
          }}
          placeholder="First name or nickname"
          maxLength={40}
          autoFocus
          className="mt-3 w-full bg-transparent font-sans text-base text-foreground outline-none placeholder:text-muted-foreground/50"
        />
      </div>

      <Button onClick={() => void handleEnterProduct()} loading={leaving} disabled={!holding}>
        {holding ? `See ${holding.ticker} live` : "Open your dashboard"} →
      </Button>
    </div>
  );

  const holdingValueLabel = holding?.current_value
    ? formatCurrency(holding.current_value, holding.portfolio_currency ?? "GBP")
    : "Value unavailable";
  const sidebarCards = step === "ON_RECORD"
    ? [
        {
          eyebrow: "Why the record matters",
          title: "Six months from now, this page is the antidote to hindsight.",
          body: "Whatever the stock does, you'll know what you believed, what changed, and what you decided.",
        },
      ]
    : step === "QUESTION_1"
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
                {step === "ON_RECORD"
                  ? renderOnRecord()
                  : step === "QUESTION_1"
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
