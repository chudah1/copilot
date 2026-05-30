import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class OnboardingStepStatus(BaseModel):
    done: bool
    count: int | None = None


class OnboardingStatusResponse(BaseModel):
    completed: bool
    current_step: str | None
    steps: dict[str, OnboardingStepStatus]


class OnboardingStateResponse(BaseModel):
    portfolio_connected: bool
    drafts_generated_at: datetime | None
    drafts_reviewed_at: datetime | None
    wizard_skipped_at: datetime | None
    wizard_completed_at: datetime | None
    reasons_written_count: int
    investor_profile: str | None

    model_config = {"from_attributes": True}


class SetInvestorProfileRequest(BaseModel):
    investor_profile: str


class DraftItemResponse(BaseModel):
    draft_id: uuid.UUID
    holding_id: uuid.UUID
    ticker: str
    name: str
    status: str  # pending | ready | failed | reviewed
    thesis_id: uuid.UUID | None
    why_own_it: str | None = None
    must_remain_true: str | None = None
    what_would_change_my_mind: str | None = None

    model_config = {"from_attributes": True}


class DraftStatusResponse(BaseModel):
    total: int
    ready: int
    pending: int
    failed: int
    reviewed: int
    drafts: list[DraftItemResponse]


class SynthesisRequest(BaseModel):
    holding_id: uuid.UUID
    investor_profile: str | None = None
    question1: str
    answer1: str
    question2: str
    answer2: str


class SynthesisResponse(BaseModel):
    thesis_id: uuid.UUID
    why_own_it: str
    must_remain_true: str
    what_would_change_my_mind: str
    ai_summary: str
    # Hype-buyer climb: when the user's raw answers read as vague/hearsay, the
    # frontend should ground them (stress-test + these follow-ups) before relying
    # on the thesis. Defaults keep the field backward-compatible.
    needs_grounding: bool = False
    grounding_reasons: list[str] = []
    suggested_questions: list[str] = []


class GroundingRequest(BaseModel):
    holding_id: uuid.UUID
    investor_profile: str | None = None
    why_own_it: str
    what_would_change_my_mind: str | None = None


class CandidateSignalSchema(BaseModel):
    signal_type: Literal["price_move", "revenue_growth", "earnings_growth"]
    label: str
    threshold_pct: float = Field(ge=0, le=1000, allow_inf_nan=False)
    rationale: str = ""
    operator: Literal[">=", "<=", ">", "<"] | None = None


class GroundingResponse(BaseModel):
    needs_grounding: bool
    reasons: list[str] = []
    suggested_questions: list[str] = []
    bear_case: str | None = None
    key_risks: list[str] = []
    what_to_watch: list[str] = []
    candidate_signals: list[CandidateSignalSchema] = []


class ConfirmSignalsRequest(BaseModel):
    thesis_id: uuid.UUID
    signals: list[CandidateSignalSchema]


class ConfirmSignalsResponse(BaseModel):
    applied: int


class HoldingContextResponse(BaseModel):
    holding_id: uuid.UUID
    ticker: str
    name: str
    sector: str | None
    current_price: float | None
    current_value: float | None
    quantity: float
    average_cost_basis: float

    model_config = {"from_attributes": True}
