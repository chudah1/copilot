"use client";

import { useEffect, useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import { AuthGuard } from "@/components/layout/auth-guard";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { buildOnboardingAutoConfirmPayload } from "@/lib/onboarding-decomposition";
import { getErrorMessage } from "@/lib/errors";
import type {
  CandidateSignal,
  GroundingResponse,
  Holding,
  HoldingContext,
  SynthesisResponse,
  ThesisDecompositionEnvelope,
  Thesis,
} from "@/types";

// ---------------------------------------------------------------------------
// Step machine
// ---------------------------------------------------------------------------

type Step =
  | "WELCOME"
  | "QUESTION_1"
  | "QUESTION_2"
  | "SYNTHESISING"
  | "CLIMB"
  | "REVIEW"
  | "DONE";

const SIGNAL_TYPE_LABEL: Record<CandidateSignal["signal_type"], string> = {
  price_move: "Price",
  revenue_growth: "Revenue",
  earnings_growth: "Earnings",
  news_watch: "Event",
};

type InvestorProfile = "thesis_driven" | "hearsay_driven";

const PROFILE_CONTENT: Record<
  InvestorProfile,
  {
    label: string;
    title: string;
    subtitle: string;
    welcomeLines: string[];
    q1: string;
    q2: string;
    q1Placeholder: string;
    q2Placeholder: string;
  }
> = {
  thesis_driven: {
    label: "I invest from a thesis",
    title: "You already have a view. Put it on paper.",
    subtitle:
      "Two questions, one position — then we watch for news that touches what you wrote.",
    welcomeLines: [
      "One position, two questions — about 2 minutes.",
      "We structure it without sanding off your wording.",
      "Alerts only when something touches what you said you believe.",
      "A steady check-in rhythm you can hold to, whether the tape is loud or quiet.",
    ],
    q1: "What is the core thesis behind owning this position?",
    q2: "What specific evidence would tell you that thesis is breaking?",
    q1Placeholder:
      "e.g. This is an AI infrastructure leader with pricing power, durable demand, and a software moat that should keep returns above peers…",
    q2Placeholder:
      "e.g. Data center demand weakens, gross margins compress for multiple quarters, or a credible competitor breaks the software lock-in…",
  },
  hearsay_driven: {
    label: "I often buy from tips, chatter, or momentum",
    title: "Tips and themes are fine. Still write the reason down.",
    subtitle:
      "No polished essay needed — just enough detail that you can tell later if the idea still works.",
    welcomeLines: [
      "One position, two questions — about 2 minutes.",
      "Start with what caught your eye, even if it was chatter or momentum.",
      "We turn a hunch into something you can test.",
      "Regular check-ins, so fear isn't the trigger.",
    ],
    q1: "What made this stock interesting enough to buy in the first place?",
    q2: "What would make you admit the original idea is no longer working?",
    q1Placeholder:
      "e.g. Everyone was talking about AI demand, the numbers looked strong, and it felt like this company was in the right place at the right time…",
    q2Placeholder:
      "e.g. Revenue growth cools sharply, management guidance weakens, or the whole story starts depending more on hype than business results…",
  },
};

const STORAGE_KEY = "copilot_onboarding_wizard";

interface WizardState {
  holdingId: string | null;
  investorProfile: InvestorProfile;
  answer1: string;
  answer2: string;
  synthesisResult: SynthesisResponse | null;
}

function loadState(): WizardState {
  if (typeof window === "undefined")
    return { holdingId: null, investorProfile: "thesis_driven", answer1: "", answer2: "", synthesisResult: null };
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      return { ...parsed, investorProfile: parsed.investorProfile ?? "thesis_driven" };
    }
  } catch {}
  return { holdingId: null, investorProfile: "thesis_driven", answer1: "", answer2: "", synthesisResult: null };
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

function inferInitialStep(state: WizardState): Step {
  if (state.answer2) return "QUESTION_2";
  if (state.answer1) return "QUESTION_2";
  return "QUESTION_1";
}

// ---------------------------------------------------------------------------
// Step counter display
// ---------------------------------------------------------------------------

const STEP_ORDER: Step[] = [
  "WELCOME",
  "QUESTION_1",
  "QUESTION_2",
  "SYNTHESISING",
  "CLIMB",
  "REVIEW",
  "DONE",
];
const VISIBLE_STEPS = ["QUESTION_1", "QUESTION_2"] as const;

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
  const queryHoldingId = searchParams.get("holding_id");
  const initialWizardState = (() => {
    const loaded = loadState();
    return queryHoldingId ? { ...loaded, holdingId: queryHoldingId } : loaded;
  })();

  const [step, setStep] = useState<Step>(() => inferInitialStep(initialWizardState));
  const [wizardState, setWizardState] = useState<WizardState>(() => initialWizardState);
  const [holding, setHolding] = useState<HoldingContext | null>(null);
  const [error, setError] = useState("");
  const [savingThesis, setSavingThesis] = useState(false);
  const [groundingResult] = useState<GroundingResponse | null>(null);
  const [selectedSignalIdx, setSelectedSignalIdx] = useState<Set<number>>(new Set());
  const [draftingForMe, setDraftingForMe] = useState(false);
  const profile = wizardState.investorProfile;
  const profileContent = PROFILE_CONTENT[profile];
  const holdingValueLabel = holding?.current_value
    ? `£${holding.current_value.toLocaleString("en-GB", { maximumFractionDigits: 0 })}`
    : "Value unavailable";

  // Sync wizardState to localStorage
  useEffect(() => {
    saveState(wizardState);
  }, [wizardState]);

  // Pick a starting holding whenever none is set — initial mount, or after we
  // clear a stale ID below when its context fetch 404s.
  useEffect(() => {
    if (wizardState.holdingId) return;
    Promise.all([
      api.get<Holding[]>("/api/portfolio/holdings"),
      api.get<Thesis[]>("/api/theses/current"),
    ])
      .then(([holdings, theses]) => {
        const withThesis = new Set(theses.map((t) => t.holding_id));
        const undrafted = holdings
          .filter((h) => !withThesis.has(h.id))
          .sort((a, b) => (b.current_value ?? 0) - (a.current_value ?? 0));
        if (undrafted[0]) {
          setWizardState((prev) => ({ ...prev, holdingId: undrafted[0].id }));
        } else {
          // Every position already has a reason — nothing to onboard.
          router.replace("/dashboard");
        }
      })
      .catch(() => router.replace("/dashboard"));
  }, [wizardState.holdingId, router]);

  useEffect(() => {
    api
      .get<{ investor_profile: InvestorProfile | null }>("/api/onboarding/state")
      .then((state) => {
        if (state.investor_profile) {
          setWizardState((prev) => ({ ...prev, investorProfile: prev.investorProfile ?? state.investor_profile }));
        }
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!wizardState.holdingId) return;
    api
      .get<HoldingContext>(`/api/onboarding/context/${wizardState.holdingId}`)
      .then((h) => setHolding(h))
      .catch((e) => {
        // A persisted holdingId can outlive the holding it points at — deleted
        // position, different account, or state carried over from another env.
        // Wipe the stale wizard state so the picker above re-fires; otherwise
        // holding stays null and the save action silent-returns on click.
        if (e instanceof Error && e.message === "Holding not found") {
          setHolding(null);
          setStep("QUESTION_1");
          setWizardState((prev) => ({
            ...prev,
            holdingId: null,
            answer1: "",
            answer2: "",
            synthesisResult: null,
          }));
        }
      });
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

  const handleQuickSave = async () => {
    if (!wizardState.holdingId || !holding) return;
    if (wizardState.answer1.trim().length < 5 || wizardState.answer2.trim().length < 5) return;
    setSavingThesis(true);
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
    } catch (e) {
      setError(getErrorMessage(e, "We couldn't save this record yet. Please try again."));
    } finally {
      setSavingThesis(false);
    }
  };

  const toggleSignal = (i: number) => {
    setSelectedSignalIdx((prev) => {
      const next = new Set(prev);
      if (next.has(i)) next.delete(i);
      else next.add(i);
      return next;
    });
  };

  const selectedCandidateSignals = (): CandidateSignal[] =>
    groundingResult
      ? groundingResult.candidate_signals.filter((_, i) => selectedSignalIdx.has(i))
      : [];

  const handleSelectProfile = async (selected: InvestorProfile) => {
    setWizardState((prev) => ({ ...prev, investorProfile: selected }));
    try {
      await api.post("/api/onboarding/profile", { investor_profile: selected });
    } catch {}
  };

  const handleComplete = async () => {
    if (!wizardState.holdingId || !wizardState.synthesisResult || !holding) {
      setError("We couldn't find a thesis to save yet. Please try again.");
      return;
    }
    setSavingThesis(true);
    setError("");
    try {
      const thesisId = wizardState.synthesisResult.thesis_id;
      await api.put<Thesis>(`/api/theses/${thesisId}`, {
        status: "active",
        confidence: "medium",
        review_cadence_days: 7,
        source: "ai_assisted",
      });
      const chosenSignals = selectedCandidateSignals();
      // Decompose first, THEN attach the watches the user chose in the climb, so
      // they are the final active state — a later decompose would otherwise
      // re-sync the interpretation and overwrite them. On the clean path (no
      // climb selections), immediately confirm the safe auto-active draft
      // signals so first pulse and historical audit can use the structured map.
      const decomposition = await api
        .post<ThesisDecompositionEnvelope>("/api/theses/" + thesisId + "/decompose")
        .catch(() => null);
      if (chosenSignals.length === 0) {
        const autoConfirmPayload = buildOnboardingAutoConfirmPayload(decomposition);
        if (autoConfirmPayload) {
          await api
            .post(`/api/theses/${thesisId}/decomposition/confirm`, autoConfirmPayload)
            .catch(() => null);
        }
      }
      if (chosenSignals.length > 0) {
        await api
          .post("/api/onboarding/confirm-signals", { thesis_id: thesisId, signals: chosenSignals })
          .catch(() => null);
      }
      await api.post("/api/onboarding/complete");
      clearState();
      router.push(`/dashboard/positions/${holding.ticker}?source=onboarding`);
    } catch (e) {
      setError(getErrorMessage(e, "We couldn't save your first thesis yet. Please try again."));
    } finally {
      setSavingThesis(false);
    }
  };

  const visibleStep = VISIBLE_STEPS.indexOf(step as (typeof VISIBLE_STEPS)[number]);
  const stepDisplay =
    visibleStep >= 0 ? `0${visibleStep + 1} / 0${VISIBLE_STEPS.length}` : null;
  const sidebarCards = (() => {
    switch (step) {
      case "WELCOME":
        return [
          {
            eyebrow: "",
            title: "~2 min",
            body: "One position, two answers, and a working thesis you can review later.",
          },
          {
            eyebrow: "Goal",
            title: "Get to one usable reason fast.",
            body: "The product gets real once an important holding has a written case behind it.",
          },
        ];
      case "QUESTION_1":
        return [
          {
            eyebrow: holding ? `${holding.ticker} · ${holdingValueLabel}` : "Your position",
            title: "Write the positive case in your own words.",
            body: holding ? `${holding.name}${holding.sector ? ` · ${holding.sector}` : ""}` : "",
          },
          {
            eyebrow: "Tip",
            title: "Direction beats polish.",
            body: "Get the real idea down first. You can sharpen the sentence once the structure exists.",
          },
        ];
      case "QUESTION_2":
        return [
          {
            eyebrow: "Question 2",
            title: "Define what would break the case.",
            body: "This is the part that keeps the thesis honest once the stock starts moving.",
          },
        ];
      case "SYNTHESISING":
        return [
          {
            eyebrow: "In progress",
            title: "Turning your answers into a working thesis.",
            body: "Turning your answers into something you can review and monitor.",
          },
        ];
      case "CLIMB":
        return [
          {
            eyebrow: "Pressure test",
            title: "Pick the signals that should matter.",
            body: "You are choosing what evidence would force a revisit later, not building a giant dashboard.",
          },
          {
            eyebrow: "Selected",
            title: `${selectedSignalIdx.size} watch${selectedSignalIdx.size === 1 ? "" : "es"} chosen.`,
            body: selectedSignalIdx.size > 0
              ? "Those watches will be attached once you start monitoring this position."
              : "You can continue without taking the suggested watches yet.",
          },
        ];
      case "REVIEW":
        return [
          {
            eyebrow: "Outcome",
            title: "This becomes the first working thesis.",
            body: "It does not need to be perfect on day one. It needs to be specific enough to test.",
          },
          {
            eyebrow: "Next",
            title: "Monitoring starts after this save.",
            body: "News, filings, and earnings get checked against what you wrote. Your first digest arrives Sunday.",
          },
        ];
      default:
        return [
          {
            eyebrow: "Setup",
            title: "Building the first decision record.",
            body: "One real position, quickly. No setup theatre.",
          },
        ];
    }
  })();

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
          Let&rsquo;s talk about<br />how you invest.
        </h1>
        <p className="text-base text-muted-foreground leading-relaxed max-w-sm">
          Pick what sounds most like you. The questions and wording change a bit — same product either way.
        </p>
      </div>

      <div className="grid gap-3">
        {(Object.entries(PROFILE_CONTENT) as Array<[InvestorProfile, (typeof PROFILE_CONTENT)[InvestorProfile]]>).map(([key, content]) => {
          const selected = profile === key;
          return (
            <button
              key={key}
              type="button"
              onClick={() => handleSelectProfile(key)}
              className={`text-left border p-4 transition-colors ${
                selected ? "border-primary bg-primary/5" : "border-border hover:border-primary/40 hover:bg-background/50"
              }`}
            >
              <div className="flex items-start justify-between gap-4">
                <div className="space-y-2">
                  <p className="font-mono text-[10px] uppercase tracking-[0.25em] text-primary">{content.label}</p>
                  <p className="text-base font-medium text-foreground">{content.title}</p>
                  <p className="text-sm text-muted-foreground leading-relaxed">{content.subtitle}</p>
                </div>
                <span className={`mt-1 h-3 w-3 rounded-full border ${selected ? "border-primary bg-primary" : "border-border"}`} />
              </div>
            </button>
          );
        })}
      </div>

      <div className="space-y-3 border-l-2 border-primary/30 pl-4">
        {profileContent.welcomeLines.map((line, i) => (
          <p key={i} className="text-sm text-foreground/70 font-mono">
            {line}
          </p>
        ))}
      </div>

      <div className="flex items-center gap-4 pt-2">
        <Button onClick={() => goTo("QUESTION_1")}>
          Begin
        </Button>
        <button
          onClick={handleSkip}
          className="text-xs text-muted-foreground hover:text-foreground transition-colors font-mono underline underline-offset-4"
        >
          Skip for now
        </button>
      </div>
    </motion.div>
  );


  // Opt-in AI help: only when the user asks for it, and only as a starting point
  // they can edit — never pre-filled before they've had a chance to write their own.
  const handleDraftForMe = async () => {
    if (!holding) return;
    setDraftingForMe(true);
    setError("");
    try {
      const draft = await api.post<{ why_own_it: string; what_would_change_my_mind: string }>(
        "/api/theses/draft",
        { ticker: holding.ticker }
      );
      setWizardState((prev) => ({
        ...prev,
        answer1: prev.answer1.trim() ? prev.answer1 : draft.why_own_it,
        answer2: prev.answer2.trim() ? prev.answer2 : (draft.what_would_change_my_mind ?? prev.answer2),
      }));
    } catch (e) {
      setError(getErrorMessage(e, "Couldn't draft a starting point — write a line yourself to continue."));
    } finally {
      setDraftingForMe(false);
    }
  };

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

      <div className="border border-border/70 bg-background/55 p-4 sm:p-5">
        <textarea
          value={wizardState[qKey]}
          onChange={(e) =>
            setWizardState((prev) => ({ ...prev, [qKey]: e.target.value }))
          }
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
            {wizardState[qKey].length} chars
          </span>
        </div>
      </div>

      {error && (
        <p className="text-sm text-red-600 font-mono">{error}</p>
      )}

      <div className="space-y-3">
        <div className="flex items-center gap-4">
          <Button
            onClick={onNext}
            disabled={wizardState[qKey].trim().length < 5}
            loading={qKey === "answer2" && savingThesis}
          >
            {qKey === "answer2" ? "Save record" : "Continue"}
          </Button>
          <button
            onClick={handleSkip}
            className="text-xs text-muted-foreground hover:text-foreground transition-colors font-mono underline underline-offset-4"
          >
            Skip for now
          </button>
        </div>
        {wizardState[qKey].trim().length < 10 && (
          <button
            onClick={handleDraftForMe}
            disabled={draftingForMe || !holding}
            className="flex items-center gap-2 text-sm text-primary hover:text-primary/80 transition-colors font-mono disabled:opacity-50"
          >
            <span className="text-base leading-none">↳</span>
            {draftingForMe ? "Drafting a starting point…" : "Not sure where to start? Draft one for me"}
          </button>
        )}
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
          {holding ? ` for ${holding.ticker}` : ""}. Usually takes about 10 seconds.
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

  const renderClimb = () => {
    const g = groundingResult;
    if (!g) return null;
    const selectedCount = selectedSignalIdx.size;
    return (
      <motion.div
        key="climb"
        variants={stepVariants}
        initial="enter"
        animate="center"
        exit="exit"
        transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
        className="space-y-8"
      >
        <div className="space-y-2">
          <span className="font-mono text-[10px] uppercase tracking-[0.3em] text-primary">
            Pressure test{holding ? ` — ${holding.ticker}` : ""}
          </span>
          <h2 className="font-display italic text-[2rem] leading-tight text-foreground">
            Before you commit, the other side.
          </h2>
          <p className="text-muted-foreground text-sm">
            Your reason is still more story than signal. Here&rsquo;s the bear case &mdash; and the few
            numbers that would actually prove you right or wrong.
          </p>
        </div>

        {g.bear_case && (
          <div className="border border-border/70 bg-background/55 p-4 space-y-1">
            <div className="font-mono text-[9px] uppercase tracking-[0.25em] text-muted-foreground">
              The bear case
            </div>
            <p className="text-sm text-foreground/80 leading-relaxed italic">{g.bear_case}</p>
          </div>
        )}

        {g.suggested_questions.length > 0 && (
          <div className="space-y-2">
            <div className="font-mono text-[9px] uppercase tracking-[0.25em] text-muted-foreground">
              Worth asking yourself
            </div>
            <ul className="space-y-1.5">
              {g.suggested_questions.map((q, i) => (
                <li key={i} className="text-sm text-foreground/70 leading-relaxed flex gap-2">
                  <span className="text-primary">&mdash;</span>
                  <span>{q}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {g.candidate_signals.length > 0 && (
          <div className="space-y-3">
            <div className="space-y-1">
              <p className="text-base font-medium text-foreground">
                Pick what you&rsquo;ll hold this position to.
              </p>
            </div>
            <div className="grid gap-2">
              {g.candidate_signals.map((sig, i) => {
                const selected = selectedSignalIdx.has(i);
                return (
                  <button
                    key={i}
                    type="button"
                    onClick={() => toggleSignal(i)}
                    aria-pressed={selected}
                    className={`text-left border p-4 transition-colors ${
                      selected ? "border-primary bg-primary/5" : "border-border hover:border-primary/40 hover:bg-background/50"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="space-y-1.5">
                        <p className="font-mono text-[10px] uppercase tracking-[0.25em] text-primary">
                          {SIGNAL_TYPE_LABEL[sig.signal_type] ?? sig.signal_type}
                        </p>
                        <p className="text-sm font-medium text-foreground">{sig.label}</p>
                        {sig.rationale && (
                          <p className="text-sm text-muted-foreground leading-relaxed">{sig.rationale}</p>
                        )}
                      </div>
                      <span
                        className={`mt-1 flex h-4 w-4 items-center justify-center border text-[10px] leading-none ${
                          selected
                            ? "border-primary bg-primary text-primary-foreground"
                            : "border-border text-transparent"
                        }`}
                      >
                        ✓
                      </span>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {error && <p className="text-sm text-red-600 font-mono">{error}</p>}

        <div className="flex items-center gap-4 pt-2">
          <Button
            onClick={() => goTo("REVIEW")}
          >
            {selectedCount > 0
              ? `Watch ${selectedCount} signal${selectedCount === 1 ? "" : "s"}`
              : "Continue without watches"}
          </Button>
          <button
            onClick={() => {
              setSelectedSignalIdx(new Set());
              goTo("REVIEW");
            }}
            className="text-xs text-muted-foreground hover:text-foreground transition-colors font-mono underline underline-offset-4"
          >
            Skip for now
          </button>
        </div>
      </motion.div>
    );
  };

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
          <div className="border border-border/70 bg-background/55 p-4">
            <p className="text-sm text-foreground/70 italic font-sans leading-relaxed">
              &ldquo;{result.ai_summary}&rdquo;
            </p>
          </div>
        )}

        {selectedCandidateSignals().length > 0 && (
          <div className="space-y-2 border border-border/70 bg-background/55 p-4">
            <div className="font-mono text-[9px] uppercase tracking-[0.25em] text-muted-foreground">
              Watches you picked
            </div>
            <ul className="space-y-1">
              {selectedCandidateSignals().map((s, i) => (
                <li key={i} className="text-sm text-foreground/70 flex gap-2">
                  <span className="text-primary">+</span>
                  <span>{s.label}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {error && <p className="text-sm text-red-600 font-mono">{error}</p>}

        <div className="flex items-center gap-4 pt-2">
          <Button
            onClick={handleComplete}
            disabled={savingThesis}
          >
            {savingThesis ? "Turning on monitoring…" : "Start monitoring this holding"}
          </Button>
          <button
            onClick={() => goTo("QUESTION_1")}
            className="text-xs text-muted-foreground hover:text-foreground transition-colors font-mono underline underline-offset-4"
          >
            Edit answers
          </button>
        </div>
      </motion.div>
    );
  };

  // ---------------------------------------------------------------------------
  // Layout
  // ---------------------------------------------------------------------------

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
              {stepDisplay && (
                <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground tabular-nums">
                  {stepDisplay}
                </span>
              )}
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

          <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_18rem]">
            <section className="min-w-0">
              <div className="product-panel product-panel-muted p-6 sm:p-8">
                <AnimatePresence mode="wait">
                  {step === "WELCOME" && renderWelcome()}
                  {step === "QUESTION_1" &&
                    renderQuestion(
                      "answer1",
                      profileContent.q1,
                      profileContent.q1Placeholder,
                      () => goTo("QUESTION_2"),
                      "Question 01"
                    )}
                  {step === "QUESTION_2" &&
                    renderQuestion(
                      "answer2",
                      profileContent.q2,
                      profileContent.q2Placeholder,
                      handleQuickSave,
                      "Question 02"
                    )}
                  {step === "SYNTHESISING" && renderSynthesising()}
                  {step === "CLIMB" && renderClimb()}
                  {step === "REVIEW" && renderReview()}
                </AnimatePresence>
              </div>
            </section>

            <aside className="space-y-4">
              {sidebarCards.map((card) => (
                <SidebarPanel
                  key={card.title}
                  eyebrow={card.eyebrow}
                  title={card.title}
                  body={card.body}
                />
              ))}
            </aside>
          </div>
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
    <div className="border border-border/70 bg-background/55 p-4 space-y-1">
      <div className="font-mono text-[9px] uppercase tracking-[0.25em] text-muted-foreground">
        {label}
      </div>
      <p className="text-sm text-foreground leading-relaxed">{text}</p>
    </div>
  );
}

function SidebarPanel({
  eyebrow,
  title,
  body,
}: {
  eyebrow: string;
  title: string;
  body: string;
}) {
  return (
    <div className="product-panel p-5">
      <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
        {eyebrow}
      </p>
      <p className="mt-2 font-display text-[1.3rem] italic leading-tight text-foreground">
        {title}
      </p>
      <p className="mt-2 font-sans text-sm leading-relaxed text-muted-foreground">
        {body}
      </p>
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
