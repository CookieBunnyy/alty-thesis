from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class TransactionResponse(BaseModel):
    transaction_id: str
    external_transaction_id: str | None = None
    client_id: str
    client_name: str
    property_id: int
    property_external_id: str | None = None
    property_title: str | None = None
    agent_id: str
    agent_name: str
    transaction_type: str
    transaction_date: datetime
    amount: Decimal
    status: str
    notes: str | None = None
    source: str | None = None
    source_document_id: str | None = None
    sync_status: str | None = None
    created_at: datetime
    updated_at: datetime


class TransactionSummary(BaseModel):
    total: int
    reserved: int
    completed: int  # completed sales
    cancelled: int = 0
    amount_total: Decimal  # revenue from completed sales


class TransactionSyncResult(BaseModel):
    total: int
    inserted: int
    updated: int
    skipped_pending: int = 0
    errors: int
    error_messages: list[str] = []
    last_synced_at: datetime
