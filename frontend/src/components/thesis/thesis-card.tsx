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

export function ThesisCard({ thesis, onEdit, onInvalidate }: Props) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <div className="flex items-center gap-2">
          <CardTitle className="text-base">Investment Thesis</CardTitle>
          <Badge className={statusColors[thesis.status]}>{thesis.status.replace("_", " ")}</Badge>
          <Badge className={convictionColors[thesis.conviction]}>{thesis.conviction} conviction</Badge>
          {thesis.ai_generated && <Badge variant="outline">AI generated</Badge>}
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
          <h4 className="text-sm font-medium text-muted-foreground">Bull Case</h4>
          <p className="mt-1">{thesis.bull_case}</p>
        </div>
        <div>
          <h4 className="text-sm font-medium text-muted-foreground">Key Metrics to Watch</h4>
          <ul className="mt-1 space-y-1">
            {thesis.key_metrics.map((m, i) => (
              <li key={i} className="text-sm">
                <code>{m.metric}</code> {m.operator} {m.threshold} — {m.rationale}
              </li>
            ))}
          </ul>
        </div>
        <div>
          <h4 className="text-sm font-medium text-muted-foreground">Risk Factors</h4>
          <p className="mt-1">{thesis.risk_factors}</p>
        </div>
        <p className="text-xs text-muted-foreground">
          Created {formatDate(thesis.created_at)} · Updated {formatDate(thesis.updated_at)}
        </p>
      </CardContent>
    </Card>
  );
}
