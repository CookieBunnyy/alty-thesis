"""Deals from inquiry to closing: stages, history, seller scope, and the link
to reservation and sale records."""

from app.models.agent import Agent
from app.models.property_listing import PropertyListing
from tests.conftest import login
from tests.test_cancellations import _reserve

API = "/api/v1"


def _seller(api, admin, db, agent_id, username):
    if db.get(Agent, agent_id) is None:
        db.add(Agent(agent_id=agent_id, full_name=f"Seller {agent_id}", status="ACTIVE", sync_status="SYNCED"))
        db.commit()
    assert api.post(f"{API}/users", headers=admin, json={"username": username, "full_name": username, "role": "Seller",
                                                         "password": "password123", "agent_id": agent_id}).status_code == 201
    return login(api, username)


def _listing(db):
    listing = PropertyListing(title="Lumina Homes Unit 7", status="AVAILABLE", sync_status="SYNCED", price_total=2_500_000)
    db.add(listing)
    db.commit()
    return listing.listing_id


def test_seller_records_inquiry_and_viewing_but_not_closing(api, admin, db):
    seller = _seller(api, admin, db, "AGT-61", "s61")
    other = _seller(api, admin, db, "AGT-62", "s62")
    listing_id = _listing(db)
    made = api.post(f"{API}/deals", headers=seller, json={
        "listing_id": listing_id, "agent_id": "AGT-62",           # ignored: a seller's deal is their own
        "buyer": {"full_name": "Grace Uy", "phone_number": "0917 000 1111"}})
    assert made.status_code == 201, made.text
    deal = made.json()
    assert deal["stage"] == "INQUIRY" and deal["agent_id"] == "AGT-61" and deal["buyer_name"] == "Grace Uy"
    path = f"{API}/deals/{deal['id']}"
    viewed = api.put(path, headers=seller, json={"viewing_type": "virtual", "viewing_at": "2026-11-12T10:00:00"})
    assert viewed.status_code == 200 and viewed.json()["stage"] == "VIEWING" and viewed.json()["viewing_type"] == "VIRTUAL"
    assert api.put(path, headers=seller, json={"developer_status": "SUBMITTED"}).status_code == 403
    assert api.post(f"{path}/stage", headers=seller, json={"stage": "RESERVED"}).status_code == 403
    # Other sellers can't see it; their list is empty.
    assert api.get(path, headers=other).status_code == 404
    assert api.get(f"{API}/deals", headers=other).json() == []
    assert [d["id"] for d in api.get(f"{API}/deals", headers=seller).json()] == [deal["id"]]
    # Lost needs a reason; history keeps every step.
    assert api.post(f"{path}/stage", headers=seller, json={"stage": "LOST"}).status_code == 422
    lost = api.post(f"{path}/stage", headers=seller, json={"stage": "LOST", "note": "Chose another developer"})
    assert lost.json()["stage"] == "LOST" and lost.json()["lost_reason"] == "Chose another developer"
    stages = [(e["from_stage"], e["to_stage"]) for e in lost.json()["events"] if e["to_stage"]]
    assert stages == [("INQUIRY", "VIEWING"), ("VIEWING", "LOST")]
    assert api.post(f"{path}/stage", headers=seller, json={"stage": "VIEWING"}).status_code == 409


def test_reservation_and_sale_records_move_the_deal(api, admin, agents, db):
    # A reservation recorded from a document creates (or advances) the deal.
    reservation = _reserve(api, admin, db)
    deals = api.get(f"{API}/deals", headers=admin).json()
    assert len(deals) == 1 and deals[0]["stage"] == "RESERVED"
    deal = deals[0]
    assert deal["reservation_transaction_id"] == reservation.transaction_id and deal["reservation_status"] == "RESERVED"
    path = f"{API}/deals/{deal['id']}"
    # Developer processing, then closing only when the sale is recorded.
    processing = api.put(path, headers=admin, json={"developer_status": "SUBMITTED"})
    assert processing.json()["stage"] == "DEVELOPER_PROCESSING"
    assert api.post(f"{path}/stage", headers=admin, json={"stage": "CLOSED"}).status_code == 409
    listing = db.get(PropertyListing, reservation.property_id)
    listing.price_total = 4_000_000
    db.commit()
    sold = api.post(f"{API}/transactions/{reservation.transaction_id}/complete-sale", headers=admin, json={})
    assert sold.status_code == 200, sold.text
    closed = api.get(path, headers=admin).json()
    assert closed["stage"] == "CLOSED" and closed["closing_date"] and closed["sale_transaction_id"]
    assert closed["reservation_status"] == "COMPLETED"


def test_cancelled_reservation_marks_the_deal_lost(api, admin, agents, db):
    reservation = _reserve(api, admin, db)
    api.post(f"{API}/transactions/{reservation.transaction_id}/cancel", headers=admin, json={"reason": "Loan denied"})
    deal = api.get(f"{API}/deals", headers=admin).json()[0]
    assert deal["stage"] == "LOST" and deal["lost_reason"] == "Loan denied" and deal["reservation_status"] == "CANCELLED"
    summary = api.get(f"{API}/deals/summary", headers=admin).json()
    assert summary["by_stage"]["LOST"] == 1


def test_payment_schedule_on_cost_estimate_off(api, admin, agents, db):
    reservation = _reserve(api, admin, db)
    assert api.get(f"{API}/transactions/features", headers=admin).json() == {"payment_schedule": True,
                                                                            "cost_estimate": False}
    # The payment schedule is on since the second interview; the tax and fee estimate is still off.
    assert api.get(f"{API}/transactions/{reservation.transaction_id}/payment-plan", headers=admin).status_code == 200
    assert api.get(f"{API}/transactions/{reservation.transaction_id}/cost-breakdown", headers=admin).status_code == 404
