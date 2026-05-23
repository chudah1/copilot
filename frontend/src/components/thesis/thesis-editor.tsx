"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getErrorMessage } from "@/lib/errors";
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
    what_would_change_my_mind: string | null;
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
  const [whyOwnIt, setWhyOwnIt] = useState(asText(thesis?.why_own_it));
  const [mustRemainTrue, setMustRemainTrue] = useState(asText(thesis?.must_remain_true));
  const [changeMind, setChangeMind] = useState(asText(thesis?.what_would_change_my_mind));
  const [confidence, setConfidence] = useState<"high" | "medium" | "low">(thesis?.confidence ?? "medium");
  const [aiSummary, setAiSummary] = useState(asText(thesis?.ai_summary));
  const [interpretation, setInterpretation] = useState<Record<string, unknown> | null>(thesis?.interpretation ?? null);
  const [assisting, setAssisting] = useState(false);
  const [assistError, setAssistError] = useState("");

  const interpretationData = interpretation ?? {};
  const watchHints = Array.isArray(interpretationData.watch_hints)
    ? interpretationData.watch_hints.filter((hint): hint is Record<string, unknown> => typeof hint === "object" && hint !== null)
    : [];
  const labels = Array.isArray(interpretationData.labels)
    ? interpretationData.labels.filter((label): label is string => typeof label === "string" && label.length > 0)
    : [];
  const monitorability = typeof interpretationData.monitorability === "string" ? interpretationData.monitorability : null;
  const ambiguityNote = typeof interpretationData.ambiguity_note === "string" ? interpretationData.ambiguity_note : "";

  const METRIC_LABELS: Record<string, string> = {
    revenue_growth_yoy: "Revenue growth (YoY)",
    earnings_growth_yoy: "Earnings growth (YoY)",
    pe_ratio: "P/E ratio",
    dividend_yield: "Dividend yield",
    gross_margin: "Gross margin",
    operating_margin: "Operating margin",
  };
  const RATIO_KEYWORDS = ["margin", "share", "growth", "yield", "rate", "pct", "percent", "coverage"];
  const LABEL_ABBREVS = new Set(["ai", "ml", "pe", "ev", "roi", "yoy", "qoq", "ytd"]);
  const watchHintDescriptions = watchHints
    .map((hint) => {
      if (hint.kind === "price_move_pct" && typeof hint.threshold === "number") {
        return `Review if price moves ${hint.threshold}% or more.`;
      }
      if (
        hint.kind === "metric_threshold" &&
        typeof hint.metric === "string" &&
        typeof hint.operator === "string" &&
        typeof hint.threshold === "number"
      ) {
        if (hint.threshold === 0) return null;
        const m = hint.metric;
        const label = METRIC_LABELS[m] ?? m.replaceAll("_", " ").replace(/\b\w+/g, w => LABEL_ABBREVS.has(w.toLowerCase()) ? w.toUpperCase() : w[0].toUpperCase() + w.slice(1));
        const t = hint.threshold as number;
        const isRatio = RATIO_KEYWORDS.some(k => m.toLowerCase().includes(k));
        const fmt = isRatio
          ? `${Math.abs(t) <= 1 ? (t * 100) % 1 === 0 ? (t * 100).toFixed(0) : (t * 100).toFixed(1) : t}%`
          : String(t);
        return `${label} stays ${hint.operator} ${fmt}.`;
      }
      return null;
    })
    .filter((value): value is string => Boolean(value));

  const baseCopy = investorProfile === "thesis_driven"
    ? {
        title: thesis ? "Edit thesis" : "Write your thesis",
        helperTitle: "What makes a strong thesis here",
        helperBody: "Be specific enough that you would know which assumption changed. A strong thesis explains why you own this, what must remain true, and what would clearly break the case.",
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
          helperBody: "Turn the original story into something testable. A strong reason explains why you own this, what has to stay true, and what would clearly prove the story wrong.",
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
          helperBody: "Be specific enough that you would know what changed. A good reason explains why you own this, what has to stay true, and what would clearly break the case.",
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
          helperBody: "Keep what is still true, but remove the part of the story that already broke. The next version should make it obvious why you still own this and what would prove the new reason wrong.",
          saveLabel: "Save rewritten reason",
        }
      : {
          title: "Rewrite the thesis",
          helperTitle: "What to rewrite this time",
          helperBody: "Keep what is still true, but remove the assumption that already broke. The next version should make it obvious why you still own this and what would invalidate the new thesis.",
          saveLabel: "Save rewritten thesis",
        }
    : mode === "tighten"
      ? investorProfile === "hearsay_driven"
        ? {
            title: "Tighten the reason",
            helperTitle: "What to tighten here",
            helperBody: "Make the business driver clearer, make the break condition sharper, and remove any language that still sounds like a loose story.",
            saveLabel: "Save tighter reason",
          }
        : {
            title: "Tighten the thesis",
            helperTitle: "What to tighten here",
            helperBody: "Make the core assumption more specific, sharpen the break condition, and cut wording we can't tie to real evidence.",
            saveLabel: "Save tighter thesis",
          }
      : mode === "first_write"
        ? investorProfile === "hearsay_driven"
          ? {
              title: "Write the real reason",
              helperTitle: "Turn the story into something testable",
              helperBody: "Start with why it caught your eye, then nail what would prove you wrong. Messy is fine — vague isn't. We'll watch for evidence against what you write and nudge you to revisit on a schedule, not only when you're rattled.",
              saveLabel: "Save reason and start watching",
            }
          : {
              title: "Write the thesis",
              helperTitle: "Make the position monitorable",
              helperBody: "Why you own it, what has to stay true, and what would make you sell. Not a sell-side note — a short case we can check against news and earnings, with reminders to re-read it before the tape does your thinking for you.",
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
      setChangeMind(asText(result.what_would_change_my_mind) || changeMind);
      setAiSummary(asText(result.ai_summary));
      setInterpretation(result.interpretation);
    } catch (error: unknown) {
      setAssistError(getErrorMessage(error, "Failed to assist thesis draft"));
    } finally {
      setAssisting(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{copy.title}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="rounded-xl border bg-muted/30 p-4">
          <p className="text-sm font-medium">{copy.helperTitle}</p>
          <p className="mt-1 text-sm text-muted-foreground">
            {copy.helperBody}
          </p>
        </div>

        <div className="space-y-2">
          <Label>{copy.why}</Label>
          <Textarea
            value={whyOwnIt}
            onChange={(e) => setWhyOwnIt(e.target.value)}
            rows={4}
            placeholder={copy.whyPlaceholder}
          />
        </div>

        <div className="space-y-2">
          <Label>{copy.must}</Label>
          <Textarea
            value={mustRemainTrue}
            onChange={(e) => setMustRemainTrue(e.target.value)}
            rows={3}
            placeholder={copy.mustPlaceholder}
          />
        </div>

        <div className="space-y-2">
          <Label>{copy.breaks}</Label>
          <Textarea
            value={changeMind}
            onChange={(e) => setChangeMind(e.target.value)}
            rows={3}
            placeholder={copy.breaksPlaceholder}
          />
        </div>

        <div className="space-y-2">
          <Label>Confidence</Label>
          <Select value={confidence} onValueChange={(v) => v && setConfidence(v as "high" | "medium" | "low")}>
            <SelectTrigger className="w-40"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="high">High</SelectItem>
              <SelectItem value="medium">Medium</SelectItem>
              <SelectItem value="low">Low</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-2">
          <Label>AI Assist</Label>
          <div className="flex gap-2">
            <Button type="button" variant="outline" onClick={handleAssist} disabled={assisting || whyOwnIt.trim().length === 0}>
              {assisting ? "Thinking..." : "Refine with AI"}
            </Button>
          </div>
          {assistError && <p className="text-sm text-red-500">{assistError}</p>}
          {aiSummary && (
            <div className="rounded-xl border bg-muted/30 p-4">
              <p className="text-sm font-medium">AI Summary</p>
              <p className="mt-1 text-sm text-muted-foreground">{aiSummary}</p>
              {(monitorability || labels.length > 0 || watchHintDescriptions.length > 0 || ambiguityNote) && (
                <div className="mt-4 space-y-3 border-t pt-4">
                  <div className="flex flex-wrap items-center gap-2">
                    {monitorability && (
                      <span className="rounded-full bg-background px-2 py-1 text-xs font-medium text-muted-foreground">
                        {monitorability} monitorability
                      </span>
                    )}
                    {labels.map((label) => (
                      <span key={label} className="rounded-full border px-2 py-1 text-xs text-muted-foreground">
                        {label}
                      </span>
                    ))}
                  </div>
                  {watchHintDescriptions.length > 0 && (
                    <div className="space-y-1">
                      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Proposed monitoring</p>
                      {watchHintDescriptions.map((description) => (
                        <p key={description} className="text-sm text-muted-foreground">
                          {description}
                        </p>
                      ))}
                    </div>
                  )}
                  {ambiguityNote && (
                    <div className="rounded-lg bg-background/80 p-3">
                      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Ambiguity note</p>
                      <p className="mt-1 text-sm text-muted-foreground">{ambiguityNote}</p>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>

        <div className="flex gap-2">
          <Button
            onClick={() =>
              onSave({
                thesis_kind: "company",
                why_own_it: whyOwnIt,
                must_remain_true: mustRemainTrue || null,
                what_would_change_my_mind: changeMind || null,
                confidence,
                review_cadence_days: thesis?.review_cadence_days ?? 7,
                ai_summary: aiSummary || null,
                interpretation,
                source: aiSummary ? "ai_assisted" : "user",
                status: "active",
              })
            }
            disabled={whyOwnIt.trim().length === 0}
          >
            {copy.saveLabel}
          </Button>
          <Button variant="outline" onClick={onCancel}>Cancel</Button>
        </div>
      </CardContent>
    </Card>
  );
}
