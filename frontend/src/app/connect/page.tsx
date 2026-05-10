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

  const handleConnect = async (e: React.FormEvent) => {
    e.preventDefault();
    setBrokerError("");
    setBrokerLoading(true);
    try {
      const conn = await api.post<BrokerConnection>("/api/portfolio/connect", {
        broker_type: "trading_212",
        api_key: apiKey,
      });
      await api.post(`/api/portfolio/sync/${conn.id}`);
      router.push("/dashboard");
    } catch (err: any) {
      setBrokerError(err.message || "Failed to connect");
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
    } catch (err: any) {
      setManualError(err.message || "Failed to add holding");
    } finally {
      setManualLoading(false);
    }
  };

  return (
    <AuthGuard>
      <Navbar />
      <main className="mx-auto max-w-2xl px-4 py-10">
        <h1 className="mb-6 text-2xl font-bold">Connect Your Portfolio</h1>
        <Tabs defaultValue="broker">
          <TabsList className="mb-4">
            <TabsTrigger value="broker">Trading 212</TabsTrigger>
            <TabsTrigger value="manual">Manual Entry</TabsTrigger>
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
                  {brokerError && <p className="text-sm text-red-500">{brokerError}</p>}
                  <Button type="submit" disabled={brokerLoading}>
                    {brokerLoading ? "Connecting..." : "Connect & Sync"}
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
