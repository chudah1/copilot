import uuid
from datetime import datetime
from pydantic import BaseModel


class ConnectBrokerRequest(BaseModel):
    broker_type: str
    api_key: str


class BrokerConnectionResponse(BaseModel):
    id: uuid.UUID
    broker_type: str
    status: str
    last_synced_at: datetime | None
    created_at: datetime
    model_config = {"from_attributes": True}
