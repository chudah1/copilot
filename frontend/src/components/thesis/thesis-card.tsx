"use client";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatDate } from "@/lib/utils";
import type { Thesis } from "@/types";

interface Props {
  thesis: Thesis;
  onEdit: () => void;
  onInvalidate: () => void;
}

const statusColors: Record<string, string> = {
  draft: "bg-gray-100 text-gray-800",
  active: "bg-green-100 text-green-800",
  needs_review: "bg-orange-100 text-orange-800",
  invalidated: "bg-red-100 text-red-800",
};

const convictionColors: Record<string, string> = {
  high: "bg-green-100 text-green-800",
  medium: "bg-yellow-100 text-yellow-800",
  low: "bg-red-100 text-red-800",
};

const monitorabilityColors: Record<string, string> = {
  high: "bg-emerald-100 text-emerald-800",
  medium: "bg-sky-100 text-sky-800",
  low: "bg-stone-200 text-stone-800",
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
    return `${hint.metric.replaceAll("_", " ")} should stay ${hint.operator} ${hint.threshold}.`;
  }
  return null;
}

export function ThesisCard({ thesis, onEdit, onInvalidate }: Props) {
  const { labels, watchHints, monitorability, ambiguityNote } = getInterpretation(thesis);

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <div className="flex items-center gap-2">
          <CardTitle className="text-base">Investment Thesis</CardTitle>
          <Badge className={statusColors[thesis.status]}>{thesis.status.replace("_", " ")}</Badge>
          <Badge className={convictionColors[thesis.confidence]}>{thesis.confidence} confidence</Badge>
          <Badge variant="outline">{thesis.source === "ai_assisted" ? "AI assisted" : "User authored"}</Badge>
        </div>
        <div className="flex gap-2">
          {thesis.status !== "invalidated" && (
            <>
              <button onClick={onEdit} className="text-sm text-blue-600 hover:underline">Edit</button>
              <button onClick={onInvalidate} className="text-sm text-red-600 hover:underline">Invalidate</button>
            </>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div>
          <h4 className="text-sm font-medium text-muted-foreground">Why You Own It</h4>
          <p className="mt-1">{thesis.why_own_it}</p>
        </div>
        {thesis.must_remain_true && (
          <div>
            <h4 className="text-sm font-medium text-muted-foreground">What Must Remain True</h4>
            <p className="mt-1">{thesis.must_remain_true}</p>
          </div>
        )}
        {thesis.what_would_change_my_mind && (
          <div>
            <h4 className="text-sm font-medium text-muted-foreground">What Would Change Your Mind</h4>
            <p className="mt-1">{thesis.what_would_change_my_mind}</p>
          </div>
        )}
        {thesis.ai_summary && (
          <div>
            <h4 className="text-sm font-medium text-muted-foreground">AI Summary</h4>
            <p className="mt-1 text-sm text-muted-foreground">{thesis.ai_summary}</p>
          </div>
        )}
        {(monitorability || labels.length > 0 || watchHints.length > 0 || ambiguityNote) && (
          <div className="rounded-xl border bg-muted/30 p-4">
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

            {watchHints.length > 0 && (
              <div className="mt-3 space-y-2">
                <p className="text-sm font-medium text-muted-foreground">What the app is watching</p>
                <div className="space-y-1">
                  {watchHints.map((hint, index) => {
                    const description = describeWatchHint(hint);
                    if (!description) return null;
                    return (
                      <p key={`${description}-${index}`} className="text-sm text-muted-foreground">
                        {description}
                      </p>
                    );
                  })}
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
        <p className="text-xs text-muted-foreground">
          Created {formatDate(thesis.created_at)} · Updated {formatDate(thesis.updated_at)}
        </p>
      </CardContent>
    </Card>
  );
}
