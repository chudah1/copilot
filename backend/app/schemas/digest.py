import uuid
from datetime import datetime
from pydantic import BaseModel


class DigestResponse(BaseModel):
    id: uuid.UUID
    sent_at: datetime | None
    period_start: datetime
    period_end: datetime
    content: dict
    status: str
    model_config = {"from_attributes": True}
