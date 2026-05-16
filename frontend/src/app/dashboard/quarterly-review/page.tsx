"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { api } from "@/lib/api";
import { getErrorMessage } from "@/lib/errors";
import { formatCurrency } from "@/lib/utils";
import type { QuarterlyReviewCurrent, QuarterlyReviewHolding, QuarterlyReviewSubmission } from "@/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";

const RESPONSE_OPTIONS: Array<{
  value: "yes_absolutely" | "probably" | "not_sure" | "no";
  label: string;
  description: string;
}> = [
  {
    value: "yes_absolutely",
    label: "Yes, absolutely",
    description: "Your reason still feels strong at today's price.",
  },
  {
    value: "probably",
    label: "Probably",
    description: "The reason still works, but with a little less certainty.",
  },
  {
    value: "not_sure",
    label: "Not sure",
    description: "Something feels off and this reason needs another pass.",
  },
  {
    value: "no",
    label: "No",
    description: "You would not start this position today for the same reason.",
  },
];

export default function QuarterlyReviewPage() {
  const [review, setReview] = useState<QuarterlyReviewCurrent | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState<QuarterlyReviewSubmission["response"] | null>(null);
  const [lastSubmitted, setLastSubmitted] = useState<QuarterlyReviewSubmission | null>(null);

  const refreshReview = async (options?: { preserveLoading?: boolean }) => {
    try {
      const current = await api.get<QuarterlyReviewCurrent>("/api/quarterly-review/current");
      setReview(current);
      setLoadError(null);
    } catch (err) {
      setLoadError(getErrorMessage(err, "Failed to load quarterly review"));
    } finally {
      if (!options?.preserveLoading) {
        setLoading(false);
      }
    }
  };

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      try {
        const current = await api.get<QuarterlyReviewCurrent>("/api/quarterly-review/current");
        if (cancelled) {
          return;
        }
        setReview(current);
        setLoadError(null);
      } catch (err) {
        if (cancelled) {
          return;
        }
        setLoadError(getErrorMessage(err, "Failed to load quarterly review"));
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  const pendingHoldings = useMemo(
    () => review?.holdings.filter((holding) => holding.response === null) ?? [],
    [review],
  );

  const currentHolding: QuarterlyReviewHolding | null = pendingHoldings[0] ?? null;

  const handleSubmit = async (response: QuarterlyReviewSubmission["response"]) => {
    if (!currentHolding) {
      return;
    }

    try {
      setSubmitting(response);
      const result = await api.post<QuarterlyReviewSubmission>("/api/quarterly-review/current/respond", {
        holding_id: currentHolding.holding_id,
        response,
        notes: notes.trim() || undefined,
      });
      setLastSubmitted(result);
      setNotes("");
      toast.success(`${currentHolding.ticker} logged for ${review?.quarter ?? "this quarter"}.`);
      await refreshReview({ preserveLoading: true });
    } catch (err) {
      toast.error(getErrorMessage(err, "Failed to save quarterly review"));
    } finally {
      setSubmitting(null);
    }
  };

  if (loading) {
    return <div className="py-16 text-center text-stone-500">Loading quarterly review...</div>;
  }

  if (loadError) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-4 py-12 text-center">
          <p className="text-stone-500">{loadError}</p>
          <Button onClick={() => { setLoading(true); void refreshReview(); }}>Try again</Button>
        </CardContent>
      </Card>
    );
  }

  if (!review || review.total_holdings === 0) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <p className="text-lg font-medium">No current reasons are ready for quarterly review.</p>
          <p className="mt-2 text-sm text-stone-500">
            Add a holding reason first and this flow will appear once there is something worth revisiting.
          </p>
          <div className="mt-6">
            <Link href="/dashboard">
              <Button>Back to dashboard</Button>
            </Link>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!currentHolding) {
    return (
      <div className="space-y-6">
        <Card className="border-0 bg-[linear-gradient(135deg,rgba(29,37,53,0.98),rgba(47,89,72,0.92)_58%,rgba(229,236,223,0.95))] text-white">
          <CardHeader>
            <div className="flex flex-wrap items-center gap-2">
              <Badge className="bg-white/12 text-white">{review.quarter}</Badge>
              <Badge className="bg-white/12 text-white">{review.completed_count} reviewed</Badge>
            </div>
            <CardTitle className="text-3xl font-semibold tracking-tight text-white">
              Quarterly review complete
            </CardTitle>
            <CardDescription className="text-white/80">
              Every current reason has been revisited for this quarter. Reason age keeps compounding; the log now has the latest answer.
            </CardDescription>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-xl">Reviewed holdings</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {review.holdings.map((holding) => (
              <div key={holding.holding_id} className="rounded-2xl border p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="font-medium">{holding.ticker} · {holding.name}</p>
                    <p className="mt-1 text-sm text-stone-500">
                      Reason age: {holding.reason_age_days} days
                    </p>
                  </div>
                  <Badge variant="outline">{holding.response?.replace("_", " ")}</Badge>
                </div>
                {holding.response_notes && (
                  <p className="mt-3 text-sm text-stone-600">{holding.response_notes}</p>
                )}
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    );
  }

  const currentIndex = review.completed_count + 1;

  return (
    <div className="space-y-6">
      <Card className="border-0 bg-[linear-gradient(135deg,rgba(31,41,55,0.98),rgba(56,94,80,0.92)_58%,rgba(232,236,224,0.96))] text-white">
        <CardHeader className="gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <Badge className="bg-white/12 text-white">{review.quarter}</Badge>
            <Badge className="bg-white/12 text-white">
              {currentIndex} of {review.total_holdings}
            </Badge>
          </div>
          <CardTitle className="text-3xl font-semibold tracking-tight text-white">
            Would you buy this today?
          </CardTitle>
          <CardDescription className="max-w-2xl text-white/80">
            Keep this simple and honest. The goal is not to predict the market, only to test whether your reason still deserves fresh capital.
          </CardDescription>
        </CardHeader>
      </Card>

      <div className="grid gap-6 lg:grid-cols-[1.15fr_0.85fr]">
        <Card>
          <CardHeader>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <CardTitle className="text-2xl">{currentHolding.ticker} · {currentHolding.name}</CardTitle>
                <CardDescription className="mt-2">
                  Reason age: {currentHolding.reason_age_days} days
                  {currentHolding.current_price !== null && (
                    <> · Current price: {formatCurrency(currentHolding.current_price, currentHolding.currency)}</>
                  )}
                </CardDescription>
              </div>
              <Link href={`/dashboard/positions/${currentHolding.ticker}`}>
                <Button variant="outline">Open holding</Button>
              </Link>
            </div>
          </CardHeader>
          <CardContent className="space-y-5">
            <div className="rounded-2xl border bg-stone-50 p-4">
              <p className="text-sm font-medium text-stone-500">Your reason</p>
              <p className="mt-3 whitespace-pre-wrap text-base leading-7 text-stone-900">
                {currentHolding.why_own_it}
              </p>
            </div>

            <div className="space-y-3">
              <Label htmlFor="quarterly-notes">Notes for your future self</Label>
              <Textarea
                id="quarterly-notes"
                value={notes}
                onChange={(event) => setNotes(event.target.value)}
                placeholder="What changed, if anything?"
                rows={4}
              />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-xl">Your answer</CardTitle>
            <CardDescription>
              Pick the one that is closest to the truth. A weaker answer will keep this holding on your radar.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {RESPONSE_OPTIONS.map((option) => (
              <button
                key={option.value}
                type="button"
                onClick={() => void handleSubmit(option.value)}
                disabled={submitting !== null}
                className="w-full rounded-2xl border p-4 text-left transition hover:border-stone-400 hover:bg-stone-50 disabled:cursor-not-allowed disabled:opacity-60"
              >
                <div className="flex items-center justify-between gap-3">
                  <p className="font-medium">{option.label}</p>
                  {submitting === option.value && <Badge variant="outline">Saving…</Badge>}
                </div>
                <p className="mt-2 text-sm text-stone-500">{option.description}</p>
              </button>
            ))}

            {lastSubmitted && ["not_sure", "no"].includes(lastSubmitted.response) && (
              <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
                This answer keeps the holding in review. The best next move is to tighten or rewrite the reason on the holding page.
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
