"use client";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatDate } from "@/lib/utils";
import type { MonitoringEvent } from "@/types";

interface Props {
  events: MonitoringEvent[];
}

const severityColors: Record<string, string> = {
  info: "bg-blue-100 text-blue-800",
  warning: "bg-orange-100 text-orange-800",
  thesis_breaking: "bg-red-100 text-red-800",
};

export function EventTimeline({ events }: Props) {
  if (events.length === 0) {
    return (
      <Card>
        <CardHeader><CardTitle className="text-base">Monitoring Events</CardTitle></CardHeader>
        <CardContent><p className="text-muted-foreground">No events yet.</p></CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader><CardTitle className="text-base">Monitoring Events</CardTitle></CardHeader>
      <CardContent className="space-y-4">
        {events.map((e) => (
          <div key={e.id} className="border-l-2 border-muted pl-4">
            <div className="flex items-center gap-2">
              <Badge className={severityColors[e.severity]}>{e.severity.replace("_", " ")}</Badge>
              <span className="text-xs text-muted-foreground">{formatDate(e.created_at)}</span>
            </div>
            <h4 className="mt-1 font-medium">{e.title}</h4>
            <p className="text-sm text-muted-foreground">{e.summary}</p>
            {e.ai_analysis && <p className="mt-1 text-sm italic">{e.ai_analysis}</p>}
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
