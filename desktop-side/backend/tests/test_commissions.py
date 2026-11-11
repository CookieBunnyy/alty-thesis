"""Commission records (sale and rental), configurable structures, approval and
release, vouchers, and what sellers may see."""

from datetime import date, timedelta

from app.models.agent import Agent
from tests.conftest import login
from tests.test_cancellations import _reserve

API = "/api/v1"


def _sale(api, admin, db):
    reservation = _reserve(api, admin, db)
    from app.models.property_listing import PropertyListing

    listing = db.get(PropertyListing, reservation.property_id)
    listing.price_total = 4_000_000
    db.commit()
    sold = api.post(f"{API}/transactions/{reservation.transaction_id}/complete-sale", headers=admin, json={})
    assert sold.status_code == 200, sold.text
    return sold.json()


def test_usual_rate_and_structures_suggest(api, admin, agents, db):
    sale = _sale(api, admin, db)
    # No amount and no structure: the usual 5% of the TCP (second interview), editable.
    usual = api.post(f"{API}/commissions", headers=admin, json={"transaction_id": sale["transaction_id"]})
    assert usual.status_code == 201, usual.text
    assert usual.json()["rate_percent"] == 5 and usual.json()["amount"] == round(usual.json()["basis_amount"] * 0.05, 2)
    agreed_rate = api.post(f"{API}/commissions", headers=admin, json={"transaction_id": sale["transaction_id"],
                                                                      "rate_percent": "3"}).json()
    assert agreed_rate["amount"] == round(agreed_rate["basis_amount"] * 0.03, 2)
    # A rental without an amount is still refused (no rate is assumed for rentals).
    assert api.post(f"{API}/commissions", headers=admin, json={"kind": "RENTAL", "agent_id": agents[0],
                                                               "property_description": "Unit"}).status_code == 422
    structure = api.post(f"{API}/commissions/structures", headers=admin, json={
        "name": "Developer X sale terms", "basis": "PERCENT_OF_PRICE", "rate_percent": "4.5",
        "seller_share_percent": "60"}).json()
    preview = api.post(f"{API}/commissions/preview", headers=admin, json={"structure_id": structure["id"],
                                                                         "basis_amount": "4000000"}).json()
    assert preview == {"amount": 180000.0, "seller_share_amount": 108000.0, "rate_percent": 4.5}
    made = api.post(f"{API}/commissions", headers=admin, json={"transaction_id": sale["transaction_id"],
                                                               "structure_id": structure["id"]})
    assert made.status_code == 201, made.text
    record = made.json()
    assert record["amount"] == 180000 and record["basis_amount"] == 4_000_000
    assert record["agent_id"] == sale["agent_id"] and record["approval_status"] == "PENDING"
    # An agreed amount entered by management always wins over the structure.
    other = api.post(f"{API}/commissions", headers=admin, json={"transaction_id": sale["transaction_id"],
                                                                "structure_id": structure["id"], "amount": "150000"})
    assert other.json()["amount"] == 150000


def test_approval_release_and_voucher(api, admin, employee, agents, db):
    sale = _sale(api, admin, db)
    record = api.post(f"{API}/commissions", headers=admin, json={"transaction_id": sale["transaction_id"],
                                                                 "amount": "120000"}).json()
    path = f"{API}/commissions/{record['id']}"
    assert api.post(f"{path}/release", headers=admin, json={"released_on": str(date.today())}).status_code == 409
    assert api.post(f"{path}/approval", headers=employee, json={"decision": "APPROVED"}).status_code == 403
    assert api.post(f"{path}/approval", headers=admin, json={"decision": "REJECTED"}).status_code == 422
    approved = api.post(f"{path}/approval", headers=admin, json={"decision": "APPROVED"}).json()
    assert approved["approval_status"] == "APPROVED" and approved["approved_by"]
    future = str(date.today() + timedelta(days=3))
    assert api.post(f"{path}/release", headers=admin, json={"released_on": future}).status_code == 422
    assert api.post(f"{path}/release", headers=admin, json={"released_on": str(date.today()), "amount": "1",
                                                            "method": "PIGEON"}).status_code == 422
    part = api.post(f"{path}/release", headers=admin, json={"released_on": str(date.today()), "amount": "50000",
                                                            "method": "atm", "bank_name": "BDO"}).json()
    assert part["status"] == "PARTIALLY_RELEASED" and part["released_amount"] == 50000
    assert part["releases"][0]["method"] == "ATM" and part["releases"][0]["bank_name"] == "BDO"
    assert api.post(f"{path}/release", headers=admin, json={"released_on": str(date.today()),
                                                            "amount": "90000"}).status_code == 422
    rest = api.post(f"{path}/release", headers=admin, json={"released_on": str(date.today())}).json()
    assert rest["status"] == "RELEASED" and rest["released_amount"] == 120000   # the unpaid 70,000 released
    assert [r["amount"] for r in rest["releases"]] == [50000, 70000]                # paid in parts
    # The filing manager (legacy Employee) attaches vouchers but can't approve.
    assert api.put(f"{path}/voucher", headers=employee, json={"document_id": 99999}).status_code == 422
    summary = api.get(f"{API}/commissions/summary", headers=employee).json()
    assert summary["without_voucher"] == 1
    actions = {e["action"] for e in api.get(f"{API}/audit?entity_type=commission_records", headers=admin).json()["items"]}
    assert {"COMMISSION_RECORDED", "COMMISSION_APPROVED", "COMMISSION_RELEASED"} <= actions


def test_rental_commission_agreement(api, admin, agents, db):
    rental = api.post(f"{API}/commissions", headers=admin, json={
        "kind": "rental", "agent_id": agents[0], "property_description": "Studio unit, Tower 2, Pasig",
        "lessor_name": "Mr. Lim", "lessee_name": "Ana Reyes", "monthly_rent": "18000", "lease_term_months": 12,
        "amount": "18000", "agreement_reference": "LEASE-2026-07", "agreement_notes": "One month's rent, agreed "
                                                                                     "with the lessor"})
    assert rental.status_code == 201, rental.text
    body = rental.json()
    assert body["kind"] == "RENTAL" and body["lessor_name"] == "Mr. Lim" and body["amount"] == 18000
    assert api.post(f"{API}/commissions", headers=admin, json={"kind": "RENTAL", "amount": "1"}).status_code == 422


def test_sellers_see_their_own_commissions(api, admin, agents, db):
    sale = _sale(api, admin, db)
    api.post(f"{API}/commissions", headers=admin, json={"transaction_id": sale["transaction_id"], "amount": "99000"})
    api.post(f"{API}/users", headers=admin, json={"username": "seller1", "full_name": "S", "role": "Seller",
                                                  "password": "password123", "agent_id": sale["agent_id"]})
    other_agent = next(a for a in agents if a != sale["agent_id"])
    api.post(f"{API}/users", headers=admin, json={"username": "seller2", "full_name": "S2", "role": "Seller",
                                                  "password": "password123", "agent_id": other_agent})
    seller = login(api, "seller1")
    # Shared by default (second interview); management can turn it off per seller.
    assert api.get(f"{API}/commissions", headers=seller).status_code == 403
    api.put(f"{API}/agents/{sale['agent_id']}/assignment", headers=admin, json={"commission_visible": False})
    assert api.get(f"{API}/seller/commissions", headers=seller).status_code == 403
    api.put(f"{API}/agents/{sale['agent_id']}/assignment", headers=admin, json={"commission_visible": True})
    mine = api.get(f"{API}/seller/commissions", headers=seller)
    assert mine.status_code == 200 and [r["amount"] for r in mine.json()] == [99000]
    assert "agreement_notes" not in mine.json()[0]
    api.put(f"{API}/agents/{other_agent}/assignment", headers=admin, json={"commission_visible": True})
    assert api.get(f"{API}/seller/commissions", headers=login(api, "seller2")).json() == []
    assert db.get(Agent, sale["agent_id"]).commission_visible
