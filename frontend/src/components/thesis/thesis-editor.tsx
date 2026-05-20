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

export function ThesisEditor({ thesis, onSave, onAssist, onCancel }: Props) {
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
        return `${hint.metric.replaceAll("_", " ")} should stay ${hint.operator} ${hint.threshold}.`;
      }
      return null;
    })
    .filter((value): value is string => Boolean(value));

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
        <CardTitle className="text-base">{thesis ? "Edit Thesis" : "Create Thesis"}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="rounded-xl border bg-muted/30 p-4">
          <p className="text-sm font-medium">What makes a strong thesis here</p>
          <p className="mt-1 text-sm text-muted-foreground">
            Be specific enough that you would know what changed. Good theses explain the reason for owning, what has to stay true, and what would clearly break the case.
          </p>
        </div>

        <div className="space-y-2">
          <Label>Why do you own this?</Label>
          <Textarea
            value={whyOwnIt}
            onChange={(e) => setWhyOwnIt(e.target.value)}
            rows={4}
            placeholder="Example: I own this because demand for AI infrastructure should keep revenue growth and margins strong for the next 3 years."
          />
        </div>

        <div className="space-y-2">
          <Label>What must remain true?</Label>
          <Textarea
            value={mustRemainTrue}
            onChange={(e) => setMustRemainTrue(e.target.value)}
            rows={3}
            placeholder="Example: Revenue growth stays healthy, margins hold up, and management keeps guiding confidently."
          />
        </div>

        <div className="space-y-2">
          <Label>What would change your mind?</Label>
          <Textarea
            value={changeMind}
            onChange={(e) => setChangeMind(e.target.value)}
            rows={3}
            placeholder="Example: Growth falls below expectations for multiple quarters or management signals weaker long-term demand."
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
            Save & Start Monitoring
          </Button>
          <Button variant="outline" onClick={onCancel}>Cancel</Button>
        </div>
      </CardContent>
    </Card>
  );
}
