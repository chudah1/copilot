"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { AuthGuard } from "@/components/layout/auth-guard";
import { Navbar } from "@/components/layout/navbar";
import { Card, CardContent } from "@/components/ui/card";
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
        <h1 className="mb-6 text-2xl font-bold">Past Digests</h1>
        {digests.length === 0 ? (
          <p className="text-muted-foreground">No digests yet. Your first digest will be sent on Sunday.</p>
        ) : (
          <div className="space-y-3">
            {digests.map((d) => (
              <Link key={d.id} href={`/digests/${d.id}`}>
                <Card className="hover:bg-muted/50 cursor-pointer">
                  <CardContent className="flex items-center justify-between py-4">
                    <div>
                      <p className="font-medium">
                        Week of {formatDate(d.period_start)} — {formatDate(d.period_end)}
                      </p>
                      <p className="text-sm text-muted-foreground">
                        {d.content.events_count || 0} events across {d.content.holdings_count || 0} holdings
                      </p>
                    </div>
                    <Badge variant={d.status === "sent" ? "default" : "destructive"}>{d.status}</Badge>
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
