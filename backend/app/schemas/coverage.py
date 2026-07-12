import uuid
from datetime import datetime
from pydantic import BaseModel


class SignalCoverageResponse(BaseModel):
    signal_id: uuid.UUID
    signal_label: str | None
    signal_type: str | None
    claim_id: uuid.UUID
    claim_text: str
    covered: bool
    matched_event_count: int
    last_matched_at: datetime | None
    last_event_id: uuid.UUID | None
    last_event_severity: str | None
    # Maximum LLM-adjudicated confidence we saw on any matching event in the
    # window. None means every match was either explicit (Gemini label / pre-
    # bound) or simply has no confidence recorded — both render as "strong."
    max_confidence: float | None
    is_strong_binding: bool


class ThesisCoverageResponse(BaseModel):
    thesis_id: uuid.UUID
    window_start: datetime
    window_end: datetime
    covered_count: int
    uncovered_count: int
    inactive_signal_count: int
    no_decomposition: bool
    signals: list[SignalCoverageResponse]


class CoveragePassResponse(BaseModel):
    """One pipeline pass — the funnel that answers 'where did the candidates
    go?' for a specific check-now / daily run / EDGAR-watch pass."""

    id: uuid.UUID
    thesis_id: uuid.UUID
    holding_id: uuid.UUID
    run_id: str
    triggered_by: str
    started_at: datetime
    finished_at: datetime | None
    payload: dict
    created_at: datetime


class RetrievalChunkResponse(BaseModel):
    chunk_id: uuid.UUID
    source_type: str
    source_id: str | None
    chunk_type: str
    score: float
    chunk_text: str
    embedded_at: datetime | None
    created_at: datetime


class ClaimRetrievalResponse(BaseModel):
    claim_id: uuid.UUID
    claim_text: str
    embedding_text: str | None
    hits: list[RetrievalChunkResponse]


class ThesisCoverageRetrievalResponse(BaseModel):
    thesis_id: uuid.UUID
    window_start: datetime
    window_end: datetime
    chunk_pool_size: int
    no_decomposition: bool
    claim_results: list[ClaimRetrievalResponse]


class ClaimRetrievalComparisonResponse(BaseModel):
    claim_id: uuid.UUID
    claim_text: str
    embedding_text: str | None
    signal_labels: list[str]
    covered_signal_count: int
    uncovered_signal_count: int
    matched_event_count: int
    retrieval_hit_count: int
    top_hit_score: float | None
    hits: list[RetrievalChunkResponse]


class ThesisCoverageComparisonResponse(BaseModel):
    thesis_id: uuid.UUID
    window_start: datetime
    window_end: datetime
    chunk_pool_size: int
    no_decomposition: bool
    covered_count: int
    uncovered_count: int
    claim_results: list[ClaimRetrievalComparisonResponse]


class MonitoringSoakBasketEntryRequest(BaseModel):
    label: str
    ticker: str | None = None
    holding_id: uuid.UUID | None = None


class MonitoringSoakReportRequest(BaseModel):
    days: int = 5
    timezone_name: str = "Europe/London"
    holdings: list[MonitoringSoakBasketEntryRequest] = []


class MonitoringSoakRecentEventResponse(BaseModel):
    created_at: datetime
    severity: str
    event_type: str
    title: str


class MonitoringSoakHoldingSummaryResponse(BaseModel):
    label: str
    holding_id: uuid.UUID
    ticker: str
    holding_name: str
    thesis_id: uuid.UUID | None
    thesis_status: str | None
    latest_triggered_by: str | None
    latest_pass_started_at: datetime | None
    latest_stage_counts: dict[str, int]
    latest_events_persisted: int
    pass_count: int
    total_events_persisted: int
    total_same_event_merges: int
    source_error_count: int
    partial_failure_count: int
    recent_event_count: int
    recent_events: list[MonitoringSoakRecentEventResponse]
    assessment: str
    assessment_reason: str


class MonitoringSoakUnresolvedEntryResponse(BaseModel):
    label: str
    reason: str


class MonitoringSoakReportResponse(BaseModel):
    start_at: datetime
    end_at: datetime
    timezone_name: str
    markdown: str
    summaries: list[MonitoringSoakHoldingSummaryResponse]
    unresolved: list[MonitoringSoakUnresolvedEntryResponse]
