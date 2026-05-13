import uuid
from datetime import datetime
from pydantic import BaseModel


class HoldingResponse(BaseModel):
    id: uuid.UUID
    ticker: str
    name: str
    exchange: str | None
    quantity: float
    average_cost_basis: float
    currency: str
    current_price: float | None
    current_value: float | None
    sector: str | None
    geography: str | None
    asset_class: str | None
    last_updated_at: datetime
    model_config = {"from_attributes": True}


class ManualHoldingRequest(BaseModel):
    ticker: str
    name: str
    exchange: str | None = None
    quantity: float
    average_cost_basis: float
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


class PortfolioSummary(BaseModel):
    total_value: float
    total_cost: float
    total_pnl: float
    total_pnl_pct: float
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
