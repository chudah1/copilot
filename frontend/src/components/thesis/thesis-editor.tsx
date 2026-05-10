"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { Thesis, KeyMetric } from "@/types";

interface Props {
  thesis: Thesis;
  onSave: (data: { bull_case: string; key_metrics: KeyMetric[]; risk_factors: string; conviction: string; status: string }) => void;
  onCancel: () => void;
}

export function ThesisEditor({ thesis, onSave, onCancel }: Props) {
  const [bullCase, setBullCase] = useState(thesis.bull_case);
  const [riskFactors, setRiskFactors] = useState(thesis.risk_factors);
  const [conviction, setConviction] = useState(thesis.conviction);
  const [metrics, setMetrics] = useState<KeyMetric[]>(thesis.key_metrics);

  const updateMetric = (index: number, field: keyof KeyMetric, value: string | number) => {
    const updated = [...metrics];
    updated[index] = { ...updated[index], [field]: value };
    setMetrics(updated);
  };

  const addMetric = () => {
    setMetrics([...metrics, { metric: "", operator: ">=", threshold: 0, rationale: "" }]);
  };

  const removeMetric = (index: number) => {
    setMetrics(metrics.filter((_, i) => i !== index));
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Edit Thesis</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label>Bull Case</Label>
          <Textarea value={bullCase} onChange={(e) => setBullCase(e.target.value)} rows={3} />
        </div>

        <div className="space-y-2">
          <Label>Key Metrics</Label>
          {metrics.map((m, i) => (
            <div key={i} className="grid grid-cols-5 gap-2 items-end">
              <Input placeholder="metric_name" value={m.metric} onChange={(e) => updateMetric(i, "metric", e.target.value)} />
              <Select value={m.operator} onValueChange={(v) => v && updateMetric(i, "operator", v)}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value=">=">{"≥"}</SelectItem>
                  <SelectItem value="<=">{"≤"}</SelectItem>
                  <SelectItem value=">">{">"}</SelectItem>
                  <SelectItem value="<">{"<"}</SelectItem>
                </SelectContent>
              </Select>
              <Input type="number" value={m.threshold} onChange={(e) => updateMetric(i, "threshold", parseFloat(e.target.value))} />
              <Input placeholder="rationale" value={m.rationale} onChange={(e) => updateMetric(i, "rationale", e.target.value)} />
              <Button variant="ghost" size="sm" onClick={() => removeMetric(i)}>Remove</Button>
            </div>
          ))}
          <Button variant="outline" size="sm" onClick={addMetric}>Add Metric</Button>
        </div>

        <div className="space-y-2">
          <Label>Risk Factors</Label>
          <Textarea value={riskFactors} onChange={(e) => setRiskFactors(e.target.value)} rows={2} />
        </div>

        <div className="space-y-2">
          <Label>Conviction</Label>
          <Select value={conviction} onValueChange={(v) => v && setConviction(v)}>
            <SelectTrigger className="w-40"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="high">High</SelectItem>
              <SelectItem value="medium">Medium</SelectItem>
              <SelectItem value="low">Low</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="flex gap-2">
          <Button onClick={() => onSave({ bull_case: bullCase, key_metrics: metrics, risk_factors: riskFactors, conviction, status: "active" })}>
            Save & Activate
          </Button>
          <Button variant="outline" onClick={onCancel}>Cancel</Button>
        </div>
      </CardContent>
    </Card>
  );
}
