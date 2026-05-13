"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { AuthGuard } from "@/components/layout/auth-guard";
import { Navbar } from "@/components/layout/navbar";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { formatDate } from "@/lib/utils";
import type { Digest } from "@/types";

export default function DigestDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [digest, setDigest] = useState<Digest | null>(null);

  useEffect(() => {
    api.get<Digest>(`/api/digests/${id}`).then(setDigest);
  }, [id]);

  if (!digest) return <p>Loading...</p>;

  return (
    <AuthGuard>
      <Navbar />
      <main className="mx-auto max-w-4xl px-4 py-6">
        <Card className="mb-6 border-0 bg-[linear-gradient(135deg,rgba(23,28,42,0.98),rgba(36,67,56,0.94)_55%,rgba(225,231,214,0.96))] text-white ring-0">
          <CardHeader className="gap-3">
            <div className="flex flex-wrap items-center gap-2">
              <Badge className="bg-white/12 text-white">{digest.status}</Badge>
              <Badge className="bg-white/12 text-white">{digest.content.events_count || 0} events</Badge>
              <Badge className="bg-white/12 text-white">{digest.content.holdings_count || 0} holdings</Badge>
            </div>
            <CardTitle className="text-3xl font-semibold tracking-tight text-white">
              {digest.content.headline || `Digest: ${formatDate(digest.period_start)} — ${formatDate(digest.period_end)}`}
            </CardTitle>
            <CardDescription className="text-white/80">
              {digest.sent_at ? `Sent ${formatDate(digest.sent_at)}` : "Not sent"} • Review window {formatDate(digest.period_start)} — {formatDate(digest.period_end)}
            </CardDescription>
          </CardHeader>
          {(digest.content.summary_points?.length || digest.content.missing_theses_count || digest.content.stale_theses_count || digest.content.concentration_warning) && (
            <CardContent className="grid gap-4 md:grid-cols-[1.2fr_0.8fr]">
              <div className="rounded-2xl border border-white/12 bg-white/8 p-4 backdrop-blur">
                <p className="text-sm text-white/70">Key takeaways</p>
                <div className="mt-3 space-y-2">
                  {(digest.content.summary_points || []).map((point) => (
                    <p key={point} className="text-sm text-white/85">
                      {point}
                    </p>
                  ))}
                </div>
              </div>
              <div className="rounded-2xl border border-white/12 bg-white/8 p-4 backdrop-blur">
                <p className="text-sm text-white/70">Digest stats</p>
                <div className="mt-3 grid grid-cols-2 gap-3 text-sm">
                  <div>
                    <p className="text-white/65">Stable holdings</p>
                    <p className="mt-1 text-lg font-semibold">{digest.content.stable_holdings_count || 0}</p>
                  </div>
                  <div>
                    <p className="text-white/65">Missing theses</p>
                    <p className="mt-1 text-lg font-semibold">{digest.content.missing_theses_count || 0}</p>
                  </div>
                  <div>
                    <p className="text-white/65">Stale theses</p>
                    <p className="mt-1 text-lg font-semibold">{digest.content.stale_theses_count || 0}</p>
                  </div>
                  <div>
                    <p className="text-white/65">Concentration</p>
                    <p className="mt-1 text-sm">{digest.content.concentration_warning || "No high concentration warning"}</p>
                  </div>
                </div>
              </div>
            </CardContent>
          )}
        </Card>
        <Card>
          <CardContent className="py-6">
            {digest.content.html ? (
              <div dangerouslySetInnerHTML={{ __html: digest.content.html }} />
            ) : (
              <p className="text-muted-foreground">Digest content unavailable.</p>
            )}
          </CardContent>
        </Card>
      </main>
    </AuthGuard>
  );
}
