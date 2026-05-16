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

interface UserPreferences {
  digest_frequency: string;
  digest_day: string;
  digest_time: string;
  earnings_alerts: boolean;
  quarterly_review_reminders: boolean;
  email_enabled: boolean;
  notification_sensitivity: string;
}

const DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"];

function Toggle({
  checked,
  onChange,
  label,
  description,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label: string;
  description?: string;
}) {
  const id = label.toLowerCase().replace(/\s+/g, "-");
  return (
    <div className="flex items-start justify-between gap-4">
      <div className="flex-1">
        <p id={id} className="text-sm font-medium">{label}</p>
        {description && <p className="text-sm text-muted-foreground mt-0.5">{description}</p>}
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-labelledby={id}
        onClick={() => onChange(!checked)}
        className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ${
          checked ? "bg-stone-900" : "bg-stone-200"
        }`}
      >
        <span
          className={`pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow-lg ring-0 transition-transform ${
            checked ? "translate-x-5" : "translate-x-0"
          }`}
        />
      </button>
    </div>
  );
}

export default function SettingsPage() {
  const [prefs, setPrefs] = useState<UserPreferences>({
    digest_frequency: "weekly",
    digest_day: "sunday",
    digest_time: "17:00",
    earnings_alerts: true,
    quarterly_review_reminders: true,
    email_enabled: true,
    notification_sensitivity: "all",
  });
  const [summary, setSummary] = useState<PortfolioSummary | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    api.get<UserPreferences>("/api/settings").then(setPrefs).catch(() => null);
    api.get<PortfolioSummary>("/api/portfolio/summary").then(setSummary).catch(() => null);
  }, []);

  const set = <K extends keyof UserPreferences>(key: K, value: UserPreferences[K]) =>
    setPrefs((p) => ({ ...p, [key]: value }));

  const handleSave = async () => {
    setSaving(true);
    try {
      const updated = await api.put<UserPreferences>("/api/settings", prefs);
      setPrefs(updated);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } finally {
      setSaving(false);
    }
  };

  return (
    <AuthGuard>
      <Navbar />
      <main className="mx-auto max-w-2xl px-4 py-6 space-y-6">
        <Card className="border-0 bg-[linear-gradient(135deg,rgba(20,25,38,0.98),rgba(34,58,76,0.94)_55%,rgba(226,231,235,0.96))] text-white ring-0">
          <CardHeader>
            <CardTitle className="text-3xl font-semibold tracking-tight text-white">
              Preferences
            </CardTitle>
            <CardDescription className="text-white/80">
              Control when and how Copilot Investor contacts you.
            </CardDescription>
          </CardHeader>
          {summary && (
            <CardContent>
              <div
                className={`rounded-2xl border px-4 py-3 text-sm ${
                  summary.monitoring_ready
                    ? "border-emerald-200/20 bg-emerald-200/10 text-emerald-50"
                    : "border-amber-200/20 bg-amber-200/10 text-amber-50"
                }`}
              >
                {summary.monitoring_message}
              </div>
            </CardContent>
          )}
        </Card>

        {/* Master kill switch */}
        <Card>
          <CardHeader>
            <CardTitle>Email</CardTitle>
            <CardDescription>
              Turning email off pauses all outbound messages — digests, earnings alerts, and onboarding drip.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Toggle
              checked={prefs.email_enabled}
              onChange={(v) => set("email_enabled", v)}
              label="Email enabled"
              description="When off, no emails are sent regardless of other settings."
            />
          </CardContent>
        </Card>

        {/* Digest settings */}
        <Card className={!prefs.email_enabled ? "opacity-50 pointer-events-none" : undefined}>
          <CardHeader>
            <CardTitle>Weekly digest</CardTitle>
            <CardDescription>
              Your portfolio summary sent on a schedule. Weekly is the default and works best for thesis review.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            <div className="space-y-2">
              <Label>Frequency</Label>
              <Select
                value={prefs.digest_frequency}
                onValueChange={(v) => v && set("digest_frequency", v)}
              >
                <SelectTrigger className="w-56">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="weekly">Weekly</SelectItem>
                  <SelectItem value="fortnightly">Fortnightly</SelectItem>
                  <SelectItem value="monthly">Monthly</SelectItem>
                  <SelectItem value="none">Disabled</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {prefs.digest_frequency !== "none" && (
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Day</Label>
                  <Select
                    value={prefs.digest_day}
                    onValueChange={(v) => v && set("digest_day", v)}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {DAYS.map((d) => (
                        <SelectItem key={d} value={d}>
                          {d.charAt(0).toUpperCase() + d.slice(1)}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Time</Label>
                  <input
                    type="time"
                    value={prefs.digest_time}
                    onChange={(e) => set("digest_time", e.target.value)}
                    className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  />
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Notification toggles */}
        <Card className={!prefs.email_enabled ? "opacity-50 pointer-events-none" : undefined}>
          <CardHeader>
            <CardTitle>Alerts</CardTitle>
            <CardDescription>
              Individual email alert types. Each can be switched off independently.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            <Toggle
              checked={prefs.earnings_alerts}
              onChange={(v) => set("earnings_alerts", v)}
              label="Earnings alerts"
              description="In-app notification when a holding reports within 2 days. We also evaluate your reasons the morning after."
            />
            <Toggle
              checked={prefs.quarterly_review_reminders}
              onChange={(v) => set("quarterly_review_reminders", v)}
              label="Quarterly review reminders"
              description="Email at the start of each quarter prompting you to revisit every reason."
            />
          </CardContent>
        </Card>

        {/* Monitoring sensitivity */}
        <Card>
          <CardHeader>
            <CardTitle>Monitoring sensitivity</CardTitle>
            <CardDescription>
              Controls which monitoring events appear in your event timeline.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            <Label>Sensitivity</Label>
            <Select
              value={prefs.notification_sensitivity}
              onValueChange={(v) => v && set("notification_sensitivity", v)}
            >
              <SelectTrigger className="w-56">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All events</SelectItem>
                <SelectItem value="thesis_breaking_only">Thesis-breaking only</SelectItem>
              </SelectContent>
            </Select>
            <p className="text-sm text-muted-foreground">
              Use "Thesis-breaking only" if you only want the sharpest signal.
            </p>
          </CardContent>
        </Card>

        <div className="flex justify-end">
          <Button onClick={handleSave} disabled={saving} className="w-28">
            {saving ? "Saving…" : saved ? "Saved ✓" : "Save"}
          </Button>
        </div>
      </main>
    </AuthGuard>
  );
}
