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


class ReviewedItemResponse(BaseModel):
    """One 'reviewed but not alerted on' item, ready for the position tab.

    Wire shape mirrors what the digest already stashes — same publisher-first
    label so the position page and the email agree on how to refer to the
    source."""
    ticker: str
    headline: str
    reason: str
    source_label: str
    url: str | None = None
    published_at: str | None = None
    matched_signal_labels: list[str] = []


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
    # All signals this event touches — Gemini often tags an article with 3-4
    # relevant signals and the single primary signal_id throws away the rest.
    # The primary is always included as the first element.
    matched_signal_ids: list[uuid.UUID] = []
    matched_signal_labels: list[str] = []
    # Cosine similarity per matched signal (0-1). Gemini explicit-label matches
    # and pre-bound signals don't appear here — only the embedding-inferred
    # ones do, so a missing entry means "we know this is the right signal
    # because the source attributed it explicitly."
    match_confidence_by_signal: dict[uuid.UUID, float] = {}
    evidence_type: str | None = None
    evidence_summary: str | None = None
    verdict: str | None = None
    created_at: datetime
