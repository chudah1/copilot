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
