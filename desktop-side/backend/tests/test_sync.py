"""Pull-sync behaviour against a fake Supabase (no network)."""

from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from sqlalchemy import select

from app.core.config import settings
from app.models.client import Client
from app.models.property_listing import PropertyListing
from app.models.transaction import PropertyTransaction
from app.services import agent_sync, client_sync, property_listing_sync, transaction_sync


class FakeTable:
    def __init__(self, rows):
        self.rows = rows

    def select(self, *_args):
        return self

    def execute(self):
        return SimpleNamespace(data=self.rows)


class FakeSupabase:
    def __init__(self, tables):
        self.tables = tables

    def table(self, name):
        return FakeTable(self.tables.get(name, []))


def test_transaction_pull_matches_same_reservation_with_different_id(db, agents, monkeypatch):
    listing = PropertyListing(title="Luxury House", status="RESERVED", sync_status="SYNCED")
    db.add(listing)
    db.flush()
    client = Client(full_name="Andrea Villanueva", property_id=listing.listing_id, agent_id="AGT-0003",
                    transaction_type="RESERVED", status="RESERVED", sync_status="SYNCED")
    db.add(client)
    db.flush()
    local_id = str(uuid4())
    db.add(PropertyTransaction(transaction_id=local_id, client_id=client.client_id,
                               property_id=listing.listing_id, agent_id="AGT-0003",
                               transaction_type="RESERVED", status="RESERVED", amount=Decimal("8500000"),
                               transaction_date=datetime(2026, 8, 19, tzinfo=timezone.utc),
                               sync_status="SYNCED"))
    db.commit()
    cloud_row = {"transaction_id": str(uuid4()), "client_id": client.client_id,
                 "property_id": listing.listing_id, "agent_id": "AGT-0003", "transaction_type": "RESERVED",
                 "transaction_date": "2026-08-19T06:30:00+00:00", "amount": 8500000.0, "status": "RESERVED"}
    fake = FakeSupabase({"transactions": [cloud_row, dict(cloud_row, transaction_id=str(uuid4()))]})
    for module in (transaction_sync, client_sync, agent_sync, property_listing_sync):
        monkeypatch.setattr(module, "supabase", fake)
    monkeypatch.setattr(settings, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(settings, "SUPABASE_SERVICE_ROLE_KEY", "test")

    result = transaction_sync.sync_transactions(db)

    assert result["errors"] == 0 and result["inserted"] == 0 and result["updated"] == 2
    db.expire_all()
    rows = db.execute(select(PropertyTransaction)).scalars().all()
    assert [row.transaction_id for row in rows] == [local_id]  # no duplicate reservation
