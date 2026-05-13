"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { AuthGuard } from "@/components/layout/auth-guard";
import { Navbar } from "@/components/layout/navbar";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { formatDate } from "@/lib/utils";
import type { Digest } from "@/types";

export default function DigestsPage() {
  const [digests, setDigests] = useState<Digest[]>([]);

  useEffect(() => {
    api.get<Digest[]>("/api/digests").then(setDigests);
  }, []);

  return (
    <AuthGuard>
      <Navbar />
      <main className="mx-auto max-w-4xl px-4 py-6">
        <Card className="mb-6 border-0 bg-[linear-gradient(135deg,rgba(23,28,42,0.98),rgba(32,59,70,0.94)_55%,rgba(218,227,232,0.96))] text-white ring-0">
          <CardHeader>
            <CardTitle className="text-3xl font-semibold tracking-tight text-white">Weekly investor reviews</CardTitle>
            <CardDescription className="max-w-2xl text-white/80">
              Each digest summarizes what changed, what stayed stable, and where your own thesis needs a decision from you.
            </CardDescription>
          </CardHeader>
        </Card>
        {digests.length === 0 ? (
          <Card>
            <CardContent className="py-8">
              <p className="font-medium">No digests yet.</p>
              <p className="mt-2 text-sm text-muted-foreground">
                Your first digest will land on Sunday after there is at least one holding with a current thesis and monitoring is active.
              </p>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-3">
            {digests.map((d) => (
              <Link key={d.id} href={`/digests/${d.id}`}>
                <Card className="cursor-pointer transition-colors hover:bg-muted/50">
                  <CardContent className="py-5">
                    <div className="flex items-start justify-between gap-4">
                      <div className="space-y-3">
                        <div>
                          <p className="font-medium">
                            Week of {formatDate(d.period_start)} — {formatDate(d.period_end)}
                          </p>
                          <p className="mt-1 text-sm text-muted-foreground">
                            {d.content.headline || "Weekly thesis review"}
                          </p>
                        </div>
                        {d.content.summary_points && d.content.summary_points.length > 0 && (
                          <div className="space-y-1">
                            {d.content.summary_points.map((point) => (
                              <p key={point} className="text-sm text-muted-foreground">
                                {point}
                              </p>
                            ))}
                          </div>
                        )}
                        <div className="flex flex-wrap gap-2">
                          <Badge variant="outline">{d.content.events_count || 0} events</Badge>
                          <Badge variant="outline">{d.content.holdings_count || 0} holdings</Badge>
                          {!!d.content.stale_theses_count && <Badge variant="outline">{d.content.stale_theses_count} stale theses</Badge>}
                          {!!d.content.missing_theses_count && <Badge variant="outline">{d.content.missing_theses_count} missing theses</Badge>}
                        </div>
                      </div>
                      <div className="flex flex-col items-end gap-2">
                        <Badge variant={d.status === "sent" ? "default" : "destructive"}>{d.status}</Badge>
                        <p className="text-xs text-muted-foreground">
                          {d.sent_at ? `Sent ${formatDate(d.sent_at)}` : "Not sent"}
                        </p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </Link>
            ))}
          </div>
        )}
      </main>
    </AuthGuard>
  );
}
