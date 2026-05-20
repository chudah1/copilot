"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { CounterThesisResponse } from "@/types";

export function CounterThesisCard({ thesisId }: { thesisId: string }) {
  const [data, setData] = useState<CounterThesisResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
      <Card>
        <CardContent className="flex items-center justify-between py-4">
          <div>
            <p className="text-sm font-medium">Devil&apos;s Advocate</p>
            <p className="text-xs text-muted-foreground">Generate a bear case to stress-test your reason.</p>
          </div>
          <Button variant="outline" size="sm" onClick={generate}>
            Challenge reason
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (loading) {
    return (
      <Card>
        <CardContent className="py-4">
          <p className="text-sm text-muted-foreground animate-pulse">Generating bear case...</p>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <CardContent className="flex items-center justify-between py-4">
          <p className="text-sm text-red-600">{error}</p>
          <Button variant="outline" size="sm" onClick={generate}>Retry</Button>
        </CardContent>
      </Card>
    );
  }

  if (!data) return null;

  return (
    <Card>
      <CardHeader className="cursor-pointer pb-2" onClick={() => setExpanded(!expanded)}>
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">Devil&apos;s Advocate</CardTitle>
          <span className="text-xs text-muted-foreground">{expanded ? "collapse" : "expand"}</span>
        </div>
      </CardHeader>
      {expanded && (
        <CardContent className="space-y-4">
          <div>
            <p className="text-sm font-medium">Bear Case</p>
            <p className="mt-1 text-sm text-muted-foreground">{data.bear_case}</p>
          </div>
          {data.key_risks.length > 0 && (
            <div>
              <p className="text-sm font-medium">Key Risks</p>
              <ul className="mt-1 list-disc pl-4 text-sm text-muted-foreground">
                {data.key_risks.map((risk, i) => <li key={i}>{risk}</li>)}
              </ul>
            </div>
          )}
          {data.blind_spots.length > 0 && (
            <div>
              <p className="text-sm font-medium">Blind Spots</p>
              <ul className="mt-1 list-disc pl-4 text-sm text-muted-foreground">
                {data.blind_spots.map((spot, i) => <li key={i}>{spot}</li>)}
              </ul>
            </div>
          )}
          {data.suggested_additions.length > 0 && (
            <div>
              <p className="text-sm font-medium">Suggested Additions</p>
              <ul className="mt-1 list-disc pl-4 text-sm text-muted-foreground">
                {data.suggested_additions.map((s, i) => <li key={i}>{s}</li>)}
              </ul>
            </div>
          )}
        </CardContent>
      )}
    </Card>
  );
}
