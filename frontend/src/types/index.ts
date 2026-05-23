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
  why_own_it: string;
  must_remain_true: string;
  what_would_change_my_mind: string;
  ai_summary: string;
  interpretation: Record<string, unknown>;
  source: "ai_assisted";
}

export interface ThesisDecompositionSignal {
  id: string;
  signal_type: string;
  signal_label: string | null;
  signal_config_json: Record<string, unknown> | null;
  rationale: string | null;
  confidence: number | null;
  confirmation_required: boolean;
  user_confirmed: boolean | null;
  active: boolean;
  created_at: string;
}

export interface ThesisDecompositionEntity {
  id: string;
  entity_name: string;
  entity_ticker: string | null;
  entity_type: string | null;
  relation_type: string | null;
  rationale: string | null;
  confidence: number | null;
  confirmation_required: boolean;
  user_confirmed: boolean | null;
  created_at: string;
  signals: ThesisDecompositionSignal[];
}

export interface ThesisDecompositionClaim {
  id: string;
  claim_text: string;
  claim_type: string | null;
  confidence: number | null;
  position: number;
  created_at: string;
  entities: ThesisDecompositionEntity[];
}

export interface ThesisDecomposition {
  id: string;
  thesis_id: string;
  version: number;
  status: "draft" | "confirmed" | "partially_confirmed" | "rejected" | "pending" | "failed";
  reason_type: string | null;
  monitorability: string | null;
  decomposition_confidence: number | null;
  provider: string | null;
  model: string | null;
  prompt_version: string | null;
  created_at: string;
  claims: ThesisDecompositionClaim[];
}

export interface ThesisDecompositionEnvelope {
  status: "draft" | "confirmed" | "partially_confirmed" | "rejected" | "pending" | "failed";
  message: string | null;
  decomposition: ThesisDecomposition | null;
}

export interface ConfirmDecompositionRequest {
  decomposition_id: string;
  entities: Array<{
    id: string;
    user_confirmed: boolean;
  }>;
  signals: Array<{
    id: string;
    user_confirmed: boolean;
    active: boolean;
  }>;
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
  review_action: "reaffirmed" | "ignored" | "lowered_confidence" | "invalidated" | "not_relevant" | null;
  review_notes: string | null;
  claim_id: string | null;
  signal_id: string | null;
  signal_label: string | null;
  evidence_type: string | null;
  evidence_summary: string | null;
  verdict: "supports" | "threatens" | "neutral" | "review" | null;
  created_at: string;
}

export interface MonitoringEventReviewResponse {
  id: string;
  monitoring_event_id: string;
  thesis_id: string;
  action: "reaffirmed" | "ignored" | "lowered_confidence" | "invalidated" | "not_relevant";
  notes: string | null;
  created_at: string;
  thesis: Thesis;
  reason_age_days: number | null;
}

export interface ConvictionLogEntry {
  id: string;
  thesis_id: string;
  holding_id: string;
  entry_type: string;
  content: string;
  metadata_json: Record<string, unknown> | null;
  claim_id: string | null;
  signal_id: string | null;
  created_at: string;
}

export interface ConvictionLogResponse {
  entries: ConvictionLogEntry[];
  reason_age_days: number | null;
  review_count: number;
}

export interface QuarterlyReviewHolding {
  holding_id: string;
  thesis_id: string;
  ticker: string;
  name: string;
  currency: string;
  current_price: number | null;
  reason_age_days: number;
  why_own_it: string;
  response: "yes_absolutely" | "probably" | "not_sure" | "no" | null;
  response_notes: string | null;
  reviewed_at: string | null;
}

export interface QuarterlyReviewCurrent {
  review_id: string;
  quarter: string;
  status: "pending" | "completed" | "skipped";
  total_holdings: number;
  completed_count: number;
  pending_count: number;
  holdings: QuarterlyReviewHolding[];
}

export interface QuarterlyReviewSubmission {
  review_id: string;
  holding_id: string;
  thesis_id: string;
  response: "yes_absolutely" | "probably" | "not_sure" | "no";
  notes: string | null;
  price_at_review: number | null;
  created_at: string;
  thesis_status: Thesis["status"];
  pending_count: number;
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
    digest_mode?: "events" | "quiet_week";
    subject_line?: string;
    events_count?: number;
    holdings_count?: number;
    stable_holdings_count?: number;
    headline?: string;
    summary_points?: string[];
    missing_theses_count?: number;
    stale_theses_count?: number;
    concentration_warning?: string;
    monitoring_receipt?: string;
    quiet_nudge?: string | null;
    consecutive_quiet_weeks?: number;
    investor_profile?: "thesis_driven" | "hearsay_driven" | null;
    next_earnings?: {
      ticker: string;
      report_date: string;
      days_until: number;
    } | null;
  };
  status: string;
}

export interface HoldingPulse {
  holding_id: string;
  ticker: string;
  name: string;
  pulse_status: "intact" | "watch" | "review";
  reason: string;
  assumption_label: string | null;
  latest_event_summary: string | null;
  days_since_thesis_update: number | null;
  has_thesis: boolean;
  latest_event_at: string | null;
  urgency_score: number;
  pnl_pct: number | null;
  last_checked_at: string | null;
  recent_event_count: number;
}

export interface RecentEventSummary {
  holding_id: string;
  ticker: string;
  title: string;
  severity: "info" | "warning" | "thesis_breaking";
  event_type: string;
  created_at: string | null;
}

export interface PortfolioPulse {
  pulses: HoldingPulse[];
  next_digest_at: string | null;
  recent_events?: RecentEventSummary[];
}

export interface UpcomingEarnings {
  holding_id: string;
  ticker: string;
  name: string;
  report_date: string;
  days_until: number;
}

export interface UserPreferences {
  digest_frequency: string;
  digest_day: string;
  digest_time: string;
  earnings_alerts: boolean;
  quarterly_review_reminders: boolean;
  email_enabled: boolean;
  notification_sensitivity: string;
}


export interface PortfolioTrend {
  snapshot_date: string | null;
  top_3_concentration_pct: number | null;
  thesis_coverage_pct: number | null;
  monitorable_pct: number | null;
  unmonitored_count: number | null;
  holdings_count: number | null;
}

export interface HealthCheckCandidate {
  event_type: string;
  description: string;
  severity: string | null;
  ai_analysis: string | null;
}

export interface WatchHintStatus {
  metric: string;
  operator: string;
  threshold: number;
  actual_value: number;
  breached: boolean;
  rationale: string;
}

export interface HealthCheckResult {
  thesis_id: string;
  ticker: string;
  current_price: number | null;
  sector: string | null;
  pe_ratio: number | null;
  market_cap: number | null;
  upcoming_earnings_date: string | null;
  recent_earnings_surprise_pct: number | null;
  candidates: HealthCheckCandidate[];
  watch_hints_status: WatchHintStatus[];
  recent_news_count: number;
  thesis_assessment: "all_clear" | "watch" | "review_needed";
  checked_at: string;
}

export interface BrokerConnection {
  id: string;
  broker_type: string;
  status: string;
  last_synced_at: string | null;
  created_at: string;
}

export interface MarketSnapshot {
  current_price: number | null;
  price_change_pct: number | null;
  cost_basis: number | null;
  pnl: number | null;
  pnl_pct: number | null;
  sector: string | null;
  pe_ratio: number | null;
  market_cap: number | null;
  upcoming_earnings_date: string | null;
  recent_news_count: number;
  watch_hints_ok: number;
  watch_hints_total: number;
  checked_at: string | null;
}

export interface CheckNowResponse {
  status: "completed" | "rate_limited";
  events_created: number;
  next_available_at: string | null;
  snapshot: MarketSnapshot | null;
}

export interface SimulateTradeRequest {
  ticker: string;
  quantity: number;
  price_per_share: number;
}

export interface PortfolioSnapshot {
  total_value: number;
  total_cost: number;
  holdings_count: number;
  top_3_concentration_pct: number;
  sector_breakdown: Record<string, number>;
}

export interface SimulationWarning {
  warning_type: string;
  message: string;
}

export interface SimulateTradeResponse {
  ticker: string;
  name: string;
  simulated_quantity: number;
  simulated_price: number;
  simulated_value: number;
  before: PortfolioSnapshot;
  after: PortfolioSnapshot;
  warnings: SimulationWarning[];
}

export interface OnboardingBannerResponse {
  show: boolean;
  banner_type: "start_first_reason" | "first_reason_monitoring" | "add_more_reasons" | null;
  message: string | null;
  holdings_count: number;
  reasons_count: number;
  suggested_holding: {
    id: string;
    ticker: string;
    name: string;
  } | null;
}

export interface CounterThesisResponse {
  thesis_id: string;
  bear_case: string;
  key_risks: string[];
  blind_spots: string[];
  suggested_additions: string[];
  generated_at: string;
}

export interface OnboardingState {
  portfolio_connected: boolean;
  drafts_generated_at: string | null;
  drafts_reviewed_at: string | null;
  wizard_skipped_at: string | null;
  wizard_completed_at: string | null;
  reasons_written_count: number;
  investor_profile: "thesis_driven" | "hearsay_driven" | null;
}

export interface DraftItem {
  draft_id: string;
  holding_id: string;
  ticker: string;
  name: string;
  status: "pending" | "ready" | "failed" | "reviewed";
  thesis_id: string | null;
  why_own_it: string | null;
  must_remain_true: string | null;
  what_would_change_my_mind: string | null;
}

export interface DraftStatus {
  total: number;
  ready: number;
  pending: number;
  failed: number;
  reviewed: number;
  drafts: DraftItem[];
}

export interface LivePrice {
  ticker: string;
  current_price: number;
  current_value: number;
}

export interface HoldingContext {
  holding_id: string;
  ticker: string;
  name: string;
  sector: string | null;
  current_price: number | null;
  current_value: number | null;
  quantity: number;
  average_cost_basis: number;
}

export interface SynthesisRequest {
  holding_id: string;
  investor_profile: "thesis_driven" | "hearsay_driven" | null;
  question1: string;
  answer1: string;
  question2: string;
  answer2: string;
}

export interface SynthesisResponse {
  thesis_id: string;
  why_own_it: string;
  must_remain_true: string;
  what_would_change_my_mind: string;
  ai_summary: string;
}

export interface ClaimVerdict {
  claim_id: string;
  claim_text: string;
  verdict: "holds" | "watch" | "broken" | "unclear";
  explanation: string;
  evidence: string | null;
}

export interface EarningsReviewResult {
  thesis_id: string;
  ticker: string;
  verdicts: ClaimVerdict[];
  overall_assessment: "thesis_intact" | "watch" | "thesis_challenged";
  summary: string;
  fiscal_quarter: string | null;
  earnings_surprise_pct: number | null;
  log_entry_id: string;
  reviewed_at: string;
}
