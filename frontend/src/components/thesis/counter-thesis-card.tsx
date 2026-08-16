"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import type { CounterThesisResponse } from "@/types";

export function CounterThesisCard({
  thesisId,
  investorProfile,
}: {
  thesisId: string;
  investorProfile?: "thesis_driven" | "hearsay_driven" | null;
}) {
  const [data, setData] = useState<CounterThesisResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const copy = investorProfile === "thesis_driven"
    ? {
        body: "See the opposite case before the market forces it on you.",
        cta: "Generate bear case",
      }
    : {
        body: "See the opposite case before the market forces it on you.",
        cta: "Generate bear case",
      };

  const generate = async () => {
    try {
      setLoading(true);
      setError(null);
      const result = await api.post<CounterThesisResponse>(`/api/theses/${thesisId}/counter-thesis`);
      setData(result);
      setExpanded(true);
    } catch (err) {
      setError("Failed to generate counter-thesis.");
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  if (!data && !loading) {
    return (
      <div className="product-panel p-5 sm:p-6">
        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">Counter case</p>
            <p className="mt-2 font-sans text-sm leading-relaxed text-foreground/80">{copy.body}</p>
          </div>
          <Button variant="outline" size="sm" onClick={generate}>
            {copy.cta}
          </Button>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="product-panel p-5 sm:p-6">
        <p className="text-sm text-muted-foreground animate-pulse">Generating bear case...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="product-panel p-5 sm:p-6">
        <div className="flex items-center justify-between gap-4">
          <p className="text-sm text-red-600">{error}</p>
          <Button variant="outline" size="sm" onClick={generate}>Retry</Button>
        </div>
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className="product-panel overflow-hidden">
      <div className="cursor-pointer border-b border-border/40 px-5 py-4 sm:px-6" onClick={() => setExpanded(!expanded)}>
        <div className="flex items-center justify-between">
          <div className="space-y-1">
            <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">Counter case</p>
            <p className="font-sans text-sm leading-relaxed text-foreground/80">
              Pressure-test the position against the opposite view.
            </p>
          </div>
          <span className="text-xs text-muted-foreground">{expanded ? "hide" : "show"}</span>
        </div>
      </div>
      {expanded && (
        <div className="space-y-4 px-5 py-5 sm:px-6">
          <div>
            <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">Bear case</p>
            <p className="mt-2 text-sm leading-relaxed text-foreground/80">{data.bear_case}</p>
          </div>
          {data.key_risks.length > 0 && (
            <div>
              <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">Key risks</p>
              <ul className="mt-2 list-disc pl-4 text-sm text-muted-foreground space-y-1">
                {data.key_risks.map((risk, i) => <li key={i}>{risk}</li>)}
              </ul>
            </div>
          )}
          {data.blind_spots.length > 0 && (
            <div>
              <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">Gaps to examine</p>
              <ul className="mt-2 list-disc pl-4 text-sm text-muted-foreground space-y-1">
                {data.blind_spots.map((spot, i) => <li key={i}>{spot}</li>)}
              </ul>
            </div>
          )}
          {data.suggested_additions.length > 0 && (
            <div>
              <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                {investorProfile === "hearsay_driven" ? "Add to the reason" : "Add to the thesis"}
              </p>
              <ul className="mt-2 list-disc pl-4 text-sm text-muted-foreground space-y-1">
                {data.suggested_additions.map((s, i) => <li key={i}>{s}</li>)}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
