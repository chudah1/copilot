import uuid
from datetime import datetime
from pydantic import BaseModel
from app.schemas.thesis import ThesisResponse


class ReviewMonitoringEventRequest(BaseModel):
    action: str
    notes: str | None = None


class MonitoringEventReviewResponse(BaseModel):
    id: uuid.UUID
    monitoring_event_id: uuid.UUID
    thesis_id: uuid.UUID
    action: str
    notes: str | None
    created_at: datetime
    thesis: ThesisResponse
    reason_age_days: int | None = None


class MonitoringEventResponse(BaseModel):
    id: uuid.UUID
    holding_id: uuid.UUID
    thesis_id: uuid.UUID
    event_type: str
    severity: str
    title: str
    summary: str
    source_url: str | None
    ai_analysis: str | None
    review_action: str | None = None
    review_notes: str | None = None
    claim_id: uuid.UUID | None = None
    signal_id: uuid.UUID | None = None
    signal_label: str | None = None
    evidence_type: str | None = None
    evidence_summary: str | None = None
    verdict: str | None = None
    created_at: datetime
