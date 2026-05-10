"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";
import { ThesisCard } from "@/components/thesis/thesis-card";
import { ThesisEditor } from "@/components/thesis/thesis-editor";
import { EventTimeline } from "@/components/monitoring/event-timeline";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import type { Holding, Thesis, MonitoringEvent } from "@/types";

export default function PositionDetailPage() {
  const { ticker } = useParams<{ ticker: string }>();
  const [holdings, setHoldings] = useState<Holding[]>([]);
  const [theses, setTheses] = useState<Thesis[]>([]);
  const [events, setEvents] = useState<MonitoringEvent[]>([]);
  const [editing, setEditing] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [invalidateOpen, setInvalidateOpen] = useState(false);
  const [invalidateReason, setInvalidateReason] = useState("");
  const [loading, setLoading] = useState(true);

  const holding = holdings.find((h) => h.ticker === ticker);
  const activeThesis = theses.find((t) => t.status === "active" || t.status === "draft" || t.status === "needs_review");

  useEffect(() => {
    async function load() {
      try {
        const h = await api.get<Holding[]>("/api/portfolio/holdings");
        setHoldings(h);
        const match = h.find((x) => x.ticker === ticker);
        if (match) {
          const [t, e] = await Promise.all([
            api.get<Thesis[]>(`/api/theses/holding/${match.id}`),
            api.get<MonitoringEvent[]>(`/api/monitoring/holdings/${match.id}/events`),
          ]);
          setTheses(t);
          setEvents(e);
        }
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [ticker]);

  const handleGenerate = async () => {
    if (!holding) return;
    setGenerating(true);
    try {
      const thesis = await api.post<Thesis>("/api/theses/generate", { holding_id: holding.id });
      setTheses([thesis, ...theses]);
    } catch (err) {
      console.error(err);
    } finally {
      setGenerating(false);
    }
  };

  const handleSave = async (data: any) => {
    if (!activeThesis) return;
    try {
      const updated = await api.put<Thesis>(`/api/theses/${activeThesis.id}`, data);
      setTheses(theses.map((t) => (t.id === updated.id ? updated : t)));
      setEditing(false);
    } catch (err) {
      console.error(err);
    }
  };

  const handleInvalidate = async () => {
    if (!activeThesis) return;
    try {
      const updated = await api.post<Thesis>(`/api/theses/${activeThesis.id}/invalidate`, { reason: invalidateReason });
      setTheses(theses.map((t) => (t.id === updated.id ? updated : t)));
      setInvalidateOpen(false);
      setInvalidateReason("");
    } catch (err) {
      console.error(err);
    }
  };

  if (loading) return <p>Loading...</p>;
  if (!holding) return <p>Holding not found for ticker {ticker}</p>;

  const cost = holding.quantity * holding.average_cost_basis;
  const value = holding.current_value || 0;
  const pnl = value - cost;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">{holding.ticker}</h1>
        <p className="text-muted-foreground">{holding.name}</p>
      </div>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm text-muted-foreground">Quantity</CardTitle></CardHeader>
          <CardContent><p className="text-xl font-bold">{holding.quantity}</p></CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm text-muted-foreground">Avg Cost</CardTitle></CardHeader>
          <CardContent><p className="text-xl font-bold">{formatCurrency(holding.average_cost_basis, holding.currency)}</p></CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm text-muted-foreground">Current Value</CardTitle></CardHeader>
          <CardContent><p className="text-xl font-bold">{formatCurrency(value, holding.currency)}</p></CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm text-muted-foreground">P&L</CardTitle></CardHeader>
          <CardContent><p className={`text-xl font-bold ${pnl >= 0 ? "text-green-600" : "text-red-600"}`}>{formatCurrency(pnl, holding.currency)}</p></CardContent>
        </Card>
      </div>

      {activeThesis && !editing && (
        <ThesisCard thesis={activeThesis} onEdit={() => setEditing(true)} onInvalidate={() => setInvalidateOpen(true)} />
      )}

      {activeThesis && editing && (
        <ThesisEditor thesis={activeThesis} onSave={handleSave} onCancel={() => setEditing(false)} />
      )}

      {!activeThesis && (
        <Card>
          <CardContent className="flex flex-col items-center gap-4 py-8">
            <p className="text-muted-foreground">No active thesis for this position.</p>
            <Button onClick={handleGenerate} disabled={generating}>
              {generating ? "Generating..." : "Generate Thesis with AI"}
            </Button>
          </CardContent>
        </Card>
      )}

      <EventTimeline events={events} />

      {theses.filter((t) => t.status === "invalidated").length > 0 && (
        <Card>
          <CardHeader><CardTitle className="text-base">Thesis History</CardTitle></CardHeader>
          <CardContent className="space-y-2">
            {theses.filter((t) => t.status === "invalidated").map((t) => (
              <div key={t.id} className="border-l-2 border-muted pl-4 py-2">
                <p className="text-sm">{t.bull_case}</p>
                <p className="text-xs text-muted-foreground">Invalidated: {t.invalidation_reason}</p>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      <Dialog open={invalidateOpen} onOpenChange={setInvalidateOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>Invalidate Thesis</DialogTitle></DialogHeader>
          <Textarea placeholder="Why is this thesis no longer valid?" value={invalidateReason} onChange={(e) => setInvalidateReason(e.target.value)} />
          <DialogFooter>
            <Button variant="outline" onClick={() => setInvalidateOpen(false)}>Cancel</Button>
            <Button variant="destructive" onClick={handleInvalidate}>Invalidate</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
