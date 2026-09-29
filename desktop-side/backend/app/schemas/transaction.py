from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class TransactionResponse(BaseModel):
    transaction_id: str
    client_id: str
    client_name: str
    property_id: int
    property_title: str | None = None
    agent_id: str
    agent_name: str
    transaction_type: str
    transaction_date: datetime
    amount: Decimal
    status: str
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


class TransactionSummary(BaseModel):
    total: int
    reserved: int
    completed: int
    amount_total: Decimal


class TransactionSyncResult(BaseModel):
    total: int
    inserted: int
    updated: int
    errors: int
    last_synced_at: datetime