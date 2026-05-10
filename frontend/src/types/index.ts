export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface Holding {
  id: string;
  ticker: string;
  name: string;
  exchange: string | null;
  quantity: number;
  average_cost_basis: number;
  currency: string;
  current_price: number | null;
  current_value: number | null;
  sector: string | null;
  geography: string | null;
  asset_class: string | null;
  last_updated_at: string;
}

export interface KeyMetric {
  metric: string;
  operator: string;
  threshold: number;
  rationale: string;
}

export interface Thesis {
  id: string;
  holding_id: string;
  status: "draft" | "active" | "needs_review" | "invalidated";
  bull_case: string;
  key_metrics: KeyMetric[];
  risk_factors: string;
  conviction: "high" | "medium" | "low";
  ai_generated: boolean;
  created_at: string;
  updated_at: string;
  invalidated_at: string | null;
  invalidation_reason: string | null;
}

export interface MonitoringEvent {
  id: string;
  holding_id: string;
  thesis_id: string;
  event_type: string;
  severity: "info" | "warning" | "thesis_breaking";
  title: string;
  summary: string;
  source_url: string | null;
  ai_analysis: string | null;
  created_at: string;
}

export interface PortfolioSummary {
  total_value: number;
  total_cost: number;
  total_pnl: number;
  total_pnl_pct: number;
  holdings_count: number;
  theses_active: number;
  theses_need_review: number;
  theses_missing: number;
  sector_breakdown: Record<string, number>;
  geography_breakdown: Record<string, number>;
}

export interface Digest {
  id: string;
  sent_at: string | null;
  period_start: string;
  period_end: string;
  content: { html?: string; events_count?: number; holdings_count?: number };
  status: string;
}

export interface BrokerConnection {
  id: string;
  broker_type: string;
  status: string;
  last_synced_at: string | null;
  created_at: string;
}
