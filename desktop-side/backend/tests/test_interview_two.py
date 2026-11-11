"""Second interview with Abellar Realty: accreditation scope and yearly
renewal, the steps after a reservation, equity terms and loan takeout in the
payment schedule, listing computation details, contacts, quarterly reports."""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.core.config import settings
from app.models.listing_assignment import ListingAssignment
from app.models.property_listing import PropertyListing
from app.models.transaction import PropertyTransaction
from app.services.payment_plan import add_months, build_plan
from tests.conftest import login
from tests.test_accreditation import _developer, _listing
from tests.test_cancellations import _reserve

API = "/api/v1"


@pytest.fixture
def required(monkeypatch):
    monkeypatch.setattr(settings, "ACCREDITATION_REQUIRED", True)


# ---- accreditation ------------------------------------------------------------------

def test_project_specific_accreditation_and_yearly_renewal(api, admin, db, required):
    today = date.today()
    # A scope with nothing named is refused.
    assert api.post(f"{API}/partners", headers=admin, json={
        "name": "X Land", "partner_type": "DEVELOPER", "accreditation_scope": "SPECIFIC_PROJECTS"}).status_code == 422
    developer = _developer(api, admin, accreditation_status="VERIFIED", accreditation_valid_from=str(today),
                           accreditation_scope="specific_projects",
                           accreditation_projects=["Lumina Imus", " lumina  imus ", "Bella Vista"])
    # Verified without an end date: valid for a year.
    assert developer["accreditation_valid_until"] == add_months(today, 12).isoformat()
    assert developer["accreditation_projects"] == ["Lumina Imus", "Bella Vista"]

    covered = _listing(db, project_name="LUMINA IMUS", partner_id=developer["id"])
    other = _listing(db, title="Elsewhere", project_name="Lumina Baliwag", partner_id=developer["id"])
    assert api.post(f"{API}/property-listings/{covered}/marketing", headers=admin,
                    json={"action": "approve"}).status_code == 200
    refused = api.post(f"{API}/property-listings/{other}/marketing", headers=admin, json={"action": "approve"})
    assert refused.status_code == 409 and "specific projects" in refused.text
    assert [p["listing_id"] for p in api.get(f"{API}/public/properties").json()] == [covered]

    # Widening the scope to every project makes the other one approvable.
    api.put(f"{API}/partners/{developer['id']}", headers=admin, json={"accreditation_scope": "ALL_PROJECTS"})
    assert api.post(f"{API}/property-listings/{other}/marketing", headers=admin,
                    json={"action": "approve"}).status_code == 200

    # Expired: renewal gives a new year from today.
    api.put(f"{API}/partners/{developer['id']}", headers=admin, json={
        "accreditation_valid_from": str(today - timedelta(days=400)),
        "accreditation_valid_until": str(today - timedelta(days=35))})
    assert api.get(f"{API}/public/properties").json() == []
    renewed = api.post(f"{API}/partners/{developer['id']}/accreditation/renew", headers=admin)
    assert renewed.status_code == 200, renewed.text
    assert renewed.json()["accreditation_valid_from"] == today.isoformat()
    assert renewed.json()["accreditation_valid_until"] == add_months(today, 12).isoformat()
    assert len(api.get(f"{API}/public/properties").json()) == 2


# ---- after the reservation ------------------------------------------------------------

def _deal_of(api, admin, reservation):
    deals = api.get(f"{API}/deals", headers=admin).json()
    return next(d for d in deals if d["reservation_transaction_id"] == reservation.transaction_id)


def test_steps_after_reservation_and_loan_payment_schedule(api, admin, employee, agents, db):
    reservation = _reserve(api, admin, db)
    listing = db.get(PropertyListing, reservation.property_id)
    listing.price_total, listing.initial_dp = Decimal(3_000_000), Decimal(300_000)
    db.commit()
    deal = _deal_of(api, admin, reservation)
    assert [m["key"] for m in deal["milestones"]][:4] == ["DOC_RESERVATION_AGREEMENT", "DOC_BUYER_INFO_SHEET",
                                                          "DOC_VALID_IDS", "DOC_PROOF_OF_INCOME"]
    path = f"{API}/deals/{deal['id']}"
    # Financing and equity terms: a Pag-IBIG buyer paying the equity over 12 months.
    assert api.put(path, headers=admin, json={"financing_type": "GCASH"}).status_code == 422
    saved = api.put(path, headers=admin, json={"financing_type": "Pag-IBIG", "equity_terms_months": 12})
    assert saved.status_code == 200 and saved.json()["financing_type"] == "PAGIBIG"

    plan = api.get(f"{API}/transactions/{reservation.transaction_id}/payment-plan", headers=admin).json()
    items = plan["plan"]["items"]
    equity = [i for i in items if i["kind"] == "EQUITY"]
    fee = Decimal(str(reservation.amount))
    assert len(equity) == 12 and sum(Decimal(str(i["amount"])) for i in equity) == Decimal(300_000) - fee
    takeout = items[-1]
    assert takeout["kind"] == "LOAN_TAKEOUT" and "Pag-IBIG" in takeout["label"]
    assert Decimal(str(takeout["amount"])) == Decimal(2_700_000)
    assert plan["deal_id"] == deal["id"]

    # The filing manager ticks the documents; the deal moves to developer processing.
    step = f"{path}/milestones"
    ticked = api.put(step, headers=employee, json={"key": "DOC_RESERVATION_AGREEMENT"})
    assert ticked.status_code == 200, ticked.text
    assert ticked.json()["stage"] == "DEVELOPER_PROCESSING"
    assert ticked.json()["milestones"][0]["done_on"] == date.today().isoformat()
    assert api.put(step, headers=admin, json={"key": "NOPE"}).status_code == 422
    future = str(date.today() + timedelta(days=2))
    assert api.put(step, headers=admin, json={"key": "EQUITY_PAID", "done_on": future}).status_code == 422
    api.put(step, headers=admin, json={"key": "LOAN_APPROVED", "note": "LOG released by Pag-IBIG"})
    undone = api.put(step, headers=admin, json={"key": "LOAN_APPROVED", "done": False}).json()
    assert next(m for m in undone["milestones"] if m["key"] == "LOAN_APPROVED")["done_on"] is None

    # Cash buyers have no loan steps.
    api.put(path, headers=admin, json={"financing_type": "CASH"})
    body = api.get(path, headers=admin).json()
    assert not next(m for m in body["milestones"] if m["key"] == "LOAN_APPLIED")["applies"]
    assert api.put(step, headers=admin, json={"key": "LOAN_APPLIED"}).status_code == 409

    # The seller sees the steps but can't tick them.
    api.post(f"{API}/users", headers=admin, json={"username": "seller1", "full_name": "S", "role": "Seller",
                                                  "password": "password123", "agent_id": deal["agent_id"]})
    seller = login(api, "seller1")
    mine = api.get(path, headers=seller)
    assert mine.status_code == 200 and mine.json()["milestones"][0]["done_on"]
    assert api.put(step, headers=seller, json={"key": "TURNOVER"}).status_code == 403


def test_in_house_schedule_stays_monthly(api, admin, agents, db):
    reservation = _reserve(api, admin, db)
    listing = db.get(PropertyListing, reservation.property_id)
    listing.price_total, listing.initial_dp, listing.monthly_rate = Decimal(1_000_000), Decimal(100_000), Decimal(50_000)
    listing.equity_terms_months = 6
    db.commit()
    db.expire_all()
    reservation = db.get(PropertyTransaction, reservation.transaction_id)
    plan = build_plan(reservation, [], financing_type="IN_HOUSE")
    kinds = [i["kind"] for i in plan["items"]]
    assert kinds.count("EQUITY") == 6 and kinds.count("MONTHLY") == 18      # 900,000 / 50,000
    assert plan["equity_terms_months"] == 6


# ---- listing details and contacts ---------------------------------------------------------

def test_listing_details_sample_computation_and_contacts(api, admin, agents, db):
    developer = _developer(api, admin, accreditation_status="VERIFIED")
    listing_id = _listing(db, project_name="Bella Vista", partner_id=developer["id"])
    path = f"{API}/property-listings/{listing_id}"
    assert api.put(path, headers=admin, json={"property_status": "sold out"}).status_code == 422
    assert api.put(path, headers=admin, json={"financing_options": ["bitcoin"]}).status_code == 422
    saved = api.put(path, headers=admin, json={
        "property_status": "Pre-selling", "financing_options": ["bank", "Pag-IBIG", "in-house"],
        "initial_dp": "450000", "reservation_fee": "20000", "equity_terms_months": 24, "monthly_rate": "18500",
        "lat": "14.40", "lng": "120.94"})
    assert saved.status_code == 200, saved.text
    assert saved.json()["property_status"] == "PRE_SELLING"
    assert saved.json()["financing_options"] == ["BANK", "PAGIBIG", "IN_HOUSE"]
    api.post(f"{path}/marketing", headers=admin, json={"action": "approve"})

    public = api.get(f"{API}/public/properties/{listing_id}").json()
    assert public["developer"] == "Camella Homes" and public["property_status"] == "PRE_SELLING"
    assert public["sample_computation"] == {
        "tcp": 3_000_000.0, "reservation_fee": 20_000.0, "down_payment": 450_000.0, "net_equity": 430_000.0,
        "equity_terms_months": 24, "monthly_equity": 17_916.67, "amount_to_finance": 2_550_000.0,
        "monthly_amortization": 18_500.0, "note": public["sample_computation"]["note"]}

    # The seller assigned to market it is listed first among the contacts.
    far = agents[-1]
    db.add(ListingAssignment(listing_id=listing_id, agent_id=far, assigned_by="test"))
    db.commit()
    contacts = api.get(f"{API}/public/properties/{listing_id}/nearby-agents?limit=1").json()["agents"]
    assert contacts[0]["agent_id"] == far and contacts[0]["assigned"]


# ---- reports -------------------------------------------------------------------------------

def test_quarterly_report_and_dashboard_top_sellers(api, admin, agents, db):
    from tests.test_commissions import _sale

    _sale(api, admin, db)
    today = date.today()
    body = api.get(f"{API}/reports/sales?start={today.year}-01-01&end={today}&period=quarter", headers=admin).json()
    assert body["by_period"] and all("-Q" in p["name"] or "-Q" in str(p.get("period", "")) for p in body["by_period"])
    dash = api.get(f"{API}/reports/dashboard", headers=admin).json()["sales"]
    assert dash["top_sellers_month"] and dash["top_sellers_quarter"]
    assert dash["top_sellers_month"][0]["revenue"] > 0
