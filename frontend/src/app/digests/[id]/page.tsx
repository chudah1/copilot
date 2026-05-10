"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { AuthGuard } from "@/components/layout/auth-guard";
import { Navbar } from "@/components/layout/navbar";
import { Card, CardContent } from "@/components/ui/card";
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
        <h1 className="mb-2 text-2xl font-bold">
          Digest: {formatDate(digest.period_start)} — {formatDate(digest.period_end)}
        </h1>
        <p className="mb-6 text-sm text-muted-foreground">
          {digest.sent_at ? `Sent ${formatDate(digest.sent_at)}` : "Not sent"}
        </p>
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
