import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class QuarterlyReviewHoldingResponse(BaseModel):
    holding_id: uuid.UUID
    thesis_id: uuid.UUID
    ticker: str
    name: str
    currency: str
    current_price: float | None = None
    reason_age_days: int
    why_own_it: str
    response: str | None = None
    response_notes: str | None = None
    reviewed_at: datetime | None = None


class DecisionPatternExampleResponse(BaseModel):
    ticker: str
    bucket: str
    bet_text: str | None = None
    read: str | None = None
    decided_at: datetime | None = None
    resolved_at: datetime | None = None


class DecisionPatternResponse(BaseModel):
    kind: str
    tone: str
    headline: str
    detail: str
    instances: int
    hits: int
    examples: list[DecisionPatternExampleResponse] = []


class DecisionPatternsResponse(BaseModel):
    patterns: list[DecisionPatternResponse]
    resolved_count: int


class QuarterlyReviewCurrentResponse(BaseModel):
    review_id: uuid.UUID
    quarter: str
    status: str
    total_holdings: int
    completed_count: int
    pending_count: int
    holdings: list[QuarterlyReviewHoldingResponse]


class SubmitQuarterlyReviewRequest(BaseModel):
    holding_id: uuid.UUID
    response: str
    notes: str | None = Field(default=None, max_length=2000)


class QuarterlyReviewSubmissionResponse(BaseModel):
    review_id: uuid.UUID
    holding_id: uuid.UUID
    thesis_id: uuid.UUID
    response: str
    notes: str | None = None
    price_at_review: float | None = None
    created_at: datetime
    thesis_status: str
    pending_count: int
