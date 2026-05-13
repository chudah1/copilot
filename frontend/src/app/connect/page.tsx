"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { AuthGuard } from "@/components/layout/auth-guard";
import { Navbar } from "@/components/layout/navbar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { getErrorMessage } from "@/lib/errors";
import type { BrokerConnection, Holding } from "@/types";

export default function ConnectPage() {
  const router = useRouter();

  const [apiKey, setApiKey] = useState("");
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
        api_key: apiKey,
      });
      await api.post(`/api/portfolio/sync/${conn.id}`);
      router.push("/dashboard");
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
      router.push("/dashboard");
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
      const token = localStorage.getItem("access_token");
      const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${API_URL}/api/portfolio/upload-csv`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: formData,
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `Upload failed: ${res.status}`);
      }
      const holdings: Holding[] = await res.json();
      setCsvResult(`Imported ${holdings.length} holding${holdings.length !== 1 ? "s" : ""} successfully.`);
      setTimeout(() => router.push("/dashboard"), 1500);
    } catch (error: unknown) {
      setCsvError(getErrorMessage(error, "CSV upload failed"));
    } finally {
      setCsvLoading(false);
    }
  };

  return (
    <AuthGuard>
      <Navbar />
      <main className="mx-auto max-w-2xl px-4 py-10">
        <Card className="mb-6 border-0 bg-[linear-gradient(135deg,rgba(18,26,36,0.98),rgba(23,58,52,0.94)_52%,rgba(225,232,215,0.96))] text-white ring-0">
          <CardHeader className="gap-3">
            <CardTitle className="text-3xl font-semibold tracking-tight text-white">Connect your portfolio</CardTitle>
            <CardDescription className="max-w-2xl text-white/80">
              Start by importing what you actually own. Then we help you capture why each important position exists, what must remain true, and what should trigger a review.
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4 md:grid-cols-3">
            <div className="rounded-2xl border border-white/12 bg-white/8 p-4 backdrop-blur">
              <p className="text-sm text-white/70">Step 1</p>
              <p className="mt-2 font-medium">Import holdings</p>
              <p className="mt-1 text-sm text-white/75">Use CSV, manual entry, or Trading 212.</p>
            </div>
            <div className="rounded-2xl border border-white/12 bg-white/8 p-4 backdrop-blur">
              <p className="text-sm text-white/70">Step 2</p>
              <p className="mt-2 font-medium">Write top theses</p>
              <p className="mt-1 text-sm text-white/75">Start with your biggest or least-clear positions.</p>
            </div>
            <div className="rounded-2xl border border-white/12 bg-white/8 p-4 backdrop-blur">
              <p className="text-sm text-white/70">Step 3</p>
              <p className="mt-2 font-medium">Get monitored</p>
              <p className="mt-1 text-sm text-white/75">We watch for changes that matter to your own reasoning.</p>
            </div>
          </CardContent>
        </Card>

        <Card className="mb-6">
          <CardHeader>
            <CardTitle>Choose the fastest path</CardTitle>
            <CardDescription>Pick the import method that gets you to thesis setup with the least friction.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4 md:grid-cols-3">
            <div className="rounded-xl border p-4">
              <p className="font-medium">CSV Upload</p>
              <p className="mt-1 text-sm text-muted-foreground">Best if you already have an export and want the quickest start.</p>
            </div>
            <div className="rounded-xl border p-4">
              <p className="font-medium">Manual Entry</p>
              <p className="mt-1 text-sm text-muted-foreground">Best for testing the product with a few positions first.</p>
            </div>
            <div className="rounded-xl border p-4">
              <p className="font-medium">Trading 212 API</p>
              <p className="mt-1 text-sm text-muted-foreground">Best if you want your holdings to stay synced automatically.</p>
            </div>
          </CardContent>
        </Card>

        <Tabs defaultValue="csv">
          <TabsList className="mb-4">
            <TabsTrigger value="csv">CSV Upload</TabsTrigger>
            <TabsTrigger value="manual">Manual Entry</TabsTrigger>
            <TabsTrigger value="broker">Trading 212 API</TabsTrigger>
          </TabsList>

          <TabsContent value="broker">
            <Card>
              <CardHeader>
                <CardTitle>Connect Trading 212</CardTitle>
                <CardDescription>
                  Paste your API key from Trading 212 Settings &gt; API.
                  We encrypt it and never share it.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <form onSubmit={handleConnect} className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="apiKey">API Key</Label>
                    <Input id="apiKey" type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)} required />
                  </div>
                  <div className="rounded-lg bg-muted/30 p-3 text-sm text-muted-foreground">
                    Best for ongoing sync. After import, the app will surface your biggest positions first so you can set up the most important theses immediately.
                  </div>
                  {brokerError && <p className="text-sm text-red-500">{brokerError}</p>}
                  <Button type="submit" disabled={brokerLoading}>
                    {brokerLoading ? "Connecting..." : "Connect & Sync"}
                  </Button>
                </form>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="csv">
            <Card>
              <CardHeader>
                <CardTitle>Upload CSV</CardTitle>
                <CardDescription>
                  Upload a Trading 212 transaction export or a generic CSV with columns:
                  ticker, name, quantity, average_cost_basis.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <form onSubmit={handleCsvUpload} className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="csvFile">CSV File</Label>
                    <Input
                      id="csvFile"
                      type="file"
                      accept=".csv"
                      onChange={(e) => setCsvFile(e.target.files?.[0] || null)}
                      required
                    />
                  </div>
                  <div className="rounded-lg bg-muted/30 p-3 text-sm text-muted-foreground">
                    Fastest path for most people. Once imported, head straight to your top 3 positions and capture why they exist.
                  </div>
                  {csvError && <p className="text-sm text-red-500">{csvError}</p>}
                  {csvResult && <p className="text-sm text-green-600">{csvResult}</p>}
                  <Button type="submit" disabled={csvLoading || !csvFile}>
                    {csvLoading ? "Uploading..." : "Upload & Import"}
                  </Button>
                </form>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="manual">
            <Card>
              <CardHeader>
                <CardTitle>Add Position Manually</CardTitle>
                <CardDescription>Enter your holdings one at a time.</CardDescription>
              </CardHeader>
              <CardContent>
                <form onSubmit={handleManual} className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="ticker">Ticker</Label>
                      <Input id="ticker" value={ticker} onChange={(e) => setTicker(e.target.value)} placeholder="AAPL" required />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="name">Company Name</Label>
                      <Input id="name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Apple Inc" required />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="quantity">Quantity</Label>
                      <Input id="quantity" type="number" step="any" value={quantity} onChange={(e) => setQuantity(e.target.value)} required />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="avgCost">Average Cost</Label>
                      <Input id="avgCost" type="number" step="any" value={avgCost} onChange={(e) => setAvgCost(e.target.value)} required />
                    </div>
                  </div>
                  <div className="rounded-lg bg-muted/30 p-3 text-sm text-muted-foreground">
                    Good for a lightweight trial. Add 1-3 positions first, then create a thesis for each and see how the product feels before importing everything else.
                  </div>
                  {manualError && <p className="text-sm text-red-500">{manualError}</p>}
                  <Button type="submit" disabled={manualLoading}>
                    {manualLoading ? "Adding..." : "Add Holding"}
                  </Button>
                </form>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </main>
    </AuthGuard>
  );
}
