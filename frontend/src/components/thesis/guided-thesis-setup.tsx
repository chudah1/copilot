"use client";

import { useEffect, useState } from "react";
import { ArrowRight, Check, Sparkles } from "lucide-react";

import { getErrorMessage } from "@/lib/errors";
import type {
  ConfirmDecompositionRequest,
  Thesis,
  ThesisAssistResponse,
  ThesisDecompositionEnvelope,
} from "@/types";

interface DraftFields {
  why_own_it: string;
  must_remain_true: string;
  what_would_change_my_mind: string;
}

interface SavePayload {
  thesis_kind: "company";
  why_own_it: string;
  must_remain_true: string | null;
  what_would_change_my_mind: string;
  confidence: "high" | "medium" | "low";
  review_cadence_days: number;
  ai_summary: string | null;
  interpretation: Record<string, unknown> | null;
  source: "user" | "ai_assisted";
  status: "active";
}

interface GuidedThesisSetupProps {
  ticker: string;
  thesis?: Thesis | null;
  initialDraft?: Partial<DraftFields> | null;
  investorProfile?: "thesis_driven" | "hearsay_driven" | null;
  onAssist: (draft: DraftFields) => Promise<ThesisAssistResponse>;
  onSave: (data: SavePayload) => Promise<Thesis | null>;
  onGenerate: (thesisId: string) => Promise<ThesisDecompositionEnvelope | null>;
  onConfirm: (
    thesisId: string,
    payload: ConfirmDecompositionRequest,
  ) => Promise<ThesisDecompositionEnvelope | null>;
  onCancel: () => void;
  onComplete: () => void;
}

const STEPS = [
  { label: "Your reason", short: "Write" },
  { label: "AI assist", short: "Sharpen" },
  { label: "Generate checks", short: "Generate" },
  { label: "Choose checks", short: "Choose" },
  { label: "Confirm", short: "Confirm" },
] as const;

function text(value: string | null | undefined) {
  return value ?? "";
}

function collectInitialSelections(envelope: ThesisDecompositionEnvelope) {
  const selected = new Set<string>();
  for (const claim of envelope.decomposition?.claims ?? []) {
    for (const entity of claim.entities) {
      for (const signal of entity.signals) {
        if (signal.active || signal.user_confirmed === true) selected.add(signal.id);
      }
    }
  }
  return selected;
}

function buildConfirmationPayload(
  envelope: ThesisDecompositionEnvelope,
  selectedSignalIds: Set<string>,
): ConfirmDecompositionRequest | null {
  const decomposition = envelope.decomposition;
  if (!decomposition) return null;

  const entities: ConfirmDecompositionRequest["entities"] = [];
  const signals: ConfirmDecompositionRequest["signals"] = [];
  for (const claim of decomposition.claims) {
    for (const entity of claim.entities) {
      const entitySelected = entity.signals.some((signal) => selectedSignalIds.has(signal.id));
      entities.push({ id: entity.id, user_confirmed: entitySelected });
      for (const signal of entity.signals) {
        const selected = selectedSignalIds.has(signal.id);
        signals.push({ id: signal.id, user_confirmed: selected, active: selected });
      }
    }
  }
  return { decomposition_id: decomposition.id, entities, signals };
}

function SetupProgress({ step }: { step: number }) {
  return (
    <div className="border-y border-border/70 bg-background/75">
      <div className="flex items-center justify-between py-4 sm:hidden">
        <div>
          <p className="font-mono text-[9px] uppercase tracking-[0.18em] text-muted-foreground">
            Step {step + 1} of {STEPS.length}
          </p>
          <p className="mt-1 font-sans text-sm font-medium text-foreground">{STEPS[step].label}</p>
        </div>
        <span className="font-display text-2xl italic text-primary">
          {Math.round(((step + 1) / STEPS.length) * 100)}%
        </span>
      </div>
      <div className="hidden grid-cols-5 sm:grid">
        {STEPS.map((item, index) => (
          <div
            key={item.label}
            className={`border-l border-border/60 px-4 py-4 last:border-r ${index === step ? "bg-amber-50/70" : ""}`}
          >
            <div className="flex items-center gap-2">
              <span
                className={`grid h-5 w-5 place-items-center rounded-full font-mono text-[8px] ${
                  index < step
                    ? "bg-emerald-700 text-white"
                    : index === step
                      ? "bg-primary text-primary-foreground"
                      : "border border-border text-muted-foreground"
                }`}
              >
                {index < step ? <Check className="h-3 w-3" /> : index + 1}
              </span>
              <p className={`font-mono text-[9px] uppercase tracking-[0.14em] ${index === step ? "text-primary" : "text-muted-foreground"}`}>
                {item.short}
              </p>
            </div>
          </div>
        ))}
      </div>
      <div className="h-0.5 bg-border/40 sm:hidden">
        <div className="h-full bg-primary transition-all" style={{ width: `${((step + 1) / STEPS.length) * 100}%` }} />
      </div>
    </div>
  );
}

function DraftField({
  label,
  prompt,
  value,
  onChange,
}: {
  label: string;
  prompt: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="block">
      <span className="font-mono text-[9px] uppercase tracking-[0.18em] text-muted-foreground">{label}</span>
      <span className="mt-1 block font-sans text-xs text-muted-foreground/75">{prompt}</span>
      <textarea
        value={value}
        onChange={(event) => onChange(event.target.value)}
        rows={4}
        className="mt-3 min-h-28 w-full resize-y border border-border/80 bg-background/75 px-4 py-3 font-sans text-sm leading-relaxed text-foreground outline-none transition-colors placeholder:text-muted-foreground/45 focus:border-primary/60"
      />
    </label>
  );
}

export function GuidedThesisSetup({
  ticker,
  thesis,
  initialDraft,
  investorProfile,
  onAssist,
  onSave,
  onGenerate,
  onConfirm,
  onCancel,
  onComplete,
}: GuidedThesisSetupProps) {
  const reasonWord = investorProfile === "thesis_driven" ? "thesis" : "reason";
  const [step, setStep] = useState(0);
  const [draft, setDraft] = useState<DraftFields>({
    why_own_it: text(thesis?.why_own_it) || text(initialDraft?.why_own_it),
    must_remain_true: text(thesis?.must_remain_true) || text(initialDraft?.must_remain_true),
    what_would_change_my_mind:
      text(thesis?.what_would_change_my_mind) || text(initialDraft?.what_would_change_my_mind),
  });
  const [confidence, setConfidence] = useState<"high" | "medium" | "low">(thesis?.confidence ?? "medium");
  const [suggestion, setSuggestion] = useState<ThesisAssistResponse | null>(null);
  const [aiSummary, setAiSummary] = useState<string | null>(thesis?.ai_summary ?? null);
  const [interpretation, setInterpretation] = useState<Record<string, unknown> | null>(thesis?.interpretation ?? null);
  const [source, setSource] = useState<"user" | "ai_assisted">(thesis?.source ?? "user");
  const [savedThesisId, setSavedThesisId] = useState<string | null>(thesis?.id ?? null);
  const [envelope, setEnvelope] = useState<ThesisDecompositionEnvelope | null>(null);
  const [selectedSignalIds, setSelectedSignalIds] = useState<Set<string>>(new Set());
  const [assisting, setAssisting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [complete, setComplete] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "smooth" });
  }, [step]);

  const updateDraft = (key: keyof DraftFields, value: string) => {
    setDraft((current) => ({ ...current, [key]: value }));
  };

  const draftReady =
    draft.why_own_it.trim().length > 0 &&
    draft.must_remain_true.trim().length > 0 &&
    draft.what_would_change_my_mind.trim().length > 0;

  const requestAssist = async () => {
    if (!draft.why_own_it.trim()) return;
    setAssisting(true);
    setError("");
    try {
      const result = await onAssist(draft);
      setSuggestion(result);
      setStep(1);
    } catch (assistError) {
      setError(getErrorMessage(assistError, "PenKeep could not sharpen this right now. Your draft is still safe."));
    } finally {
      setAssisting(false);
    }
  };

  const saveAndContinue = async (nextDraft: DraftFields, assisted: ThesisAssistResponse | null) => {
    setSaving(true);
    setError("");
    try {
      const saved = await onSave({
        thesis_kind: "company",
        why_own_it: nextDraft.why_own_it,
        must_remain_true: nextDraft.must_remain_true || null,
        what_would_change_my_mind: nextDraft.what_would_change_my_mind,
        confidence,
        review_cadence_days: thesis?.review_cadence_days ?? 14,
        ai_summary: assisted?.ai_summary ?? aiSummary,
        interpretation: assisted?.interpretation ?? interpretation,
        source: assisted ? "ai_assisted" : source,
        status: "active",
      });
      if (!saved) return;
      setDraft(nextDraft);
      setSavedThesisId(saved.id);
      if (assisted) {
        setAiSummary(assisted.ai_summary);
        setInterpretation(assisted.interpretation);
        setSource("ai_assisted");
      }
      setStep(2);
    } catch (saveError) {
      setError(getErrorMessage(saveError, `Could not save the ${reasonWord}.`));
    } finally {
      setSaving(false);
    }
  };

  const generateChecks = async () => {
    if (!savedThesisId) return;
    setGenerating(true);
    setError("");
    try {
      const result = await onGenerate(savedThesisId);
      if (!result?.decomposition) {
        setError(result?.message || "PenKeep could not generate checks from this reason yet.");
        return;
      }
      setEnvelope(result);
      setSelectedSignalIds(collectInitialSelections(result));
      setStep(3);
    } catch (generateError) {
      setError(getErrorMessage(generateError, "PenKeep could not generate checks right now."));
    } finally {
      setGenerating(false);
    }
  };

  const toggleSignal = (signalId: string) => {
    setSelectedSignalIds((current) => {
      const next = new Set(current);
      if (next.has(signalId)) next.delete(signalId);
      else next.add(signalId);
      return next;
    });
  };

  const confirmSetup = async () => {
    if (!savedThesisId || !envelope) return;
    const payload = buildConfirmationPayload(envelope, selectedSignalIds);
    if (!payload) return;
    setConfirming(true);
    setError("");
    try {
      const confirmed = await onConfirm(savedThesisId, payload);
      if (!confirmed) return;
      setEnvelope(confirmed);
      setComplete(true);
    } catch (confirmError) {
      setError(getErrorMessage(confirmError, "Could not activate these checks."));
    } finally {
      setConfirming(false);
    }
  };

  const selectedSignals =
    envelope?.decomposition?.claims.flatMap((claim) =>
      claim.entities.flatMap((entity) =>
        entity.signals.filter((signal) => selectedSignalIds.has(signal.id)),
      ),
    ) ?? [];

  return (
    <section className="overflow-hidden border border-border/70 bg-background/65">
      <div className="flex flex-col gap-3 border-b border-border/60 px-5 py-5 sm:flex-row sm:items-center sm:justify-between sm:px-7">
        <div>
          <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-primary">Guided setup</p>
          <h2 className="mt-2 font-display text-3xl italic leading-tight text-foreground">
            Set up how PenKeep watches {ticker}.
          </h2>
        </div>
        <button type="button" onClick={onCancel} className="self-start font-mono text-[9px] uppercase tracking-[0.16em] text-muted-foreground hover:text-foreground sm:self-auto">
          {step >= 2 ? "Finish later" : "Exit setup"}
        </button>
      </div>

      <div className="px-5 sm:px-7"><SetupProgress step={step} /></div>

      <div className="mx-auto max-w-4xl px-5 py-8 sm:px-7 sm:py-12">
        {error && (
          <div className="mb-6 border border-red-500/25 bg-red-500/5 px-4 py-3 font-sans text-sm text-red-700">
            {error}
          </div>
        )}

        {step === 0 && (
          <div>
            <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-primary">Your words first</p>
            <h3 className="mt-3 max-w-2xl font-display text-3xl italic leading-tight text-foreground sm:text-4xl">
              Explain the investment as you would to a thoughtful friend.
            </h3>
            <p className="mt-3 max-w-2xl font-sans text-sm leading-relaxed text-foreground/65">
              No ratios or investing jargon required. PenKeep needs your belief, the condition behind it, and the point where you would reconsider.
            </p>

            <div className="mt-8 space-y-7">
              <DraftField label="Why do you own it?" prompt="What makes this company worth holding?" value={draft.why_own_it} onChange={(value) => updateDraft("why_own_it", value)} />
              <div className="grid gap-7 md:grid-cols-2">
                <DraftField label="What must stay true?" prompt="What needs to keep going well?" value={draft.must_remain_true} onChange={(value) => updateDraft("must_remain_true", value)} />
                <DraftField label="What would change your mind?" prompt="What evidence would make you rethink?" value={draft.what_would_change_my_mind} onChange={(value) => updateDraft("what_would_change_my_mind", value)} />
              </div>
              <label className="block max-w-44">
                <span className="font-mono text-[9px] uppercase tracking-[0.18em] text-muted-foreground">Your confidence</span>
                <select value={confidence} onChange={(event) => setConfidence(event.target.value as typeof confidence)} className="mt-3 w-full border border-border/80 bg-background px-3 py-2.5 font-sans text-sm text-foreground outline-none focus:border-primary/60">
                  <option value="high">High</option>
                  <option value="medium">Medium</option>
                  <option value="low">Low</option>
                </select>
              </label>
            </div>

            <div className="mt-8 flex flex-col gap-3 border-t border-border/60 pt-6 sm:flex-row sm:items-center sm:justify-between">
              <button type="button" disabled={!draftReady || saving} onClick={() => void saveAndContinue(draft, null)} className="order-2 font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground hover:text-foreground disabled:opacity-40 sm:order-1">
                {saving ? "Saving…" : "Keep my wording"}
              </button>
              <button type="button" disabled={!draft.why_own_it.trim() || assisting} onClick={() => void requestAssist()} className="order-1 inline-flex items-center justify-center gap-2 bg-primary px-5 py-3 font-mono text-[10px] uppercase tracking-[0.16em] text-primary-foreground disabled:opacity-40 sm:order-2">
                <Sparkles className="h-3.5 w-3.5" /> {assisting ? "Sharpening…" : "Help me sharpen it"}
              </button>
            </div>
          </div>
        )}

        {step === 1 && suggestion && (
          <div>
            <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-primary">AI assist · optional</p>
            <h3 className="mt-3 font-display text-3xl italic leading-tight text-foreground sm:text-4xl">Sharper, but still recognisably yours.</h3>
            <p className="mt-3 max-w-2xl font-sans text-sm leading-relaxed text-foreground/65">
              AI made the business driver and failure conditions more specific. Nothing changes unless you accept it.
            </p>
            <div className="mt-8 grid gap-px overflow-hidden border border-border/70 bg-border/70 md:grid-cols-3">
              {[
                ["Why I own it", suggestion.why_own_it],
                ["Must stay true", suggestion.must_remain_true],
                ["I would rethink if", suggestion.what_would_change_my_mind],
              ].map(([label, body]) => (
                <div key={label} className="bg-background p-5">
                  <p className="font-mono text-[9px] uppercase tracking-[0.16em] text-muted-foreground">{label}</p>
                  <p className="mt-3 font-sans text-sm leading-relaxed text-foreground/78">{body}</p>
                </div>
              ))}
            </div>
            <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <button type="button" onClick={() => setStep(0)} className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground hover:text-foreground">← Edit my original</button>
              <div className="flex flex-col gap-2 sm:flex-row">
                <button type="button" disabled={saving} onClick={() => void saveAndContinue(draft, null)} className="border border-border bg-background px-4 py-3 font-mono text-[10px] uppercase tracking-[0.16em] text-foreground disabled:opacity-40">Keep mine</button>
                <button type="button" disabled={saving} onClick={() => void saveAndContinue({ why_own_it: suggestion.why_own_it, must_remain_true: suggestion.must_remain_true, what_would_change_my_mind: suggestion.what_would_change_my_mind }, suggestion)} className="bg-primary px-4 py-3 font-mono text-[10px] uppercase tracking-[0.16em] text-primary-foreground disabled:opacity-40">{saving ? "Saving…" : "Use this version →"}</button>
              </div>
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="mx-auto max-w-2xl py-6 text-center sm:py-10">
            <span className="mx-auto grid h-12 w-12 place-items-center rounded-full border border-primary/20 bg-emerald-50 text-primary"><Sparkles className="h-5 w-5" /></span>
            <p className="mt-6 font-mono text-[10px] uppercase tracking-[0.2em] text-primary">Turn the {reasonWord} into checks</p>
            <h3 className="mt-3 font-display text-3xl italic leading-tight text-foreground sm:text-4xl">PenKeep looks for evidence, not keywords.</h3>
            <p className="mx-auto mt-3 max-w-xl font-sans text-sm leading-relaxed text-foreground/65">
              PenKeep identifies the claims inside your {reasonWord}, then proposes observable checks. You decide which ones represent your thinking.
            </p>
            <div className="mx-auto mt-8 max-w-lg divide-y divide-border/60 border-y border-border/60 text-left">
              {["Identify the claims that matter", "Find direct company evidence", "Add outside evidence only where useful"].map((item) => (
                <div key={item} className="flex items-center gap-3 py-4"><span className="grid h-5 w-5 place-items-center rounded-full bg-emerald-700 text-white"><Check className="h-3 w-3" /></span><p className="font-sans text-sm text-foreground/78">{item}</p></div>
              ))}
            </div>
            <button type="button" disabled={generating} onClick={() => void generateChecks()} className="mt-8 inline-flex items-center gap-2 bg-primary px-5 py-3 font-mono text-[10px] uppercase tracking-[0.16em] text-primary-foreground disabled:opacity-40">
              {generating ? "Generating checks…" : "Generate suggested checks"} {!generating && <ArrowRight className="h-3.5 w-3.5" />}
            </button>
          </div>
        )}

        {step === 3 && envelope?.decomposition && (
          <div>
            <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-primary">Choose what deserves attention</p>
            <h3 className="mt-3 font-display text-3xl italic leading-tight text-foreground sm:text-4xl">Keep only checks that could change your mind.</h3>
            <p className="mt-3 max-w-2xl font-sans text-sm leading-relaxed text-foreground/65">More checks do not mean better monitoring. Select the few that represent the reason you actually own {ticker}.</p>
            <div className="mt-8 space-y-8">
              {envelope.decomposition.claims.map((claim) => (
                <div key={claim.id}>
                  <p className="border-l-2 border-primary/25 pl-4 font-display text-lg italic leading-relaxed text-foreground/80">{claim.claim_text}</p>
                  <div className="mt-4 space-y-3">
                    {claim.entities.flatMap((entity) => entity.signals.map((signal) => {
                      const selected = selectedSignalIds.has(signal.id);
                      return (
                        <label key={signal.id} className={`block cursor-pointer border p-5 transition-colors ${selected ? "border-emerald-700/35 bg-emerald-50/55" : "border-border/70 bg-background/75"}`}>
                          <div className="flex items-start gap-4">
                            <input type="checkbox" checked={selected} onChange={() => toggleSignal(signal.id)} className="mt-1 h-4 w-4 accent-emerald-800" />
                            <div className="min-w-0 flex-1">
                              <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between"><p className="font-sans text-sm font-medium text-foreground">{signal.signal_label || signal.signal_type.replaceAll("_", " ")}</p><span className="font-mono text-[8px] uppercase tracking-[0.14em] text-muted-foreground">{entity.entity_name}</span></div>
                              {signal.rationale && <p className="mt-1 font-sans text-xs leading-relaxed text-muted-foreground">{signal.rationale}</p>}
                            </div>
                          </div>
                        </label>
                      );
                    }))}
                  </div>
                </div>
              ))}
            </div>
            <div className="sticky bottom-20 mt-6 flex items-center justify-between gap-4 border border-border/70 bg-background/95 p-4 shadow-lg backdrop-blur-sm">
              <p className="font-sans text-xs text-muted-foreground"><span className="font-medium text-foreground">{selectedSignalIds.size}</span> selected</p>
              <button type="button" disabled={selectedSignalIds.size === 0} onClick={() => setStep(4)} className="bg-primary px-5 py-3 font-mono text-[10px] uppercase tracking-[0.16em] text-primary-foreground disabled:opacity-40">Review setup →</button>
            </div>
          </div>
        )}

        {step === 4 && (
          <div>
            {complete ? (
              <div className="mx-auto max-w-2xl py-10 text-center">
                <span className="mx-auto grid h-12 w-12 place-items-center rounded-full bg-emerald-700 text-white"><Check className="h-5 w-5" /></span>
                <p className="mt-6 font-mono text-[10px] uppercase tracking-[0.2em] text-emerald-800">Monitoring is live</p>
                <h3 className="mt-3 font-display text-4xl italic text-foreground">The loop is ready.</h3>
                <p className="mx-auto mt-3 max-w-lg font-sans text-sm leading-relaxed text-foreground/65">PenKeep is watching {selectedSignalIds.size} check{selectedSignalIds.size === 1 ? "" : "s"}. You will only be asked to decide when evidence meaningfully tests this {reasonWord}.</p>
                <button type="button" onClick={onComplete} className="mt-8 bg-primary px-5 py-3 font-mono text-[10px] uppercase tracking-[0.16em] text-primary-foreground">Open monitored position →</button>
              </div>
            ) : (
              <>
                <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-primary">Confirm the monitoring contract</p>
                <h3 className="mt-3 font-display text-3xl italic leading-tight text-foreground sm:text-4xl">This is what PenKeep will watch, and why.</h3>
                <p className="mt-3 max-w-2xl font-sans text-sm leading-relaxed text-foreground/65">You will not be asked to react to every headline. PenKeep brings you back only when evidence materially tests one of these checks.</p>
                <div className="mt-8 grid gap-6 lg:grid-cols-[minmax(0,1fr)_18rem]">
                  <div className="divide-y divide-border/60 border-y border-border/60">
                    {selectedSignals.map((signal, index) => (
                      <div key={signal.id} className="grid grid-cols-[2rem_minmax(0,1fr)] gap-3 py-4"><span className="font-display text-xl italic text-primary/55">{index + 1}</span><div><p className="font-sans text-sm font-medium text-foreground">{signal.signal_label || signal.signal_type.replaceAll("_", " ")}</p>{signal.rationale && <p className="mt-1 font-sans text-xs leading-relaxed text-muted-foreground">{signal.rationale}</p>}</div></div>
                    ))}
                  </div>
                  <aside className="border border-emerald-900/15 bg-emerald-50/55 p-5">
                    <p className="font-mono text-[9px] uppercase tracking-[0.18em] text-emerald-800">What happens next</p>
                    <ol className="mt-4 space-y-4">{["PenKeep checks fresh evidence.", "Only relevant changes reach your inbox.", `You decide whether the ${reasonWord} still holds.`].map((item, index) => <li key={item} className="flex gap-3 font-sans text-xs leading-relaxed text-foreground/72"><span className="font-mono text-[9px] text-emerald-800">0{index + 1}</span>{item}</li>)}</ol>
                  </aside>
                </div>
                <div className="mt-8 flex flex-col gap-3 border-t border-border/60 pt-6 sm:flex-row sm:items-center sm:justify-between">
                  <button type="button" onClick={() => setStep(3)} className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground hover:text-foreground">← Change checks</button>
                  <button type="button" disabled={confirming} onClick={() => void confirmSetup()} className="bg-primary px-5 py-3 font-mono text-[10px] uppercase tracking-[0.16em] text-primary-foreground disabled:opacity-40">{confirming ? "Activating…" : "Looks right · activate"}</button>
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </section>
  );
}
