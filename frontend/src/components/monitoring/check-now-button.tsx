"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import type { CheckNowResponse } from "@/types";

interface CheckNowButtonProps {
  holdingId: string;
  onComplete: () => void;
}

export function CheckNowButton({ holdingId, onComplete }: CheckNowButtonProps) {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<CheckNowResponse | null>(null);

  const handleCheckNow = async () => {
    try {
      setLoading(true);
      setResult(null);
      const res = await api.post<CheckNowResponse>(`/api/monitoring/holdings/${holdingId}/check-now`);
      setResult(res);
      if (res.status === "completed") {
        onComplete();
      }
    } catch (err) {
      console.error("Check now failed:", err);
    } finally {
      setLoading(false);
    }
  };

  const nextAvailable = result?.next_available_at ? new Date(result.next_available_at) : null;
  const isRateLimited = result?.status === "rate_limited";

  return (
    <div className="flex items-center gap-3">
      <Button
        variant="outline"
        size="sm"
        onClick={handleCheckNow}
        disabled={loading || isRateLimited}
      >
        {loading ? "Checking..." : "Check now"}
      </Button>
      {result && result.status === "completed" && (
        <span className="text-xs text-muted-foreground">
          {result.events_created} event{result.events_created !== 1 ? "s" : ""} found
        </span>
      )}
      {isRateLimited && nextAvailable && (
        <span className="text-xs text-muted-foreground">
          Next available {nextAvailable.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
        </span>
      )}
    </div>
  );
}
