import uuid
from datetime import datetime

from pydantic import BaseModel

from app.schemas.holding import HoldingResponse


class DashboardSummaryMetricsResponse(BaseModel):
    total_value: float
    total_cost: float
    total_pnl: float
    total_pnl_pct: float
    portfolio_currency: str = "GBP"
    preferred_currency: str = "GBP"
    fx_unavailable: bool = False
    holdings_count: int
    monitored_count: int
    needs_decision_count: int
    changed_count: int
    needs_written_case_count: int
    drafts_ready_count: int = 0
    drafts_pending_count: int = 0


class DashboardPortfolioStateResponse(BaseModel):
    kind: str  # needs_decision | changed | needs_written_case | calm
    primary_holding_id: uuid.UUID | None = None
    primary_ticker: str | None = None
    assumption_label: str | None = None
    needs_decision_count: int
    changed_count: int
    needs_written_case_count: int


class DashboardWorkspaceItemResponse(BaseModel):
    holding: HoldingResponse
    thesis_id: uuid.UUID | None = None
    decision_state: str  # needs_decision | changed | needs_written_case | calm
    case_quality: str  # missing | weak | review_overdue | workable | sharp
    pulse_status: str | None = None
    pulse_basis: str | None = None
    assumption_label: str | None = None
    reason: str
    latest_event_summary: str | None = None
    urgency_score: int = 0
    days_since_thesis_update: int | None = None
    review_cadence_days: int | None = None


class DashboardBlindSpotResponse(BaseModel):
    holding: HoldingResponse
    thesis_id: uuid.UUID | None = None
    blind_spot_kind: str  # missing | weak | review_overdue | workable
    reason: str
    review_cadence_days: int | None = None
    days_since_thesis_update: int | None = None


class DashboardRecentDecisionResponse(BaseModel):
    holding_id: uuid.UUID
    thesis_id: uuid.UUID
    ticker: str
    name: str
    entry_type: str
    action: str | None = None
    assumption_label: str | None = None
    content: str
    created_at: datetime


class DashboardDecisionPatternResponse(BaseModel):
    kind: str
    tone: str
    headline: str
    detail: str
    instances: int
    hits: int


class DashboardDecisionMemoryResponse(BaseModel):
    resolved_count: int = 0
    open_followups_count: int = 0
    has_pattern: bool = False
    primary_pattern: DashboardDecisionPatternResponse | None = None
    secondary_patterns: list[DashboardDecisionPatternResponse] = []


class DashboardCoachModeStatsResponse(BaseModel):
    presented_count: int = 0
    acted_count: int = 0
    skipped_count: int = 0
    resolved_count: int = 0
    helpful_count: int = 0
    hurt_count: int = 0


class DashboardCoachMemoryResponse(BaseModel):
    total_presented: int = 0
    acted_count: int = 0
    skipped_count: int = 0
    last_feedback: str | None = None  # presented | acted | skipped
    last_mode: str | None = None
    mode_stats: dict[str, DashboardCoachModeStatsResponse] = {}


class DashboardCoachFeedbackRequest(BaseModel):
    advice_key: str
    mode: str
    event: str  # presented | acted | skipped
    holding_id: uuid.UUID | None = None
    thesis_id: uuid.UUID | None = None
    loop_key: str | None = None
    pattern_kind: str | None = None
    action_label: str | None = None


class DashboardCoachFeedbackResponse(BaseModel):
    ok: bool = True
    advice_key: str
    event: str
    status: str


class DashboardOpenLoopResponse(BaseModel):
    loop_key: str
    loop_type: str
    holding_id: uuid.UUID
    thesis_id: uuid.UUID | None = None
    ticker: str
    name: str
    title: str
    detail: str
    opened_at: datetime
    age_days: int
    priority: int
    cta_label: str
    cta_href: str


class DashboardOpenLoopDismissRequest(BaseModel):
    loop_key: str
    dismiss_for_days: int = 7


class DashboardOpenLoopDismissedResponse(BaseModel):
    ok: bool = True
    loop_key: str
    dismissed_until: datetime


class DashboardCommandCenterHoldingResponse(BaseModel):
    holding: HoldingResponse
    thesis_id: uuid.UUID | None = None
    workflow_state: str
    workflow_label: str
    workflow_reason: str
    primary_cta_label: str
    primary_cta_href: str
    pulse_status: str | None = None
    pulse_basis: str | None = None
    assumption_label: str | None = None
    case_quality: str | None = None
    days_since_thesis_update: int | None = None
    latest_event_summary: str | None = None
    supporting_title: str | None = None
    supporting_summary: str | None = None
    supporting_created_at: datetime | None = None
    open_loop_count: int = 0
    open_loop_title: str | None = None
    open_loop_detail: str | None = None


class DashboardCommandCenterSectionResponse(BaseModel):
    kind: str
    title: str
    count: int
    empty_copy: str
    items: list[DashboardCommandCenterHoldingResponse]


class DashboardCommandCenterSummaryResponse(BaseModel):
    needs_review_count: int = 0
    held_up_count: int = 0
    unclear_theses_count: int = 0
    decision_debt_count: int = 0


class DashboardCommandCenterResponse(BaseModel):
    investor_profile: str | None = None
    summary: DashboardCommandCenterSummaryResponse
    sections: list[DashboardCommandCenterSectionResponse]


class DashboardWorkspaceResponse(BaseModel):
    investor_profile: str | None = None
    portfolio_state: DashboardPortfolioStateResponse
    summary_metrics: DashboardSummaryMetricsResponse
    top_decision: DashboardWorkspaceItemResponse | None = None
    watchlist: list[DashboardWorkspaceItemResponse]
    blind_spots: list[DashboardBlindSpotResponse]
    recent_decisions: list[DashboardRecentDecisionResponse]
    decision_memory: DashboardDecisionMemoryResponse
