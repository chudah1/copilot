"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { AuthGuard } from "@/components/layout/auth-guard";
import { Navbar } from "@/components/layout/navbar";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

export default function SettingsPage() {
  const [frequency, setFrequency] = useState("weekly");
  const [sensitivity, setSensitivity] = useState("all");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    api.get<{ digest_frequency: string; notification_sensitivity: string }>("/api/settings").then((s) => {
      setFrequency(s.digest_frequency);
      setSensitivity(s.notification_sensitivity);
    });
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
        <h1 className="mb-6 text-2xl font-bold">Settings</h1>
        <Card>
          <CardHeader><CardTitle>Digest Preferences</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label>Digest Frequency</Label>
              <Select value={frequency} onValueChange={(v) => v && setFrequency(v)}>
                <SelectTrigger className="w-60"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="weekly">Weekly (Sunday 6pm)</SelectItem>
                  <SelectItem value="daily">Daily</SelectItem>
                  <SelectItem value="none">Disabled</SelectItem>
                </SelectContent>
              </Select>
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
