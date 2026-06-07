import uuid
from datetime import datetime
from pydantic import BaseModel


class MonitoringGapResponse(BaseModel):
    id: uuid.UUID
    thesis_id: uuid.UUID | None
    source: str
    error_message: str
    run_id: str
    failed_at: datetime

    model_config = {"from_attributes": True}
