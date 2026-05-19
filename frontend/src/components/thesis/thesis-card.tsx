"use client";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { formatDate } from "@/lib/utils";
import type { Thesis } from "@/types";

interface Props {
  thesis: Thesis;
  onEdit: () => void;
  onInvalidate: () => void;
}

const statusColors: Record<string, string> = {
  draft: "bg-muted text-muted-foreground",
  active: "bg-emerald-500/15 text-emerald-700",
  needs_review: "bg-orange-500/15 text-orange-600",
  invalidated: "bg-red-500/15 text-red-600",
};

const convictionColors: Record<string, string> = {
  high: "bg-emerald-500/15 text-emerald-700",
  medium: "bg-amber-500/15 text-amber-700",
  low: "bg-red-500/15 text-red-600",
};

const monitorabilityColors: Record<string, string> = {
  high: "bg-emerald-500/15 text-emerald-700",
  medium: "bg-sky-500/15 text-sky-700",
  low: "bg-muted text-muted-foreground",
};

function getInterpretation(thesis: Thesis) {
  const interpretation = thesis.interpretation ?? {};
  const labels = Array.isArray(interpretation.labels)
    ? interpretation.labels.filter((label): label is string => typeof label === "string" && label.length > 0)
    : [];
  const watchHints = Array.isArray(interpretation.watch_hints)
    ? interpretation.watch_hints.filter((hint): hint is Record<string, unknown> => typeof hint === "object" && hint !== null)
    : [];
  const monitorability = typeof interpretation.monitorability === "string" ? interpretation.monitorability : null;
  const ambiguityNote = typeof interpretation.ambiguity_note === "string" ? interpretation.ambiguity_note : "";

  return { labels, watchHints, monitorability, ambiguityNote };
}

const METRIC_LABELS: Record<string, string> = {
  revenue_growth_yoy: "Revenue growth (YoY)",
  earnings_growth_yoy: "Earnings growth (YoY)",
  pe_ratio: "P/E ratio",
  dividend_yield: "Dividend yield",
};

function describeWatchHint(hint: Record<string, unknown>) {
  if (hint.kind === "price_move_pct" && typeof hint.threshold === "number") {
    return `Review if price moves ${hint.threshold}% or more.`;
  }
  if (
    hint.kind === "metric_threshold" &&
    typeof hint.metric === "string" &&
    typeof hint.operator === "string" &&
    typeof hint.threshold === "number"
  ) {
    const label = METRIC_LABELS[hint.metric] ?? hint.metric.replaceAll("_", " ");
    return `${label} should stay ${hint.operator} ${hint.threshold}.`;
  }
  return null;
}

export function ThesisCard({ thesis, onEdit, onInvalidate }: Props) {
  const { labels, watchHints, monitorability, ambiguityNote } = getInterpretation(thesis);
  const watchDescriptions = watchHints
    .map((hint) => describeWatchHint(hint))
    .filter((description): description is string => Boolean(description));

  return (
    <Card>
      <CardHeader className="gap-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <CardTitle className="text-base">Current thesis</CardTitle>
              <Badge className={statusColors[thesis.status]}>{thesis.status.replace("_", " ")}</Badge>
              <Badge className={convictionColors[thesis.confidence]}>{thesis.confidence} confidence</Badge>
              <Badge variant="outline">{thesis.source === "ai_assisted" ? "AI assisted" : "User authored"}</Badge>
            </div>
            <CardDescription>
              This is the working reason for owning the position. Keep it tight enough that a future version of you can tell when it broke.
            </CardDescription>
          </div>
          <div className="flex gap-3 text-sm">
            <button onClick={onEdit} className="text-primary/80 hover:text-primary transition-colors">
              Edit
            </button>
            {thesis.status !== "invalidated" && (
              <button onClick={onInvalidate} className="text-red-600/70 hover:text-red-600 transition-colors">
                Invalidate
              </button>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-3 md:grid-cols-3">
          <ThesisBlock
            label="Own it because"
            text={thesis.why_own_it}
            tone="bg-background"
          />
          <ThesisBlock
            label="Still true if"
            text={thesis.must_remain_true ?? "You have not defined the condition that must remain true yet."}
            tone={thesis.must_remain_true ? "bg-background" : "bg-amber-500/8"}
          />
          <ThesisBlock
            label="Breaks if"
            text={thesis.what_would_change_my_mind ?? "You have not written the exit condition yet."}
            tone={thesis.what_would_change_my_mind ? "bg-background" : "bg-red-500/8"}
          />
        </div>

        {(monitorability || labels.length > 0 || watchHints.length > 0 || ambiguityNote) && (
          <div className="rounded-xl border bg-muted/30 p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex flex-wrap items-center gap-2">
                {monitorability && (
                  <Badge className={monitorabilityColors[monitorability] ?? monitorabilityColors.low}>
                    {monitorability} monitorability
                  </Badge>
                )}
                {labels.map((label) => (
                  <Badge key={label} variant="outline">
                    {label}
                  </Badge>
                ))}
              </div>
              <p className="text-xs text-muted-foreground">
                Updated {formatDate(thesis.updated_at)}
              </p>
            </div>

            {watchDescriptions.length > 0 && (
              <div className="mt-3">
                <p className="text-sm font-medium text-muted-foreground">What the app is watching</p>
                <div className="mt-2 grid gap-2 md:grid-cols-2">
                  {watchDescriptions.map((description, index) => (
                    <div key={`${description}-${index}`} className="rounded-lg border bg-background/80 p-3">
                      <p className="text-sm text-muted-foreground">{description}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {ambiguityNote && (
              <div className="mt-3 rounded-lg bg-background/80 p-3">
                <p className="text-sm font-medium text-muted-foreground">Ambiguity</p>
                <p className="mt-1 text-sm text-muted-foreground">{ambiguityNote}</p>
              </div>
            )}
          </div>
        )}

        {thesis.ai_summary && (
          <div className="rounded-lg border border-dashed p-3">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Summary</p>
            <p className="mt-1 text-sm text-muted-foreground">{thesis.ai_summary}</p>
          </div>
        )}

        <p className="text-xs text-muted-foreground">
          Created {formatDate(thesis.created_at)} · Last reviewed {formatDate(thesis.updated_at)}
        </p>
      </CardContent>
    </Card>
  );
}

function ThesisBlock({
  label,
  text,
  tone,
}: {
  label: string;
  text: string;
  tone: string;
}) {
  return (
    <div className={`rounded-xl border p-4 ${tone}`}>
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="mt-2 text-sm leading-6">{text}</p>
    </div>
  );
}
