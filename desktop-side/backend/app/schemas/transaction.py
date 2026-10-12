from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field


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
    cancellation_reason: str | None = None
    cancelled_at: datetime | None = None
    cancelled_by: str | None = None
    source: str | None = None
    source_document_id: str | None = None
    sync_status: str | None = None
    created_at: datetime
    updated_at: datetime


class TransactionCancel(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)


class PaymentCreate(BaseModel):
    amount: Decimal = Field(gt=0, le=10_000_000_000, max_digits=14, decimal_places=2)
    paid_at: date
    note: str | None = Field(default=None, max_length=300)


class SaleCompletion(BaseModel):
    """Turn an open reservation into a completed sale."""
    amount: Decimal | None = Field(default=None, gt=0, le=10_000_000_000, max_digits=14, decimal_places=2)
    sale_date: date | None = None
    note: str | None = Field(default=None, max_length=1000)


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
