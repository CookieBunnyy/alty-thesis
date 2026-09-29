from datetime import datetime
from typing import Literal

from pydantic import BaseModel

ClientTransactionStatus = Literal["RESERVED", "SOLD"]


class ClientResponse(BaseModel):
    client_id: str
    full_name: str
    location: str | None = None
    phone_number: str | None = None
    email: str | None = None
    agent_id: str
    agent_name: str
    property_id: int
    property_title: str | None = None
    property_location: str | None = None
    property_price: float | None = None
    transaction_type: ClientTransactionStatus
    transaction_date: datetime | None = None
    status: str
    created_at: datetime
    updated_at: datetime
    transaction_id: str | None = None
    amount: float | None = None


class ClientSummary(BaseModel):
    total: int
    reserved: int
    sold: int
    cancelled: int


class ClientSyncResult(BaseModel):
    total: int
    inserted: int
    updated: int
    cancelled: int
    errors: int
    last_synced_at: datetime