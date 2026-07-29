"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { AppShell } from "@/components/layout/app-shell";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import type { PortfolioSummary, UserPreferences } from "@/types";

const DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"];
const PORTFOLIO_CURRENCIES = [
  ["GBP", "British pound"],
  ["USD", "US dollar"],
  ["EUR", "Euro"],
  ["CAD", "Canadian dollar"],
  ["AUD", "Australian dollar"],
  ["NZD", "New Zealand dollar"],
  ["CHF", "Swiss franc"],
  ["JPY", "Japanese yen"],
  ["SGD", "Singapore dollar"],
  ["HKD", "Hong Kong dollar"],
  ["INR", "Indian rupee"],
  ["NGN", "Nigerian naira"],
  ["GHS", "Ghanaian cedi"],
  ["ZAR", "South African rand"],
  ["AED", "UAE dirham"],
  ["SAR", "Saudi riyal"],
  ["KES", "Kenyan shilling"],
  ["CNY", "Chinese yuan"],
  ["KRW", "South Korean won"],
  ["IDR", "Indonesian rupiah"],
  ["MYR", "Malaysian ringgit"],
  ["PHP", "Philippine peso"],
  ["THB", "Thai baht"],
  ["SEK", "Swedish krona"],
  ["NOK", "Norwegian krone"],
  ["DKK", "Danish krone"],
  ["PLN", "Polish złoty"],
  ["CZK", "Czech koruna"],
  ["HUF", "Hungarian forint"],
  ["RON", "Romanian leu"],
  ["ISK", "Icelandic króna"],
  ["TRY", "Turkish lira"],
  ["ILS", "Israeli new shekel"],
  ["BRL", "Brazilian real"],
  ["MXN", "Mexican peso"],
] as const;

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
        className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer border transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background ${
          checked ? "bg-primary border-primary" : "bg-transparent border-border"
        }`}
      >
        <span
          className={`pointer-events-none inline-block h-3 w-3 m-0.5 transition-transform ${
            checked ? "translate-x-4 bg-primary-foreground" : "translate-x-0 bg-muted-foreground/50"
          }`}
        />
      </button>
    </div>
  );
}

function Section({ label, children, disabled }: { label: string; children: React.ReactNode; disabled?: boolean }) {
  return (
    <section className={`product-panel p-5 sm:p-6 ${disabled ? "opacity-50 pointer-events-none" : ""}`}>
      <p className="font-mono text-[10px] uppercase tracking-[0.3em] text-muted-foreground mb-5">{label}</p>
      {children}
    </section>
  );
}

export default function SettingsPage() {
  const [prefs, setPrefs] = useState<UserPreferences>({
    display_name: "",
    digest_frequency: "weekly",
    digest_day: "sunday",
    digest_time: "17:00",
    earnings_alerts: true,
    quarterly_review_reminders: true,
    email_enabled: true,
    notification_sensitivity: "all",
    portfolio_currency: "GBP",
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
      <div className="max-w-4xl mx-auto px-4 sm:px-8 py-10 space-y-6">

        <div className="product-panel product-panel-muted overflow-hidden p-5 sm:p-6">
          <p className="font-mono text-[10px] uppercase tracking-[0.3em] text-muted-foreground mb-2">
            Account
          </p>
          <h1 className="font-display italic text-4xl text-foreground leading-tight">
            Settings
          </h1>
          <p className="font-sans text-sm text-muted-foreground mt-2">
            Email, alerts, and feed sensitivity.
          </p>
          {summary && (
            <div className="mt-6 grid gap-3 sm:grid-cols-3">
              <div className="border border-border/60 bg-background/70 p-4">
                <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                  Positions
                </p>
                <p className="mt-2 font-display text-[1.5rem] italic leading-none text-foreground">
                  {summary.holdings_count}
                </p>
              </div>
              <div className="border border-border/60 bg-background/70 p-4">
                <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                  Written
                </p>
                <p className="mt-2 font-display text-[1.5rem] italic leading-none text-foreground">
                  {summary.theses_active}
                </p>
              </div>
              <div className={`border p-4 text-sm font-sans leading-relaxed ${
                summary.monitoring_ready
                  ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-700/90"
                  : "border-amber-500/20 bg-amber-500/10 text-amber-700/90"
              }`}>
                {summary.monitoring_message}
                {!summary.monitoring_ready && (
                  <Link href="/onboarding" className="mt-2 block font-mono text-[10px] uppercase tracking-[0.14em] underline underline-offset-4 opacity-80 hover:opacity-100">
                    Write your first thesis →
                  </Link>
                )}
              </div>
            </div>
          )}
        </div>

        <Section label="Name">
          <div className="space-y-3">
            <input
              type="text"
              value={prefs.display_name ?? ""}
              onChange={(e) => set("display_name", e.target.value)}
              placeholder="First name or nickname"
              maxLength={40}
              className="flex h-10 w-full sm:w-72 border border-input bg-background px-3 py-2 text-sm text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            />
            <p className="max-w-xl font-sans text-xs leading-relaxed text-muted-foreground">
              Used to greet you on the dashboard. Leave blank to keep things anonymous.
            </p>
          </div>
        </Section>

        {/* Portfolio sources */}
        <Section label="Portfolio">
          <div className="flex items-start justify-between gap-6">
            <div className="flex-1">
              <p className="font-sans text-sm text-foreground">
                {summary ? `${summary.holdings_count} position${summary.holdings_count === 1 ? "" : "s"} tracked` : "Your holdings"}
              </p>
              <p className="font-sans text-xs text-muted-foreground mt-1 leading-relaxed">
                Link another broker.
              </p>
            </div>
            <Link href="/connect?return=settings" className="shrink-0">
              <Button type="button" variant="outline" size="sm">
                Add holdings
              </Button>
            </Link>
          </div>
        </Section>

        <Section label="Display currency">
          <div className="space-y-3">
            <Select
              value={prefs.portfolio_currency}
              onValueChange={(v) => v && set("portfolio_currency", v)}
            >
              <SelectTrigger className="w-full sm:w-72">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {PORTFOLIO_CURRENCIES.map(([code, name]) => (
                  <SelectItem key={code} value={code}>
                    {code} · {name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="max-w-xl font-sans text-xs leading-relaxed text-muted-foreground">
              Portfolio totals, position values, and gains will use this currency. Share prices stay in each holding&apos;s trading currency.
            </p>
          </div>
        </Section>

        {/* Email master switch */}
        <Section label="Email">
          <Toggle
            checked={prefs.email_enabled}
            onChange={(v) => set("email_enabled", v)}
            label="Email updates"
            description="Digests, alerts, and onboarding mail."
          />
        </Section>

        {/* Digest schedule */}
        <Section label="Weekly digest" disabled={!prefs.email_enabled}>
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
            description="Before results, plus a next-morning thesis check."
          />
          <Toggle
            checked={prefs.quarterly_review_reminders}
            onChange={(v) => set("quarterly_review_reminders", v)}
            label="Quarterly review reminders"
            description="Reminder to revisit each position each quarter."
          />
        </Section>

        {/* Monitoring sensitivity */}
        <Section label="Monitoring sensitivity">
          <div className="space-y-2">
            <Select
              value={prefs.notification_sensitivity}
              onValueChange={(v) => v && set("notification_sensitivity", v)}
            >
              <SelectTrigger className="w-56">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Warnings and thesis breaks</SelectItem>
                <SelectItem value="thesis_breaking_only">Thesis-breaking only</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </Section>

        {/* Save */}
        <div className="product-panel p-4 sm:p-5 flex justify-end">
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
            {saving ? "Saving…" : saved ? "Saved" : "Save"}
          </button>
        </div>
      </div>
    </AppShell>
  );
}
