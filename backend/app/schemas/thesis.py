import uuid
from datetime import datetime
from pydantic import BaseModel


class KeyMetric(BaseModel):
    metric: str
    operator: str
    threshold: float
    rationale: str


class GenerateThesisRequest(BaseModel):
    holding_id: uuid.UUID


class ThesisResponse(BaseModel):
    id: uuid.UUID
    holding_id: uuid.UUID
    status: str
    bull_case: str
    key_metrics: list[KeyMetric]
    risk_factors: str
    conviction: str
    ai_generated: bool
    created_at: datetime
    updated_at: datetime
    invalidated_at: datetime | None
    invalidation_reason: str | None
    model_config = {"from_attributes": True}


class UpdateThesisRequest(BaseModel):
    bull_case: str | None = None
    key_metrics: list[KeyMetric] | None = None
    risk_factors: str | None = None
    conviction: str | None = None
    status: str | None = None


class InvalidateThesisRequest(BaseModel):
    reason: str
