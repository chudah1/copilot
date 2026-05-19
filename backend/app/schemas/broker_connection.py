import uuid
from datetime import datetime
from pydantic import BaseModel, field_validator


class ConnectBrokerRequest(BaseModel):
    broker_type: str
    api_key: str

    @field_validator("api_key")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        return v.strip()


class BrokerConnectionResponse(BaseModel):
    id: uuid.UUID
    broker_type: str
    status: str
    last_synced_at: datetime | None
    created_at: datetime
    model_config = {"from_attributes": True}
