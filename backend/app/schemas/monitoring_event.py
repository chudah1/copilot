import uuid
from datetime import datetime
from pydantic import BaseModel


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
    created_at: datetime
    model_config = {"from_attributes": True}
