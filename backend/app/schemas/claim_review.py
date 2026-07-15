import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class ClaimEvidenceItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    event_type: str
    severity: str
    verdict: str | None
    title: str
    summary: str
    ai_analysis: str | None
    source_url: str | None
    created_at: datetime


class ClaimCheckInStateResponse(BaseModel):
    claim_id: uuid.UUID | None
    label: str
    status: str
    last_reviewed_at: datetime | None
    needs_review: bool
    needs_review_reason: str
    supports: list[ClaimEvidenceItem]
    threatens: list[ClaimEvidenceItem]
    neutral: list[ClaimEvidenceItem]


class ThesisCheckInResponse(BaseModel):
    thesis_id: uuid.UUID
    claims: list[ClaimCheckInStateResponse]
    needs_review_count: int


class ClaimDecision(BaseModel):
    claim_id: uuid.UUID | None = None
    status: Literal["holds", "weakened", "broken"]
    notes: str | None = None


class SubmitClaimReviewsRequest(BaseModel):
    decisions: list[ClaimDecision]
    thesis_action: Literal["keep_lowered", "invalidate", "rewrite"] | None = None
    notes: str | None = None


class SubmitClaimReviewsResponse(BaseModel):
    session_id: uuid.UUID
    thesis_status: str
    thesis_confidence: str
