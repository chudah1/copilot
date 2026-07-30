import uuid
from datetime import datetime
from pydantic import BaseModel, Field


class HoldingResponse(BaseModel):
    id: uuid.UUID
    ticker: str
    name: str
    exchange: str | None
    quantity: float
    average_cost_basis: float
    average_cost_native: float | None = None
    currency: str
    current_price: float | None
    current_value: float | None
    portfolio_currency: str = "GBP"
    preferred_currency: str = "GBP"
    fx_unavailable: bool = False
    sector: str | None
    geography: str | None
    asset_class: str | None
    last_updated_at: datetime
    model_config = {"from_attributes": True}


class ManualHoldingRequest(BaseModel):
    ticker: str
    name: str
    exchange: str | None = None
    quantity: float = Field(gt=0)
    average_cost_basis: float = Field(gt=0)
    currency: str = "GBP"
    sector: str | None = None
    geography: str | None = None
    asset_class: str = "stock"


class PriorityHoldingSummary(BaseModel):
    holding_id: uuid.UUID
    ticker: str
    name: str
    reason: str
    priority: str


class HoldingPulseResponse(BaseModel):
    holding_id: uuid.UUID
    ticker: str
    name: str
    pulse_status: str  # intact | watch | review
    pulse_basis: str  # evidence | case_review | missing_case | none
    reason: str
    assumption_label: str | None = None
    latest_event_summary: str | None = None
    days_since_thesis_update: int | None = None
    has_thesis: bool
    latest_event_at: datetime | None = None
    urgency_score: int = 0
    pnl_pct: float | None = None
    last_checked_at: datetime | None = None
    recent_event_count: int = 0
    unresolved_event_count: int = 0
    sources_count: int | None = None


class PortfolioPulseResponse(BaseModel):
    pulses: list[HoldingPulseResponse]
    next_digest_at: datetime | None = None


class UpcomingEarningsResponse(BaseModel):
    holding_id: uuid.UUID
    ticker: str
    name: str
    report_date: datetime
    days_until: int


class PortfolioSummary(BaseModel):
    total_value: float
    total_cost: float
    total_pnl: float
    total_pnl_pct: float
    portfolio_currency: str = "GBP"
    preferred_currency: str = "GBP"
    fx_unavailable: bool = False
    holdings_count: int
    theses_active: int
    theses_need_review: int
    theses_missing: int
    top_3_concentration_pct: float
    thesis_coverage_pct: float
    monitorable_thesis_coverage_pct: float
    stale_theses_count: int
    unmonitored_holdings_count: int
    conviction_mismatch_count: int
    monitoring_ready: bool
    monitoring_message: str
    sector_breakdown: dict[str, float]
    geography_breakdown: dict[str, float]
    attention_queue: list[PriorityHoldingSummary]


class MarketSnapshotResponse(BaseModel):
    current_price: float | None = None
    price_change_pct: float | None = None
    cost_basis: float | None = None
    pnl: float | None = None
    pnl_pct: float | None = None
    sector: str | None = None
    pe_ratio: float | None = None
    market_cap: float | None = None
    upcoming_earnings_date: datetime | None = None
    recent_news_count: int = 0
    watch_hints_ok: int = 0
    watch_hints_total: int = 0
    checked_at: datetime | None = None


class CheckNowResponse(BaseModel):
    status: str  # running | completed | rate_limited
    events_created: int
    next_available_at: datetime | None = None
    snapshot: MarketSnapshotResponse | None = None


class PortfolioTrendResponse(BaseModel):
    snapshot_date: str | None = None
    new_event_count: int = 0
    top_3_concentration_pct: float | None = None
    thesis_coverage_pct: float | None = None
    monitorable_pct: float | None = None
    unmonitored_count: int | None = None
    holdings_count: int | None = None


class SimulateTradeRequest(BaseModel):
    ticker: str
    quantity: float = Field(gt=0)
    price_per_share: float = Field(gt=0)


class PortfolioSnapshotResponse(BaseModel):
    total_value: float
    total_cost: float
    holdings_count: int
    top_3_concentration_pct: float
    sector_breakdown: dict[str, float]


class SimulationWarningResponse(BaseModel):
    warning_type: str
    message: str


class SimulateTradeResponse(BaseModel):
    ticker: str
    name: str
    simulated_quantity: float
    simulated_price: float
    simulated_value: float
    simulated_currency: str = "GBP"
    portfolio_currency: str = "GBP"
    preferred_currency: str = "GBP"
    fx_unavailable: bool = False
    before: PortfolioSnapshotResponse
    after: PortfolioSnapshotResponse
    warnings: list[SimulationWarningResponse]


class ConvictionLogEntryResponse(BaseModel):
    id: uuid.UUID
    thesis_id: uuid.UUID
    holding_id: uuid.UUID
    entry_type: str
    content: str
    metadata_json: dict | None = None
    claim_id: uuid.UUID | None = None
    signal_id: uuid.UUID | None = None
    created_at: datetime
    # enriched fields for evidence_reviewed entries
    event_title: str | None = None
    event_severity: str | None = None
    what_would_change_my_mind: str | None = None
    outcome: str | None = None  # "broke" | "held" | None (open)
    resolution_read: str | None = None  # prose from resolved DecisionSnapshot
    # merged evidence entries: one card per event (arrived -> decided -> read)
    received_at: datetime | None = None  # when the evidence arrived, if merged
    bucket: str | None = None  # held | exited | dismissed (decision mirror)
    bet_text: str | None = None  # what the user was relying on at decision time
    follow_up_at: datetime | None = None  # when the outcome gets read back
    model_config = {"from_attributes": True}


class ConvictionLogResponse(BaseModel):
    entries: list[ConvictionLogEntryResponse]
    reason_age_days: int | None = None
    review_count: int = 0


class PricePoint(BaseModel):
    date: str  # ISO date
    close: float


class PriceHistoryEvent(BaseModel):
    date: str  # ISO date
    verdict: str | None = None  # supports | threatens | review | neutral
    severity: str  # info | warning | thesis_breaking


class PriceHistoryResponse(BaseModel):
    ticker: str
    currency: str
    thesis_anchored: bool  # window starts at the written case, not an arbitrary lookback
    start_date: str
    points: list[PricePoint]
    events: list[PriceHistoryEvent]
    average_cost: float | None = None  # native currency, same unit as closes


class ManualNoteRequest(BaseModel):
    content: str = Field(min_length=1, max_length=2000)
