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

export interface Thesis {
  id: string;
  holding_id: string;
  status: "draft" | "active" | "needs_review" | "invalidated";
  thesis_kind: "company" | "portfolio_role" | "plan";
  why_own_it: string;
  must_remain_true: string | null;
  what_would_change_my_mind: string | null;
  confidence: "high" | "medium" | "low";
  review_cadence_days: number;
  ai_summary: string | null;
  interpretation: Record<string, unknown> | null;
  source: "user" | "ai_assisted";
  created_at: string;
  updated_at: string;
  invalidated_at: string | null;
  invalidation_reason: string | null;
}

export interface ThesisAssistResponse {
  ai_summary: string;
  interpretation: Record<string, unknown>;
  source: "ai_assisted";
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
  top_3_concentration_pct: number;
  thesis_coverage_pct: number;
  monitorable_thesis_coverage_pct: number;
  stale_theses_count: number;
  unmonitored_holdings_count: number;
  conviction_mismatch_count: number;
  monitoring_ready: boolean;
  monitoring_message: string;
  sector_breakdown: Record<string, number>;
  geography_breakdown: Record<string, number>;
  attention_queue: Array<{
    holding_id: string;
    ticker: string;
    name: string;
    reason: string;
    priority: "critical" | "high" | "medium";
  }>;
}

export interface Digest {
  id: string;
  sent_at: string | null;
  period_start: string;
  period_end: string;
  content: {
    html?: string;
    events_count?: number;
    holdings_count?: number;
    stable_holdings_count?: number;
    headline?: string;
    summary_points?: string[];
    missing_theses_count?: number;
    stale_theses_count?: number;
    concentration_warning?: string;
  };
  status: string;
}

export interface BrokerConnection {
  id: string;
  broker_type: string;
  status: string;
  last_synced_at: string | null;
  created_at: string;
}
