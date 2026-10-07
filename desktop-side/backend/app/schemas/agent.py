from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class AgentResponse(BaseModel):
    agent_id: str
    full_name: str
    phone_number: str | None = None
    agent_location: str | None = None
    latitude: Decimal | None = Field(default=None, ge=-90, le=90)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180)
    star_rating: Decimal | None = Field(default=None, ge=0, le=5)
    assignments_count: int = 0
    transactions_count: int = 0
    completed_sales: int = 0
    total_sales: Decimal = Decimal("0")
    total_commission: Decimal = Decimal("0")
    performance_score: Decimal = Decimal("0")
    # From client reviews (agent_reviews); star_rating above is the
    # system/legacy rating synced from Supabase.
    client_rating: float | None = None
    review_count: int = 0
    # Counted from the clients and transactions recorded in ALTY (what the
    # pages show). The stored counts above come from the Supabase import.
    assigned_clients: int = 0
    recorded_transactions: int = 0
    open_reservations: int = 0
    recorded_completed_sales: int = 0
    recorded_sales_value: float = 0
    status: str
    sync_status: str
    last_synced_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AgentSyncResult(BaseModel):
    total: int
    inserted: int
    updated: int
    errors: int
    last_synced_at: datetime