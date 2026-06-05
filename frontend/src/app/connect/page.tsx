"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { getApiBaseUrl } from "@/lib/api-base";
import { AuthGuard } from "@/components/layout/auth-guard";
import { Navbar } from "@/components/layout/navbar";
import { Button } from "@/components/ui/button";
import { getErrorMessage } from "@/lib/errors";
import { TickerSearch } from "@/components/portfolio/ticker-search";
import type { BrokerConnection, Holding } from "@/types";

type TabId = "csv" | "manual" | "broker";

const TABS: { id: TabId; label: string }[] = [
  { id: "manual", label: "Manual Entry" },
  { id: "csv", label: "CSV Upload" },
  { id: "broker", label: "Trading 212" },
];

const TAB_DETAILS: Record<
  TabId,
  {
    eyebrow: string;
    title: string;
    body: string;
    note: string;
    formTitle: string;
    formBody: string;
    after: string;
  }
> = {
  csv: {
    eyebrow: "Fastest path",
    title: "Import the full ledger in one move.",
    body: "Best when the export is already in hand.",
    note: "Accepted shape: Trading 212 export or columns for ticker, name, quantity, and average cost basis.",
    formTitle: "Upload a broker file",
    formBody: "Import first. Write the first thesis on the holding that matters most.",
    after: "Next: open the largest position and write the first thesis.",
  },
  manual: {
    eyebrow: "Best for first use",
    title: "Start with just a few names.",
    body: "Add one to three positions before a larger import.",
    note: "This is the easiest path if you want to feel the product before committing to a full setup.",
    formTitle: "Add the first position",
    formBody: "Use one real holding to feel the workflow first.",
    after: "Next: write why you own it while the case is still fresh.",
  },
  broker: {
    eyebrow: "Connected source",
    title: "Sync holdings straight from Trading 212.",
    body: "Best when you want holdings to come in directly.",
    note: "New holdings are added to what is already here. Existing positions are not overwritten.",
    formTitle: "Connect the live source",
    formBody: "Connect once, then sync the holdings in.",
    after: "Next: write the thesis on the position that matters most.",
  },
};

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
  const [tab, setTab] = useState<TabId>("manual");

  // When reached from the dashboard/settings ("add another source") rather than
  // first-run onboarding, return the user where they came from instead of
  // dropping them back into the onboarding flow.
  const [returnTo, setReturnTo] = useState<string | null>(null);
  useEffect(() => {
    // Read once after mount (render null first) to avoid a hydration mismatch
    // on the URL param.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setReturnTo(new URLSearchParams(window.location.search).get("return"));
  }, []);
  const addingMore = returnTo === "dashboard" || returnTo === "settings";
  const afterImport = () =>
    returnTo === "dashboard" ? "/dashboard"
      : returnTo === "settings" ? "/settings"
        : "/onboarding?source=import";

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
  const activeTab = TAB_DETAILS[tab];

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
      router.push(afterImport());
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
      router.push(afterImport());
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
      const res = await fetch(`${getApiBaseUrl()}/api/portfolio/upload-csv`, {
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
      setTimeout(() => router.push(afterImport()), 1500);
    } catch (error: unknown) {
      setCsvError(getErrorMessage(error, "CSV upload failed"));
    } finally {
      setCsvLoading(false);
    }
  };

  return (
    <AuthGuard>
      <Navbar />
      <main className="mx-auto max-w-5xl px-4 py-10 sm:px-8">
        <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_20rem]">
          <section className="space-y-5">
            <div className="product-panel product-panel-muted overflow-hidden p-6 sm:p-7">
              <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(18rem,20rem)]">
                <div className="space-y-3">
                  <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-muted-foreground">
                    {addingMore ? "Add a source" : "Getting started"}
                  </p>
                  <h1 className="font-display italic text-[2.4rem] leading-tight text-foreground">
                    {addingMore ? "Add more holdings." : "Connect your portfolio."}
                  </h1>
                  <p className="max-w-xl font-sans text-sm leading-relaxed text-muted-foreground">
                    {addingMore
                      ? "Connect another broker, upload a CSV, or add a position by hand. New holdings are added to what you already have."
                      : "Import what you own, then write the thesis on the position that matters most."}
                  </p>
                </div>

                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1">
                  <div className="border border-border/60 bg-background/70 p-4">
                    <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                      Outcome
                    </p>
                    <p className="mt-2 font-sans text-sm leading-relaxed text-foreground/80">
                      Holdings in first. Thesis work next.
                    </p>
                  </div>
                  <div className="border border-border/60 bg-background/70 p-4">
                    <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                      Fastest route
                    </p>
                    <p className="mt-2 font-sans text-sm leading-relaxed text-foreground/80">
                      Pick the path that gets you to one written position fastest.
                    </p>
                  </div>
                </div>
              </div>
            </div>

            <div className="product-panel p-2">
              <div className="grid gap-2 md:grid-cols-3">
                {TABS.map((t) => (
                  <button
                    key={t.id}
                    onClick={() => setTab(t.id)}
                    className={`px-4 py-3 text-left transition-colors ${
                      tab === t.id
                        ? "bg-muted text-foreground"
                        : "text-muted-foreground hover:bg-muted/50 hover:text-foreground"
                    }`}
                  >
                    <p className="font-mono text-[10px] uppercase tracking-[0.16em]">{t.label}</p>
                  </button>
                ))}
              </div>
            </div>

            <div className="product-panel p-5 sm:p-6">
              {tab === "csv" && (
                <form onSubmit={handleCsvUpload} className="space-y-4">
                  <div className="space-y-2">
                    <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                      {activeTab.formTitle}
                    </p>
                    <p className="font-sans text-sm leading-relaxed text-muted-foreground">
                      {activeTab.formBody}
                    </p>
                  </div>
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
                  <Note>Use this when the file is already ready.</Note>
                  {csvError && <p className="font-sans text-sm text-destructive" role="alert">{csvError}</p>}
                  {csvResult && <p className="font-sans text-sm text-emerald-600">{csvResult}</p>}
                  <Button type="submit" loading={csvLoading} disabled={!csvFile}>
                    <span className="font-mono text-[11px] uppercase tracking-[0.15em]">Upload & Import</span>
                  </Button>
                </form>
              )}

              {tab === "manual" && (
                <form onSubmit={handleManual} className="space-y-4">
                  <div className="space-y-2">
                    <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                      {activeTab.formTitle}
                    </p>
                    <p className="font-sans text-sm leading-relaxed text-muted-foreground">
                      {activeTab.formBody}
                    </p>
                  </div>
                  <Field label="Stock" note="Search the listed company name or ticker, then pick the common-stock match.">
                    <TickerSearch
                      value={ticker}
                      onChange={(nextTicker) => {
                        setTicker(nextTicker);
                        setName("");
                      }}
                      onSelect={(t, n) => { setTicker(t); setName(n); }}
                    />
                    {name && <p className="font-sans text-xs text-muted-foreground mt-1">{name}</p>}
                  </Field>
                  <div className="grid grid-cols-2 gap-4">
                    <Field id="quantity" label="Quantity" note="Use the real share count you hold today.">
                      <input
                        id="quantity"
                        type="number"
                        step="any"
                        min="0.000001"
                        value={quantity}
                        onChange={(e) => setQuantity(e.target.value)}
                        required
                        placeholder="12"
                        className={inputCls}
                      />
                    </Field>
                    <Field id="avgCost" label="Average cost" note="Per-share average cost basis for the holding.">
                      <input
                        id="avgCost"
                        type="number"
                        step="any"
                        min="0.000001"
                        value={avgCost}
                        onChange={(e) => setAvgCost(e.target.value)}
                        required
                        placeholder="187.40"
                        className={inputCls}
                      />
                    </Field>
                  </div>
                  <Note>One to three positions is enough to start.</Note>
                  {manualError && <p className="font-sans text-sm text-destructive" role="alert">{manualError}</p>}
                  <Button type="submit" loading={manualLoading} disabled={!ticker || !quantity || !avgCost}>
                    <span className="font-mono text-[11px] uppercase tracking-[0.15em]">Add Holding</span>
                  </Button>
                </form>
              )}

              {tab === "broker" && (
                <form onSubmit={handleConnect} className="space-y-4">
                  <div className="space-y-2">
                    <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                      {activeTab.formTitle}
                    </p>
                    <p className="font-sans text-sm leading-relaxed text-muted-foreground">
                      {activeTab.formBody}
                    </p>
                  </div>
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
                    Generate credentials in Trading 212 Settings → API. When generating, leave the IP restriction off.
                  </Note>
                  {brokerError && <p className="font-sans text-sm text-destructive" role="alert">{brokerError}</p>}
                  <Button type="submit" loading={brokerLoading}>
                    <span className="font-mono text-[11px] uppercase tracking-[0.15em]">Connect & Sync</span>
                  </Button>
                </form>
              )}
            </div>
          </section>

          <aside className="space-y-4">
            <div className="product-panel p-5">
              <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                {activeTab.eyebrow}
              </p>
              <p className="mt-2 font-display text-[1.35rem] italic leading-tight text-foreground">
                {activeTab.title}
              </p>
              <p className="mt-2 font-sans text-sm leading-relaxed text-muted-foreground">
                {activeTab.body}
              </p>
            </div>
            <div className="product-panel p-5">
              <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                Note
              </p>
              <p className="mt-2 font-sans text-sm leading-relaxed text-foreground/80">
                {activeTab.note}
              </p>
            </div>
            <div className="product-panel p-5">
              <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                Next
              </p>
              <p className="mt-2 font-sans text-sm leading-relaxed text-foreground/80">
                {activeTab.after}
              </p>
            </div>
          </aside>
        </div>
      </main>
    </AuthGuard>
  );
}
