"""The agents API reports figures counted from recorded clients and
transactions, alongside (not instead of) the imported agent record."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from app.models.agent import Agent
from app.models.client import Client
from app.models.property_listing import PropertyListing
from app.models.transaction import PropertyTransaction


def _client(db, name, agent_id):
    client = Client(full_name=name, status="RESERVED", source="DOCUMENT", sync_status="SYNCED", agent_id=agent_id)
    db.add(client)
    db.flush()
    return client


def _tx(db, client, listing, agent_id, kind, status, amount):
    db.add(PropertyTransaction(client_id=client.client_id, property_id=listing.listing_id, agent_id=agent_id,
                               transaction_type=kind, status=status, amount=Decimal(amount), source="DOCUMENT",
                               transaction_date=datetime(2026, 9, 1, tzinfo=timezone.utc)))


def test_agents_report_recorded_activity(api, admin, db):
    # Imported demo figures that must not be shown as activity.
    db.add(Agent(agent_id="AGT-R", full_name="Recorded Agent", status="ACTIVE", sync_status="SYNCED",
                 transactions_count=16, completed_sales=11, total_sales=Decimal("62100000")))
    db.add(Agent(agent_id="AGT-Z", full_name="Quiet Agent", status="ACTIVE", sync_status="SYNCED"))
    listing = PropertyListing(title="Recorded House", status="SOLD", sync_status="SYNCED")
    db.add_all([listing, PropertyListing(title="Other", status="RESERVED", sync_status="SYNCED")])
    db.flush()
    other = db.query(PropertyListing).filter_by(title="Other").one()
    buyer = _client(db, "Buyer One", "AGT-R")
    _tx(db, buyer, listing, "AGT-R", "RESERVED", "COMPLETED", "50000")   # reservation that became ...
    _tx(db, buyer, listing, "AGT-R", "SOLD", "COMPLETED", "5000000")     # ... this sale
    second = _client(db, "Buyer Two", "AGT-R")
    _tx(db, second, other, "AGT-R", "RESERVED", "RESERVED", "50000")     # open reservation
    lost = _client(db, "Buyer Three", "AGT-R")
    _tx(db, lost, other, "AGT-R", "RESERVED", "CANCELLED", "50000")      # cancelled: not counted
    db.commit()

    agents = {a["agent_id"]: a for a in api.get("/api/v1/agents", headers=admin).json()}
    recorded = agents["AGT-R"]
    assert recorded["assigned_clients"] == 3
    assert recorded["recorded_transactions"] == 3
    assert recorded["open_reservations"] == 1
    assert recorded["recorded_completed_sales"] == 1
    assert recorded["recorded_sales_value"] == 5_000_000
    assert recorded["transactions_count"] == 16  # the imported record is unchanged
    quiet = agents["AGT-Z"]
    assert (quiet["recorded_transactions"], quiet["recorded_sales_value"], quiet["assigned_clients"]) == (0, 0, 0)
    single = api.get("/api/v1/agents/AGT-R", headers=admin).json()
    assert single["recorded_completed_sales"] == 1 and single["open_reservations"] == 1
