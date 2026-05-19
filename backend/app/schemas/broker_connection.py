import uuid
from datetime import datetime
from pydantic import BaseModel, field_validator


class ConnectBrokerRequest(BaseModel):
    broker_type: str
    api_key: str
    api_secret: str | None = None

    @field_validator("api_key")
    @classmethod
    def strip_api_key(cls, v: str) -> str:
        return v.strip()

    @field_validator("api_secret")
    @classmethod
    def strip_api_secret(cls, v: str | None) -> str | None:
        return v.strip() if v else None


class BrokerConnectionResponse(BaseModel):
    id: uuid.UUID
    broker_type: str
    status: str
    last_synced_at: datetime | None
    created_at: datetime
    model_config = {"from_attributes": True}
