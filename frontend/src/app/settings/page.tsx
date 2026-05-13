"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { AuthGuard } from "@/components/layout/auth-guard";
import { Navbar } from "@/components/layout/navbar";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import type { PortfolioSummary } from "@/types";

export default function SettingsPage() {
  const [frequency, setFrequency] = useState("weekly");
  const [sensitivity, setSensitivity] = useState("all");
  const [summary, setSummary] = useState<PortfolioSummary | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    api.get<{ digest_frequency: string; notification_sensitivity: string }>("/api/settings").then((s) => {
      setFrequency(s.digest_frequency);
      setSensitivity(s.notification_sensitivity);
    });
    api.get<PortfolioSummary>("/api/portfolio/summary").then(setSummary).catch(() => null);
  }, []);

  const handleSave = async () => {
    setSaving(true);
    await api.put("/api/settings", { digest_frequency: frequency, notification_sensitivity: sensitivity });
    setSaving(false);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <AuthGuard>
      <Navbar />
      <main className="mx-auto max-w-2xl px-4 py-6">
        <Card className="mb-6 border-0 bg-[linear-gradient(135deg,rgba(20,25,38,0.98),rgba(34,58,76,0.94)_55%,rgba(226,231,235,0.96))] text-white ring-0">
          <CardHeader>
            <CardTitle className="text-3xl font-semibold tracking-tight text-white">Preferences and monitoring</CardTitle>
            <CardDescription className="text-white/80">
              Control when we contact you and sanity-check whether monitoring is fully switched on for your portfolio.
            </CardDescription>
          </CardHeader>
          {summary && (
            <CardContent>
              <div className={`rounded-2xl border px-4 py-3 text-sm ${summary.monitoring_ready ? "border-emerald-200/20 bg-emerald-200/10 text-emerald-50" : "border-amber-200/20 bg-amber-200/10 text-amber-50"}`}>
                {summary.monitoring_message}
              </div>
            </CardContent>
          )}
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Digest Preferences</CardTitle>
            <CardDescription>Weekly digests are the core rhythm for MVP. We only offer frequencies that are actually implemented.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label>Digest Frequency</Label>
              <Select value={frequency} onValueChange={(v) => v && setFrequency(v)}>
                <SelectTrigger className="w-60"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="weekly">Weekly (Sunday 6pm)</SelectItem>
                  <SelectItem value="none">Disabled</SelectItem>
                </SelectContent>
              </Select>
              <p className="text-sm text-muted-foreground">
                Weekly works best for thesis review. It keeps the product high-signal instead of becoming another noisy alert feed.
              </p>
            </div>
            <div className="space-y-2">
              <Label>Notification Sensitivity</Label>
              <Select value={sensitivity} onValueChange={(v) => v && setSensitivity(v)}>
                <SelectTrigger className="w-60"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All events</SelectItem>
                  <SelectItem value="thesis_breaking_only">Thesis-breaking only</SelectItem>
                </SelectContent>
              </Select>
              <p className="text-sm text-muted-foreground">
                Use `All events` if you want regular review nudges. Use `Thesis-breaking only` if you only want the sharpest signal.
              </p>
            </div>
            <Button onClick={handleSave} disabled={saving}>
              {saving ? "Saving..." : saved ? "Saved" : "Save"}
            </Button>
          </CardContent>
        </Card>
      </main>
    </AuthGuard>
  );
}
