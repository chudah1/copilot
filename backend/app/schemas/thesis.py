import uuid
from typing import Any, Literal
from datetime import datetime
from pydantic import BaseModel, field_validator


class CreateThesisRequest(BaseModel):
    holding_id: uuid.UUID
    thesis_kind: str = "company"
    why_own_it: str
    must_remain_true: str | None = None
    what_would_change_my_mind: str
    confidence: str = "medium"
    review_cadence_days: int = 7
    ai_summary: str | None = None
    interpretation: dict[str, Any] | None = None
    source: str = "user"
    status: str = "draft"

    @field_validator("what_would_change_my_mind")
    @classmethod
    def exit_condition_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Exit condition cannot be empty — it controls when red alerts fire")
        return v


class AssistThesisRequest(BaseModel):
    holding_id: uuid.UUID
    draft_text: str | None = None
    why_own_it: str | None = None
    must_remain_true: str | None = None
    what_would_change_my_mind: str | None = None


class AssistThesisResponse(BaseModel):
    why_own_it: str
    must_remain_true: str
    what_would_change_my_mind: str
    ai_summary: str
    interpretation: dict[str, Any]
    source: str = "ai_assisted"


class DraftThesisRequest(BaseModel):
    ticker: str


class DraftThesisResponse(BaseModel):
    why_own_it: str
    must_remain_true: str
    what_would_change_my_mind: str


class ThesisSignalResponse(BaseModel):
    id: uuid.UUID
    signal_type: str
    signal_label: str | None
    signal_config_json: dict[str, Any] | None
    rationale: str | None
    confidence: float | None
    confirmation_required: bool
    user_confirmed: bool | None
    active: bool
    created_at: datetime
    model_config = {"from_attributes": True}


class ThesisEntityResponse(BaseModel):
    id: uuid.UUID
    entity_name: str
    entity_ticker: str | None
    entity_type: str | None
    relation_type: str | None
    rationale: str | None
    confidence: float | None
    confirmation_required: bool
    user_confirmed: bool | None
    created_at: datetime
    signals: list[ThesisSignalResponse]
    model_config = {"from_attributes": True}


class ThesisClaimResponse(BaseModel):
    id: uuid.UUID
    claim_text: str
    claim_type: str | None
    confidence: float | None
    position: int
    created_at: datetime
    entities: list[ThesisEntityResponse]
    model_config = {"from_attributes": True}


class ThesisDecompositionResponse(BaseModel):
    id: uuid.UUID
    thesis_id: uuid.UUID
    version: int
    status: str
    reason_type: str | None
    monitorability: str | None
    decomposition_confidence: float | None
    provider: str | None
    model: str | None
    prompt_version: str | None
    created_at: datetime
    claims: list[ThesisClaimResponse]
    model_config = {"from_attributes": True}


class ThesisDecompositionEnvelopeResponse(BaseModel):
    status: str
    message: str | None = None
    decomposition: ThesisDecompositionResponse | None = None


class ThesisResponse(BaseModel):
    id: uuid.UUID
    holding_id: uuid.UUID
    status: str
    thesis_kind: str
    why_own_it: str
    must_remain_true: str | None
    what_would_change_my_mind: str | None
    confidence: str
    review_cadence_days: int
    ai_summary: str | None
    interpretation: dict[str, Any] | None
    source: str
    created_at: datetime
    updated_at: datetime
    invalidated_at: datetime | None
    invalidation_reason: str | None
    health_score: int | None
    health_label: str | None
    model_config = {"from_attributes": True}


class UpdateThesisRequest(BaseModel):
    thesis_kind: str | None = None
    why_own_it: str | None = None
    must_remain_true: str | None = None
    what_would_change_my_mind: str | None = None
    confidence: str | None = None
    review_cadence_days: int | None = None
    ai_summary: str | None = None
    interpretation: dict[str, Any] | None = None
    source: str | None = None
    status: str | None = None

    @field_validator("what_would_change_my_mind")
    @classmethod
    def exit_condition_not_empty(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("Exit condition cannot be empty — it controls when red alerts fire")
        return v


class DebugDecomposeRequest(BaseModel):
    ticker: str
    name: str
    why_own_it: str
    must_remain_true: str | None = None
    what_would_change_my_mind: str | None = None


class ProviderDebugResult(BaseModel):
    provider: str
    model: str | None = None
    success: bool
    status: str
    latency_ms: int | None = None
    failure_reason: str | None = None
    raw_output: dict[str, Any] | None = None
    normalized_output: dict[str, Any] | None = None
    valid: bool
    validation_error: str | None = None


class GatewayDebugResult(BaseModel):
    success: bool
    status: str
    provider: str | None = None
    model: str | None = None
    confidence: float | None = None
    latency_ms: int | None = None
    failure_reason: str | None = None
    normalized_output: dict[str, Any] | None = None


class DebugDecomposeResponse(BaseModel):
    providers: list[ProviderDebugResult]
    gateway_result: GatewayDebugResult


class ConfirmDecompositionEntityRequest(BaseModel):
    id: uuid.UUID
    user_confirmed: bool


class ConfirmDecompositionSignalRequest(BaseModel):
    id: uuid.UUID
    user_confirmed: bool
    active: bool = False


class ConfirmDecompositionRequest(BaseModel):
    decomposition_id: uuid.UUID
    entities: list[ConfirmDecompositionEntityRequest] = []
    signals: list[ConfirmDecompositionSignalRequest] = []


class StressTestRequest(BaseModel):
    ticker: str
    draft_thesis: str | None = None


class StressTestRiskGroupResponse(BaseModel):
    category: str
    items: list[str]
    model_config = {"from_attributes": True}


class StressTestSourceNoteResponse(BaseModel):
    label: str
    detail: str
    source: str
    url: str | None = None
    model_config = {"from_attributes": True}


class StressTestCandidateSignalResponse(BaseModel):
    signal_type: str
    label: str
    threshold_pct: float = 0.0
    rationale: str = ""
    operator: str | None = None
    watch_for: str | None = None
    direction: str | None = None
    model_config = {"from_attributes": True}


class StressTestResponse(BaseModel):
    ticker: str
    bear_case: str
    key_risks: list[str]
    risk_groups: list[StressTestRiskGroupResponse] = []
    blind_spots: list[str]
    what_to_watch: list[str]
    current_price: float | None
    currency: str = "USD"
    cached: bool
    source_notes: list[StressTestSourceNoteResponse] = []
    candidate_signals: list[StressTestCandidateSignalResponse] = []


class InvalidateThesisRequest(BaseModel):
    reason: str


class HealthCheckCandidateResponse(BaseModel):
    event_type: str
    description: str
    severity: str | None = None
    ai_analysis: str | None = None


class WatchHintStatusResponse(BaseModel):
    metric: str
    operator: str
    threshold: float
    actual_value: float
    breached: bool
    rationale: str


class HealthCheckResponse(BaseModel):
    thesis_id: uuid.UUID
    ticker: str
    current_price: float | None = None
    currency: str = "GBP"
    sector: str | None = None
    pe_ratio: float | None = None
    market_cap: float | None = None
    upcoming_earnings_date: datetime | None = None
    recent_earnings_surprise_pct: float | None = None
    candidates: list[HealthCheckCandidateResponse]
    watch_hints_status: list[WatchHintStatusResponse]
    recent_news_count: int
    thesis_assessment: str
    checked_at: datetime


class CounterThesisResponse(BaseModel):
    thesis_id: uuid.UUID
    bear_case: str
    key_risks: list[str]
    blind_spots: list[str]
    suggested_additions: list[str]
    generated_at: datetime


class ClaimVerdictResponse(BaseModel):
    claim_id: str
    claim_text: str
    verdict: str  # "holds" | "watch" | "broken" | "unclear"
    explanation: str
    evidence: str | None = None


class EarningsReviewResponse(BaseModel):
    thesis_id: uuid.UUID
    ticker: str
    verdicts: list[ClaimVerdictResponse]
    overall_assessment: str  # "thesis_intact" | "watch" | "thesis_challenged"
    summary: str
    fiscal_quarter: str | None = None
    earnings_surprise_pct: float | None = None
    log_entry_id: uuid.UUID
    reviewed_at: datetime


class HistoricalAuditResultItem(BaseModel):
    description: str
    severity: Literal["thesis_breaking", "warning", "info"]
    event_type: str
    event_date: str | None = None
    evidence: dict[str, Any] | None = None


class HistoricalAuditResponse(BaseModel):
    status: Literal["pending", "ready", "empty", "failed"]
    results: list[HistoricalAuditResultItem] | None = None

    model_config = {"from_attributes": True}
