"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { AppShell } from "@/components/layout/app-shell";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import type { PortfolioSummary, UserPreferences } from "@/types";

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
    <div className="flex items-start justify-between gap-6 py-4 border-b border-border/40 last:border-0">
      <div className="flex-1">
        <p id={id} className="font-sans text-sm text-foreground">{label}</p>
        {description && <p className="font-sans text-xs text-muted-foreground mt-1 leading-relaxed">{description}</p>}
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-labelledby={id}
        onClick={() => onChange(!checked)}
        className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background ${
          checked ? "bg-primary" : "bg-border"
        }`}
      >
        <span
          className={`pointer-events-none inline-block h-5 w-5 rounded-full shadow-lg ring-0 transition-transform ${
            checked ? "translate-x-5 bg-background" : "translate-x-0 bg-muted-foreground/60"
          }`}
        />
      </button>
    </div>
  );
}

function Section({ label, children, disabled }: { label: string; children: React.ReactNode; disabled?: boolean }) {
  return (
    <section className={`border-b border-border/60 pb-8 ${disabled ? "opacity-50 pointer-events-none" : ""}`}>
      <p className="font-mono text-[10px] uppercase tracking-[0.3em] text-muted-foreground mb-5">{label}</p>
      {children}
    </section>
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
    <AppShell>
      <div className="max-w-2xl mx-auto px-8 py-10 space-y-8">

        {/* Page header */}
        <div className="border-b border-border pb-6">
          <p className="font-mono text-[10px] uppercase tracking-[0.3em] text-muted-foreground mb-2">
            Account
          </p>
          <h1 className="font-display italic text-4xl text-foreground leading-tight">
            Preferences
          </h1>
          <p className="font-sans text-sm text-muted-foreground mt-2">
            Control when and how Copilot Investor contacts you.
          </p>
          {summary && (
            <div className={`mt-4 border px-4 py-3 text-sm font-sans leading-relaxed ${
              summary.monitoring_ready
                ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-700/90"
                : "border-amber-500/20 bg-amber-500/10 text-amber-700/90"
            }`}>
              {summary.monitoring_message}
            </div>
          )}
        </div>

        {/* Email master switch */}
        <Section label="Email">
          <p className="font-sans text-xs text-muted-foreground mb-4 leading-relaxed">
            Turning email off pauses all outbound messages — digests, earnings alerts, and onboarding.
          </p>
          <Toggle
            checked={prefs.email_enabled}
            onChange={(v) => set("email_enabled", v)}
            label="Email enabled"
            description="When off, no emails are sent regardless of other settings."
          />
        </Section>

        {/* Digest schedule */}
        <Section label="Weekly digest" disabled={!prefs.email_enabled}>
          <p className="font-sans text-xs text-muted-foreground mb-5 leading-relaxed">
            Your portfolio summary sent on a schedule. Weekly works best for thesis review.
          </p>
          <div className="space-y-4">
            <div className="space-y-2">
              <p className="font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground/70">Frequency</p>
              <Select
                value={prefs.digest_frequency}
                onValueChange={(v) => v && set("digest_frequency", v)}
              >
                <SelectTrigger className="w-52">
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
                  <p className="font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground/70">Day</p>
                  <Select
                    value={prefs.digest_day}
                    onValueChange={(v) => v && set("digest_day", v)}
                  >
                    <SelectTrigger>
                      <SelectValue>
                        {prefs.digest_day.charAt(0).toUpperCase() + prefs.digest_day.slice(1)}
                      </SelectValue>
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
                  <p className="font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground/70">Time</p>
                  <input
                    type="time"
                    value={prefs.digest_time}
                    onChange={(e) => set("digest_time", e.target.value)}
                    className="flex h-10 w-full border border-input bg-background px-3 py-2 text-sm text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  />
                </div>
              </div>
            )}
          </div>
        </Section>

        {/* Alert toggles */}
        <Section label="Alerts" disabled={!prefs.email_enabled}>
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
        </Section>

        {/* Monitoring sensitivity */}
        <Section label="Monitoring sensitivity">
          <p className="font-sans text-xs text-muted-foreground mb-4 leading-relaxed">
            Controls which monitoring events appear in your event timeline.
          </p>
          <div className="space-y-2">
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
            <p className="font-sans text-xs text-muted-foreground leading-relaxed">
              Use &ldquo;Thesis-breaking only&rdquo; if you only want the sharpest signal.
            </p>
          </div>
        </Section>

        {/* Save */}
        <div className="flex justify-end pt-2">
          <button
            onClick={handleSave}
            disabled={saving}
            className={`font-mono text-[11px] uppercase tracking-[0.2em] px-6 py-2.5 transition-colors border ${
              saved
                ? "border-emerald-500/40 text-emerald-700"
                : saving
                  ? "border-border text-muted-foreground cursor-not-allowed"
                  : "border-primary/40 text-primary hover:border-primary hover:bg-primary/8"
            }`}
          >
            {saving ? "Saving…" : saved ? "Saved" : "Save preferences"}
          </button>
        </div>
      </div>
    </AppShell>
  );
}
