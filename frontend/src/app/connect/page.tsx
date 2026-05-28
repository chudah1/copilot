"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { AuthGuard } from "@/components/layout/auth-guard";
import { Navbar } from "@/components/layout/navbar";
import { Button } from "@/components/ui/button";
import { getErrorMessage } from "@/lib/errors";
import { TickerSearch } from "@/components/portfolio/ticker-search";
import type { BrokerConnection, Holding } from "@/types";

type TabId = "csv" | "manual" | "broker";

const TABS: { id: TabId; label: string }[] = [
  { id: "csv", label: "CSV Upload" },
  { id: "manual", label: "Manual Entry" },
  { id: "broker", label: "Trading 212 API" },
];

function Field({
  id,
  label,
  note,
  children,
}: {
  id?: string;
  label: string;
  note?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground block">
        {label}
      </label>
      {children}
      {note && <p className="font-sans text-xs text-muted-foreground/70 leading-relaxed">{note}</p>}
    </div>
  );
}

function Note({ children }: { children: React.ReactNode }) {
  return (
    <div className="border border-border/40 bg-muted/30 px-3 py-2.5">
      <p className="font-sans text-xs text-muted-foreground leading-relaxed">{children}</p>
    </div>
  );
}

const inputCls = "w-full border border-border bg-background px-3 py-2 font-sans text-sm text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:border-foreground/30";

export default function ConnectPage() {
  const router = useRouter();
  const [tab, setTab] = useState<TabId>("csv");

  const [apiKey, setApiKey] = useState("");
  const [apiSecret, setApiSecret] = useState("");
  const [brokerError, setBrokerError] = useState("");
  const [brokerLoading, setBrokerLoading] = useState(false);

  const [ticker, setTicker] = useState("");
  const [name, setName] = useState("");
  const [quantity, setQuantity] = useState("");
  const [avgCost, setAvgCost] = useState("");
  const [manualError, setManualError] = useState("");
  const [manualLoading, setManualLoading] = useState(false);

  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [csvError, setCsvError] = useState("");
  const [csvLoading, setCsvLoading] = useState(false);
  const [csvResult, setCsvResult] = useState("");

  const handleConnect = async (e: React.FormEvent) => {
    e.preventDefault();
    setBrokerError("");
    setBrokerLoading(true);
    try {
      const conn = await api.post<BrokerConnection>("/api/portfolio/connect", {
        broker_type: "trading212",
        api_key: apiKey.trim(),
        api_secret: apiSecret.trim() || undefined,
      });
      await api.post(`/api/portfolio/sync/${conn.id}`);
      router.push("/onboarding?source=import");
    } catch (error: unknown) {
      setBrokerError(getErrorMessage(error, "Failed to connect"));
    } finally {
      setBrokerLoading(false);
    }
  };

  const handleManual = async (e: React.FormEvent) => {
    e.preventDefault();
    setManualError("");
    setManualLoading(true);
    try {
      await api.post<Holding>("/api/portfolio/holdings", {
        ticker: ticker.toUpperCase(),
        name,
        quantity: parseFloat(quantity),
        average_cost_basis: parseFloat(avgCost),
      });
      setTicker("");
      setName("");
      setQuantity("");
      setAvgCost("");
      router.push("/onboarding?source=import");
    } catch (error: unknown) {
      setManualError(getErrorMessage(error, "Failed to add holding"));
    } finally {
      setManualLoading(false);
    }
  };

  const handleCsvUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!csvFile) return;
    setCsvError("");
    setCsvResult("");
    setCsvLoading(true);
    try {
      const formData = new FormData();
      formData.append("file", csvFile);
      const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${API_URL}/api/portfolio/upload-csv`, {
        method: "POST",
        credentials: "include",
        body: formData,
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `Upload failed: ${res.status}`);
      }
      const holdings: Holding[] = await res.json();
      setCsvResult(`Imported ${holdings.length} holding${holdings.length !== 1 ? "s" : ""} successfully.`);
      setTimeout(() => router.push("/onboarding?source=import"), 1500);
    } catch (error: unknown) {
      setCsvError(getErrorMessage(error, "CSV upload failed"));
    } finally {
      setCsvLoading(false);
    }
  };

  return (
    <AuthGuard>
      <Navbar />
      <main className="max-w-2xl mx-auto px-4 sm:px-8 py-10">

        {/* Header */}
        <div className="border-b border-border pb-7 mb-8">
          <p className="font-mono text-[10px] uppercase tracking-[0.3em] text-muted-foreground mb-2">
            Getting started
          </p>
          <h1 className="font-display italic text-[2.5rem] leading-tight text-foreground mb-3">
            Connect your portfolio.
          </h1>
          <p className="font-sans text-sm text-muted-foreground leading-relaxed max-w-lg">
            Import what you own. Then write why each position exists — what must stay true, and what would make you reconsider.
          </p>

          {/* Steps */}
          <div className="grid grid-cols-3 gap-px mt-6 border border-border">
            {[
              { n: "01", title: "Import holdings", body: "CSV, manual entry, or Trading 212." },
              { n: "02", title: "Write top theses", body: "Start with your biggest positions." },
              { n: "03", title: "Get monitored", body: "We watch for changes that matter to your reasoning." },
            ].map(({ n, title, body }) => (
              <div key={n} className="bg-muted/30 px-4 py-4">
                <p className="font-mono text-[10px] tracking-[0.2em] text-primary mb-1.5">{n}</p>
                <p className="font-sans text-sm font-medium text-foreground">{title}</p>
                <p className="font-sans text-xs text-muted-foreground mt-1 leading-relaxed">{body}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Tab strip */}
        <div className="flex gap-1 border-b border-border mb-6 -mx-1">
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`relative px-3 pb-3 pt-1 font-mono text-[10px] uppercase tracking-[0.18em] transition-colors ${
                tab === t.id ? "text-foreground" : "text-muted-foreground hover:text-foreground/70"
              }`}
            >
              {t.label}
              {tab === t.id && (
                <span className="absolute bottom-0 inset-x-3 h-px bg-primary" />
              )}
            </button>
          ))}
        </div>

        {/* CSV tab */}
        {tab === "csv" && (
          <form onSubmit={handleCsvUpload} className="space-y-4">
            <Field id="csvFile" label="CSV file" note="Trading 212 transaction export or a file with columns: ticker, name, quantity, average_cost_basis.">
              <input
                id="csvFile"
                type="file"
                accept=".csv"
                onChange={(e) => setCsvFile(e.target.files?.[0] || null)}
                required
                className={inputCls}
              />
            </Field>
            <Note>
              Fastest path for most people. Once imported, head to your top 3 positions and write why each one exists.
            </Note>
            {csvError && <p className="font-sans text-sm text-destructive" role="alert">{csvError}</p>}
            {csvResult && <p className="font-sans text-sm text-emerald-600">{csvResult}</p>}
            <Button type="submit" loading={csvLoading} disabled={!csvFile}>
              <span className="font-mono text-[11px] uppercase tracking-[0.15em]">Upload & Import</span>
            </Button>
          </form>
        )}

        {/* Manual tab */}
        {tab === "manual" && (
          <form onSubmit={handleManual} className="space-y-4">
            <Field label="Stock">
              <TickerSearch value={ticker} onSelect={(t, n) => { setTicker(t); setName(n); }} />
              {name && <p className="font-sans text-xs text-muted-foreground mt-1">{name}</p>}
            </Field>
            <div className="grid grid-cols-2 gap-4">
              <Field id="quantity" label="Quantity">
                <input
                  id="quantity"
                  type="number"
                  step="any"
                  min="0.000001"
                  value={quantity}
                  onChange={(e) => setQuantity(e.target.value)}
                  required
                  className={inputCls}
                />
              </Field>
              <Field id="avgCost" label="Average cost">
                <input
                  id="avgCost"
                  type="number"
                  step="any"
                  min="0.000001"
                  value={avgCost}
                  onChange={(e) => setAvgCost(e.target.value)}
                  required
                  className={inputCls}
                />
              </Field>
            </div>
            <Note>
              Add 1–3 positions first, write a thesis for each, and see how the product feels before importing everything else.
            </Note>
            {manualError && <p className="font-sans text-sm text-destructive" role="alert">{manualError}</p>}
            <Button type="submit" loading={manualLoading} disabled={!ticker || !quantity || !avgCost}>
              <span className="font-mono text-[11px] uppercase tracking-[0.15em]">Add Holding</span>
            </Button>
          </form>
        )}

        {/* Trading 212 tab */}
        {tab === "broker" && (
          <form onSubmit={handleConnect} className="space-y-4">
            <Field id="apiKey" label="API Key">
              <input
                id="apiKey"
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                required
                className={inputCls}
              />
            </Field>
            <Field id="apiSecret" label="Secret Key" note="Leave blank if Trading 212 only gave you one key.">
              <input
                id="apiSecret"
                type="password"
                value={apiSecret}
                onChange={(e) => setApiSecret(e.target.value)}
                className={inputCls}
              />
            </Field>
            <Note>
              Generate credentials in Trading 212 Settings → API. Don&rsquo;t set an IP restriction when generating — leave it unrestricted.
            </Note>
            {brokerError && <p className="font-sans text-sm text-destructive" role="alert">{brokerError}</p>}
            <Button type="submit" loading={brokerLoading}>
              <span className="font-mono text-[11px] uppercase tracking-[0.15em]">Connect & Sync</span>
            </Button>
          </form>
        )}
      </main>
    </AuthGuard>
  );
}
