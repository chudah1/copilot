"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { InfoTip } from "@/components/ui/info-tip";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { getErrorMessage } from "@/lib/errors";
import { describeWatchHint } from "@/lib/watch-hints";
import type { Thesis, ThesisAssistResponse } from "@/types";

interface ThesisDraftFields {
  why_own_it: string;
  must_remain_true: string;
  what_would_change_my_mind: string;
}

function asText(value: unknown): string {
  return typeof value === "string" ? value : "";
}

interface Props {
  thesis?: Thesis | null;
  investorProfile?: "thesis_driven" | "hearsay_driven" | null;
  mode?: "write" | "first_write" | "tighten" | "rewrite";
  onSave: (data: {
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
  }) => void;
  onAssist: (draft: ThesisDraftFields) => Promise<ThesisAssistResponse>;
  onCancel: () => void;
}

export function ThesisEditor({ thesis, investorProfile, mode = "write", onSave, onAssist, onCancel }: Props) {
  const isAiDraft = thesis?.source === "ai_assisted" && thesis?.status === "draft";
  const [whyOwnIt, setWhyOwnIt] = useState(isAiDraft ? "" : asText(thesis?.why_own_it));
  const [mustRemainTrue, setMustRemainTrue] = useState(isAiDraft ? "" : asText(thesis?.must_remain_true));
  const [changeMind, setChangeMind] = useState(isAiDraft ? "" : asText(thesis?.what_would_change_my_mind));
  const [confidence, setConfidence] = useState<"high" | "medium" | "low">(thesis?.confidence ?? "medium");
  const [aiSummary, setAiSummary] = useState(asText(thesis?.ai_summary));
  const [interpretation, setInterpretation] = useState<Record<string, unknown> | null>(thesis?.interpretation ?? null);
  const [assisting, setAssisting] = useState(false);
  const [assistError, setAssistError] = useState("");
  const [changeMindError, setChangeMindError] = useState("");

  const interpretationData = interpretation ?? {};
  const watchHints = Array.isArray(interpretationData.watch_hints)
    ? interpretationData.watch_hints.filter((hint): hint is Record<string, unknown> => typeof hint === "object" && hint !== null)
    : [];
  const labels = Array.isArray(interpretationData.labels)
    ? interpretationData.labels.filter((label): label is string => typeof label === "string" && label.length > 0)
    : [];
  const monitorability = typeof interpretationData.monitorability === "string" ? interpretationData.monitorability : null;
  const ambiguityNote = typeof interpretationData.ambiguity_note === "string" ? interpretationData.ambiguity_note : "";

  const watchHintDescriptions = watchHints
    .map((hint) => describeWatchHint(hint))
    .filter((value): value is string => Boolean(value));

  const baseCopy = investorProfile === "thesis_driven"
    ? {
        title: thesis ? "Edit thesis" : "Write your thesis",
        helperTitle: "What makes a strong thesis here",
        helperBody: "Be specific enough that you would know which assumption changed.",
        why: "Why do you own this?",
        whyPlaceholder: "Example: I own this because AI infrastructure demand should keep revenue growth and margins strong for the next 3 years.",
        must: "What must remain true?",
        mustPlaceholder: "Example: Revenue growth stays healthy, margins hold up, and management keeps guiding confidently.",
        breaks: "What would change your mind?",
        breaksPlaceholder: "Example: Growth falls below expectations for multiple quarters or management signals weaker long-term demand.",
      }
    : investorProfile === "hearsay_driven"
      ? {
          title: thesis ? "Edit reason" : "Write your reason",
          helperTitle: "What makes a strong reason here",
          helperBody: "Turn the original story into something testable.",
          why: "Why do you own this?",
          whyPlaceholder: "Example: I own this because AI demand should keep revenue growth and margins strong for the next 3 years.",
          must: "What must remain true?",
          mustPlaceholder: "Example: Revenue growth stays healthy, margins hold up, and customers keep spending instead of delaying orders.",
          breaks: "What would change your mind?",
          breaksPlaceholder: "Example: Growth falls below expectations for multiple quarters or management signals weaker long-term demand.",
        }
      : {
          title: thesis ? "Edit reason" : "Write your reason",
          helperTitle: "What makes a strong reason here",
          helperBody: "Be specific enough that you would know what changed.",
          why: "Why do you own this?",
          whyPlaceholder: "Example: I own this because demand for AI infrastructure should keep revenue growth and margins strong for the next 3 years.",
          must: "What must remain true?",
          mustPlaceholder: "Example: Revenue growth stays healthy, margins hold up, and management keeps guiding confidently.",
          breaks: "What would change your mind?",
          breaksPlaceholder: "Example: Growth falls below expectations for multiple quarters or management signals weaker long-term demand.",
        };

  const modeCopy = mode === "rewrite"
    ? investorProfile === "hearsay_driven"
      ? {
          title: "Rewrite the reason",
          helperTitle: "What to rewrite this time",
          helperBody: "Keep what still holds. Cut what already broke.",
          saveLabel: "Save rewritten reason",
        }
      : {
          title: "Rewrite the thesis",
          helperTitle: "What to rewrite this time",
          helperBody: "Keep what still holds. Cut the assumption that broke.",
          saveLabel: "Save rewritten thesis",
        }
    : mode === "tighten"
      ? investorProfile === "hearsay_driven"
        ? {
            title: "Tighten the reason",
            helperTitle: "What to tighten here",
            helperBody: "Make the business driver clearer, sharpen the break condition, and strip out loose story language.",
            saveLabel: "Save tighter reason",
          }
        : {
            title: "Tighten the thesis",
            helperTitle: "What to tighten here",
            helperBody: "Make the core assumption more specific, sharpen the break condition, and cut wording you cannot tie to evidence.",
            saveLabel: "Save tighter thesis",
          }
      : mode === "first_write"
        ? investorProfile === "hearsay_driven"
          ? {
              title: "Write the real reason",
              helperTitle: "Turn the story into something testable",
              helperBody: "Start with why it caught your eye, then name what would prove you wrong. Messy is fine. Vague is not.",
              saveLabel: "Save reason and start watching",
            }
          : {
              title: "Write the thesis",
              helperTitle: "Make the position monitorable",
              helperBody: "Keep it short enough to re-read when evidence lands.",
              saveLabel: "Save thesis and start watching",
            }
        : {
          title: baseCopy.title,
          helperTitle: baseCopy.helperTitle,
          helperBody: baseCopy.helperBody,
          saveLabel: "Save & Start Monitoring",
        };

  const copy = {
    ...baseCopy,
    ...modeCopy,
  };
  const completionChecklist = [
    {
      label: investorProfile === "hearsay_driven" ? "Own the story" : "State the core case",
      done: whyOwnIt.trim().length >= 30,
      detail:
        investorProfile === "hearsay_driven"
          ? "Name the business reason you actually believe."
          : "Name the belief that makes this worth owning.",
    },
    {
      label: "Name what must stay true",
      done: mustRemainTrue.trim().length >= 20,
      detail: "This is what monitoring will defend.",
    },
    {
      label: "Define the break condition",
      done: changeMind.trim().length >= 20,
      detail: "Say what evidence should force a decision.",
    },
  ];
  const completedChecklistCount = completionChecklist.filter((item) => item.done).length;
  const monitorabilityTone =
    monitorability === "high"
      ? "text-emerald-700"
      : monitorability === "medium"
        ? "text-amber-700"
        : monitorability === "low"
          ? "text-red-600"
          : "text-muted-foreground";
  const workflowEyebrow =
    mode === "rewrite"
      ? investorProfile === "hearsay_driven"
        ? "Rewrite the operating case"
        : "Rewrite the operating thesis"
      : mode === "tighten"
        ? investorProfile === "hearsay_driven"
          ? "Sharpen the written reason"
          : "Sharpen the written thesis"
      : mode === "first_write"
        ? investorProfile === "hearsay_driven"
            ? "Write the operating reason"
            : "Write the operating thesis"
          : investorProfile === "hearsay_driven"
            ? "Position operating memo"
            : "Position thesis memo";

  const handleAssist = async () => {
    setAssisting(true);
    setAssistError("");
    try {
      const result = await onAssist({
        why_own_it: whyOwnIt,
        must_remain_true: mustRemainTrue,
        what_would_change_my_mind: changeMind,
      });
      setWhyOwnIt(asText(result.why_own_it) || whyOwnIt);
      setMustRemainTrue(asText(result.must_remain_true) || mustRemainTrue);
      const newChangeMind = asText(result.what_would_change_my_mind) || changeMind;
      setChangeMind(newChangeMind);
      if (newChangeMind.trim()) setChangeMindError("");
      setAiSummary(asText(result.ai_summary));
      setInterpretation(result.interpretation);
    } catch (error: unknown) {
      setAssistError(getErrorMessage(error, "Failed to assist thesis draft"));
    } finally {
      setAssisting(false);
    }
  };

  return (
    <section className="product-panel overflow-hidden">
      <div className="grid gap-0 lg:grid-cols-[minmax(0,1.2fr)_minmax(18rem,22rem)]">
        <div className="space-y-6 p-5 sm:p-6">
          <div className="space-y-4">
            <div className="space-y-2">
              <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-primary">
                {workflowEyebrow}
              </p>
              <div className="space-y-2">
                <h2 className="font-display text-[1.8rem] italic leading-tight text-foreground sm:text-[2.1rem]">
                  {copy.title}
                </h2>
                <p className="max-w-2xl font-sans text-sm leading-relaxed text-foreground/80">
                  {copy.helperBody}
                </p>
              </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-3">
              {completionChecklist.map((item) => (
                <div key={item.label} className="border border-border/70 bg-background/75 p-4">
                  <p className={`font-mono text-[10px] uppercase tracking-[0.16em] ${item.done ? "text-emerald-700" : "text-muted-foreground"}`}>
                    {item.done ? "Ready" : "Needed"}
                  </p>
                  <p className="mt-2 font-sans text-sm text-foreground">{item.label}</p>
                  <p className="mt-1 font-sans text-xs leading-relaxed text-muted-foreground">
                    {item.detail}
                  </p>
                </div>
              ))}
            </div>
          </div>

          {isAiDraft && (
            <div className="flex flex-col gap-3 border border-primary/20 bg-primary/5 px-4 py-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="space-y-1">
                <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-primary">
                  Draft ready
                </p>
                <p className="font-sans text-sm leading-relaxed text-foreground/75">
                  We prepared a draft from the position context. Load it, tighten it, and make it yours.
                </p>
              </div>
              <button
                type="button"
                onClick={() => {
                  setWhyOwnIt(asText(thesis?.why_own_it));
                  setMustRemainTrue(asText(thesis?.must_remain_true));
                  const loaded = asText(thesis?.what_would_change_my_mind);
                  setChangeMind(loaded);
                  if (loaded.trim()) setChangeMindError("");
                }}
                className="font-mono text-[10px] uppercase tracking-[0.15em] whitespace-nowrap text-primary hover:text-primary/80 transition-colors"
              >
                Load starting point
              </button>
            </div>
          )}

          <div className="space-y-5">
            <div className="space-y-2">
              <div className="flex items-center gap-1">
                <Label>{copy.why}</Label>
                <InfoTip label={copy.why}>
                  State the business result or advantage you expect to continue. This becomes the main reason PenKeep checks.
                </InfoTip>
              </div>
              <Textarea
                value={whyOwnIt}
                onChange={(e) => setWhyOwnIt(e.target.value)}
                rows={5}
                placeholder={copy.whyPlaceholder}
                className="min-h-32 bg-background/85"
              />
            </div>

            <div className="grid gap-5 lg:grid-cols-2">
              <div className="space-y-2">
                <div className="flex items-center gap-1">
                  <Label>{copy.must}</Label>
                  <InfoTip label={copy.must}>
                    Name a condition that must keep happening, such as revenue growth, customer demand, margins or management execution.
                  </InfoTip>
                </div>
                <Textarea
                  value={mustRemainTrue}
                  onChange={(e) => setMustRemainTrue(e.target.value)}
                  rows={5}
                  placeholder={copy.mustPlaceholder}
                  className="min-h-28 bg-background/85"
                />
              </div>

              <div className="space-y-2">
                <div className="flex items-center gap-1">
                  <Label>{copy.breaks}</Label>
                  <InfoTip label={copy.breaks}>
                    Name a specific result or event that would force you to review the position. PenKeep will not sell automatically.
                  </InfoTip>
                </div>
                <Textarea
                  value={changeMind}
                  onChange={(e) => { setChangeMind(e.target.value); if (e.target.value.trim()) setChangeMindError(""); }}
                  rows={5}
                  placeholder={copy.breaksPlaceholder}
                  className={`min-h-28 bg-background/85 ${changeMindError ? "border-red-500/60" : ""}`}
                />
                {changeMindError && (
                  <p className="font-sans text-xs text-red-600">{changeMindError}</p>
                )}
              </div>
            </div>

            <div className="grid gap-5 lg:grid-cols-[minmax(0,12rem)_minmax(0,1fr)]">
              <div className="space-y-2">
                <div className="flex items-center gap-1">
                  <Label>Confidence</Label>
                  <InfoTip label="Confidence">
                    Your own confidence in the reason you wrote. This is separate from PenKeep&apos;s health score and model confidence.
                  </InfoTip>
                </div>
                <Select value={confidence} onValueChange={(v) => v && setConfidence(v as "high" | "medium" | "low")}>
                  <SelectTrigger className="w-full bg-background/85">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="high">High</SelectItem>
                    <SelectItem value="medium">Medium</SelectItem>
                    <SelectItem value="low">Low</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <div className="flex items-center gap-1">
                  <Label>Writing help</Label>
                  <InfoTip label="Writing help">
                    PenKeep can make the wording more specific and suggest checks. Nothing changes until you review the text and save it.
                  </InfoTip>
                </div>
                <div className="flex flex-wrap items-center gap-3">
                  <Button type="button" variant="outline" onClick={handleAssist} disabled={assisting}>
                    {assisting ? "Thinking..." : whyOwnIt.trim().length === 0 ? "Draft with AI" : "Sharpen with AI"}
                  </Button>
                  <p className="font-sans text-xs leading-relaxed text-muted-foreground">
                    Tighten the wording and suggest checks based on public data.
                  </p>
                </div>
                {assistError && <p className="text-sm text-red-500">{assistError}</p>}
              </div>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3 border-t border-border/50 pt-5">
            <Button
              onClick={() => {
                if (!changeMind.trim()) {
                  setChangeMindError("Required — this is what triggers your red alerts. One sentence is enough.");
                  return;
                }
                onSave({
                  thesis_kind: "company",
                  why_own_it: whyOwnIt,
                  must_remain_true: mustRemainTrue || null,
                  what_would_change_my_mind: changeMind,
                  confidence,
                  review_cadence_days: thesis?.review_cadence_days ?? 7,
                  ai_summary: aiSummary || null,
                  interpretation,
                  source: aiSummary ? "ai_assisted" : "user",
                  status: "active",
                });
              }}
              disabled={whyOwnIt.trim().length === 0}
            >
              {copy.saveLabel}
            </Button>
            <Button variant="outline" onClick={onCancel}>Cancel</Button>
            <p className="font-sans text-xs leading-relaxed text-muted-foreground">
              {completedChecklistCount === completionChecklist.length
                ? "This is specific enough to monitor cleanly."
                : `Complete ${completionChecklist.length - completedChecklistCount} more section${completionChecklist.length - completedChecklistCount === 1 ? "" : "s"} to make this easier to monitor.`}
            </p>
          </div>
        </div>

        <aside className="border-t border-border/60 bg-muted/15 p-5 sm:p-6 lg:border-l lg:border-t-0">
          <div className="space-y-5">
            <div className="space-y-2">
              <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                Readiness
              </p>
              <p className="font-display text-[1.45rem] italic leading-tight text-foreground">
                {completedChecklistCount === completionChecklist.length
                  ? "Ready to monitor."
                  : "A little more specificity will make this much sharper."}
              </p>
            </div>

            <div className="space-y-3">
              {completionChecklist.map((item) => (
                <div key={item.label} className="border-l-2 border-primary/15 pl-3">
                  <p className={`font-mono text-[10px] uppercase tracking-[0.16em] ${item.done ? "text-emerald-700" : "text-muted-foreground"}`}>
                    {item.done ? "Complete" : "Open"}
                  </p>
                  <p className="mt-1 font-sans text-sm leading-relaxed text-foreground/85">
                    {item.label}
                  </p>
                </div>
              ))}
            </div>

            {aiSummary ? (
              <div className="space-y-4 border-t border-border/50 pt-5">
                <div className="space-y-2">
                  <div className="flex items-center gap-1">
                    <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                      PenKeep&apos;s summary
                    </p>
                    <InfoTip label="PenKeep's summary">
                      A plain summary generated from the three fields you wrote. Check it before saving because this is what monitoring will use.
                    </InfoTip>
                  </div>
                  <p className="font-sans text-sm leading-relaxed text-foreground/80">
                    {aiSummary}
                  </p>
                </div>

                {(monitorability || labels.length > 0) && (
                  <div className="flex flex-wrap gap-2">
                    {monitorability && (
                      <span className="inline-flex items-center gap-1">
                        <span className={`font-mono text-[10px] uppercase tracking-[0.12em] ${monitorabilityTone}`}>
                          {monitorability} monitorability
                        </span>
                        <InfoTip label="Monitorability">
                          How easily PenKeep can check this reason using public evidence. Specific metrics and events are easier to monitor than broad opinions.
                        </InfoTip>
                      </span>
                    )}
                    {labels.map((label) => (
                      <span key={label} className="border border-border/60 px-2 py-1 font-mono text-[10px] uppercase tracking-[0.1em] text-muted-foreground">
                        {label}
                      </span>
                    ))}
                  </div>
                )}

                {watchHintDescriptions.length > 0 && (
                  <div className="space-y-2">
                    <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                      Watch for
                    </p>
                    {watchHintDescriptions.map((description) => (
                      <div key={description} className="border border-border/60 bg-background/70 px-3 py-2">
                        <p className="font-sans text-sm leading-relaxed text-foreground/80">
                          {description}
                        </p>
                      </div>
                    ))}
                  </div>
                )}

                {ambiguityNote && (
                  <div className="border border-amber-500/20 bg-amber-500/5 px-3 py-3">
                    <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-amber-700">
                      Needs clearer wording
                    </p>
                    <p className="mt-2 font-sans text-sm leading-relaxed text-foreground/80">
                      {ambiguityNote}
                    </p>
                  </div>
                )}
              </div>
            ) : (
              <div className="space-y-2 border-t border-border/50 pt-5">
                <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                  After save
                </p>
                <p className="font-sans text-sm leading-relaxed text-foreground/80">
                  penKeep can generate signals, check earnings and headlines against the written case, and turn this page into a decision trail.
                </p>
              </div>
            )}
          </div>
        </aside>
      </div>
    </section>
  );
}
