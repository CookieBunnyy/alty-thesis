from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ClientResponse(BaseModel):
    client_id: str
    external_client_id: str | None = None
    full_name: str
    location: str | None = None
    phone_number: str | None = None
    email: str | None = None
    occupation: str | None = None
    civil_status: str | None = None
    preferred_contact: str | None = None
    purpose_of_purchase: str | None = None
    agent_id: str | None = None
    agent_name: str | None = None
    property_id: int | None = None
    property_external_id: str | None = None
    property_title: str | None = None
    property_location: str | None = None
    property_price: float | None = None
    transaction_type: str | None = None
    transaction_date: datetime | None = None
    status: str
    source: str | None = None
    sync_status: str | None = None
    created_at: datetime
    updated_at: datetime
    transaction_id: str | None = None
    amount: float | None = None
    transaction_count: int = 0


class ClientSummary(BaseModel):
    total: int
    prospect: int
    reserved: int
    sold: int
    cancelled: int


class ClientProfile(BaseModel):
    client: ClientResponse
    transactions: list[dict[str, Any]]
    documents: list[dict[str, Any]]


class ClientSyncResult(BaseModel):
    total: int
    inserted: int
    updated: int
    skipped_pending: int = 0
    cancelled: int = 0
    errors: int
    error_messages: list[str] = []
    last_synced_at: datetime
