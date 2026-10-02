"""Website client accounts, access separation, agent reviews and the home page."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select

from app.api.v1 import client_portal
from app.models.agent import Agent
from app.models.client import Client
from app.models.property_listing import PropertyListing
from app.models.review import AgentReview
from app.models.transaction import PropertyTransaction
from app.models.user import User
from tests import documents as build
from tests.conftest import login
from tests.test_document_pipeline import assert_success, upload


def _register(api, name="Ana Reyes", email="ana.reyes@example.com", phone="0917 111 2222"):
    client_portal.auth_limiter._hits.clear()
    response = api.post("/api/v1/client/register", json={
        "full_name": name, "email": email, "phone_number": phone, "location": "Makati",
        "password": "s3cret-pass"})
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _listing(db, title="Garden Home", price="3500000", photos=None):
    listing = PropertyListing(title=title, category="House", price_total=Decimal(price), status="AVAILABLE",
                              village_name="Village", photos=photos)
    db.add(listing)
    db.commit()
    return listing


def _record_transaction(db, email, listing_id, transaction_type="SOLD", agent_id="AGT-0003"):
    """What the document pipeline stores for this client's agent-submitted
    document (see test_agent_documents_reach_the_client_account)."""
    user = db.execute(select(User).where(User.username == email)).scalar_one()
    status = "COMPLETED" if transaction_type == "SOLD" else "RESERVED"
    transaction = PropertyTransaction(client_id=user.client_id, property_id=listing_id, agent_id=agent_id,
                                      transaction_type=transaction_type, status=status,
                                      transaction_date=datetime.now(timezone.utc), amount=Decimal("3500000"),
                                      source="DOCUMENT")
    db.add(transaction)
    db.commit()
    return transaction


def test_register_creates_linked_client_and_hashes_password(api, db):
    _register(api)
    user = db.execute(select(User).where(User.username == "ana.reyes@example.com")).scalar_one()
    client = db.get(Client, user.client_id)
    assert user.role == "Client" and client.full_name == "Ana Reyes" and client.source == "WEBSITE"
    assert user.password_hash != "s3cret-pass" and user.password_hash.startswith("$2")
    # duplicate email, weak password, invalid email
    assert api.post("/api/v1/client/register", json={
        "full_name": "Ana R", "email": "ANA.REYES@example.com", "phone_number": "0917 000 0000",
        "password": "s3cret-pass"}).status_code == 409
    assert api.post("/api/v1/client/register", json={
        "full_name": "Bo", "email": "bo@example.com", "phone_number": "0917 000 0001",
        "password": "short"}).status_code == 422
    assert api.post("/api/v1/client/register", json={
        "full_name": "Bo", "email": "not-an-email", "phone_number": "0917 000 0001",
        "password": "long-enough"}).status_code == 422


def test_existing_client_records_are_not_auto_linked(api, db):
    db.add(Client(full_name="Carla Diaz", email="carla@example.com", phone_number="0919 555 1234",
                  status="PROSPECT", source="DOCUMENT"))
    db.commit()
    response = api.post("/api/v1/client/register", json={
        "full_name": "Carla Diaz", "email": "carla@example.com", "phone_number": "0920 000 0000",
        "password": "s3cret-pass"})
    assert response.status_code == 409 and "contact your agent" in response.json()["detail"]


def test_client_and_staff_accounts_are_separated(api, admin, agents):
    ana = _register(api)
    # A client token opens no internal endpoint...
    for path in ("/api/v1/agents", "/api/v1/clients", "/api/v1/transactions", "/api/v1/auth/me"):
        assert api.get(path, headers=ana).status_code == 403, path
    # ...cannot sign in to the desktop...
    response = api.post("/api/v1/auth/login", data={"username": "ana.reyes@example.com",
                                                    "password": "s3cret-pass"})
    assert response.status_code == 403
    # ...and staff cannot use the client portal.
    assert api.get("/api/v1/client/me", headers=admin).status_code == 403
    assert api.post("/api/v1/client/login", json={"email": "admin", "password": "password123"}).status_code == 403
    # Client accounts are not listed among staff users.
    assert all(user["role"] != "Client" for user in api.get("/api/v1/users", headers=admin).json())
    # Sign in works with any letter case and returns the profile.
    session = api.post("/api/v1/client/login", json={"email": "Ana.Reyes@Example.com", "password": "s3cret-pass"})
    assert session.status_code == 200 and session.json()["client"]["full_name"] == "Ana Reyes"
    assert api.post("/api/v1/client/login", json={"email": "ana.reyes@example.com",
                                                  "password": "wrong"}).status_code == 401


def test_reviews_only_for_own_completed_transactions(api, admin, agents, db):
    listing = _listing(db)
    ana, ben = _register(api), _register(api, "Ben Cruz", "ben@example.com", "0918 222 3333")
    sale = _record_transaction(db, "ana.reyes@example.com", listing.listing_id)
    assert sale.status == "COMPLETED"
    review = {"transaction_id": sale.transaction_id, "rating": 5, "review": "  Very helpful throughout.  "}

    assert api.post("/api/v1/client/reviews", json=review).status_code == 401           # anonymous
    assert api.post("/api/v1/client/reviews", json=review, headers=ben).status_code == 404  # not Ben's
    assert api.post("/api/v1/client/reviews", json={**review, "rating": 6}, headers=ana).status_code == 422
    assert api.post("/api/v1/client/reviews", json={**review, "review": "x" * 1001},
                    headers=ana).status_code == 422
    assert api.post("/api/v1/client/reviews", json={**review, "agent_id": "AGT-0005"},
                    headers=ana).status_code == 422  # agent comes from the transaction, not the client
    created = api.post("/api/v1/client/reviews", json=review, headers=ana)
    assert created.status_code == 201, created.text
    assert created.json()["agent"]["agent_id"] == "AGT-0003" and created.json()["review"] == "Very helpful throughout."
    assert api.post("/api/v1/client/reviews", json=review, headers=ana).status_code == 409  # once per transaction

    review_id = created.json()["id"]
    assert api.put(f"/api/v1/client/reviews/{review_id}", json={"rating": 4}, headers=ben).status_code == 404
    edited = api.put(f"/api/v1/client/reviews/{review_id}", json={"rating": 4, "review": "Good."}, headers=ana)
    assert edited.status_code == 200 and edited.json()["rating"] == 4
    assert db.scalar(select(AgentReview.id).where(AgentReview.client_id.is_not(None))) == review_id
    mine = api.get("/api/v1/client/transactions", headers=ana).json()
    assert mine[0]["review"]["rating"] == 4 and mine[0]["can_review"] is False


def test_reservation_is_not_reviewable_until_completed(api, agents, db):
    listing = _listing(db)
    ana = _register(api)
    transaction_id = _record_transaction(db, "ana.reyes@example.com", listing.listing_id, "RESERVED").transaction_id
    assert api.get("/api/v1/client/transactions", headers=ana).json()[0]["can_review"] is False
    rejected = api.post("/api/v1/client/reviews", headers=ana,
                        json={"transaction_id": transaction_id, "rating": 5})
    assert rejected.status_code == 409 and "completed" in rejected.json()["detail"]


def test_ratings_are_aggregated_from_reviews_everywhere(api, admin, agents, db):
    db.get(Agent, "AGT-0003").star_rating = Decimal("4.1")  # legacy/system rating stays separate
    db.commit()
    for index, (stars, text) in enumerate(((5, "Excellent assistance."), (3, None))):
        session = _register(api, f"Client {index} Tester", f"c{index}@example.com", f"0917 000 100{index}")
        listing = _listing(db, title=f"Home {index}")
        sale = _record_transaction(db, f"c{index}@example.com", listing.listing_id)
        api.post("/api/v1/client/reviews", headers=session,
                 json={"transaction_id": sale.transaction_id, "rating": stars, "review": text})

    desktop = {a["agent_id"]: a for a in api.get("/api/v1/agents", headers=admin).json()}["AGT-0003"]
    assert desktop["client_rating"] == 4.0 and desktop["review_count"] == 2
    assert float(desktop["star_rating"]) == 4.1
    detail = api.get("/api/v1/agents/AGT-0003/reviews", headers=admin).json()
    assert detail["distribution"] == {"5": 1, "4": 0, "3": 1, "2": 0, "1": 0}

    public = api.get("/api/v1/public/agents/AGT-0003").json()
    assert public["client_rating"] == 4.0 and public["review_count"] == 2
    first = public["reviews"][0]
    assert first["reviewer"] in {"Client T.", "Client 1 T."} or first["reviewer"].endswith("T.")
    for leaked in ("email", "phone_number", "client_id", "location"):
        assert leaked not in first
    assert {a["agent_id"]: a for a in api.get("/api/v1/public/agents").json()}["AGT-0003"]["review_count"] == 2

    home = api.get("/api/v1/public/home").json()
    assert home["stats"]["client_reviews"] == {"average": 4.0, "count": 2}
    assert home["reviews"][0]["review"] == "Excellent assistance."  # reviews with text first
    assert home["agents"][0]["agent_id"] == "AGT-0003"               # most reviewed first


def test_home_page_uses_live_data_only(api, agents, db):
    empty = api.get("/api/v1/public/home").json()
    assert empty["featured_properties"] == [] and empty["reviews"] == []
    assert empty["stats"]["client_reviews"] == {"average": None, "count": 0}
    for index in range(8):
        _listing(db, title=f"Listing {index}", photos=["https://example.com/p.jpg"] if index == 2 else None)
    db.add(PropertyListing(title="Sold one", price_total=Decimal("1"), status="SOLD"))
    db.commit()
    home = api.get("/api/v1/public/home").json()
    assert len(home["featured_properties"]) == 6                    # capped, not the whole table
    assert home["featured_properties"][0]["title"] == "Listing 2"   # photos first
    assert all(p["status"] == "AVAILABLE" for p in home["featured_properties"])
    assert home["stats"]["available_properties"] == 8
    assert home["categories"] == [{"category": "House", "count": 8}]
    assert {a["agent_id"] for a in home["agents"]} <= {"AGT-0003", "AGT-0005", "AGT-0006", "AGT-0007"}


def test_staff_login_still_works(api, admin):
    assert api.get("/api/v1/auth/me", headers=admin).json()["role"] == "Administrator"
    assert login(api, "admin")


def test_agent_documents_reach_the_client_account(api, admin, agents, db):
    """The real flow: the client contacts an agent; the filing manager uploads
    the agent's reservation and sale documents; the transactions appear in
    the client's account (matched by email) and the agent can then be rated."""
    michael = _register(api, "Michael Santos", "michael.santos.test@example.com", "0917 222 3333")
    assert api.get("/api/v1/client/transactions", headers=michael).json() == []

    without_client_id = lambda lines: [line for line in lines if not line.startswith("Client ID:")]  # noqa: E731
    assert_success(upload(api, admin, "property.docx", build.docx(build.PROPERTY_LINES)))
    assert_success(upload(api, admin, "reservation.docx", build.docx(without_client_id(build.RESERVATION_LINES))))
    mine = api.get("/api/v1/client/transactions", headers=michael).json()
    assert [(t["transaction_type"], t["status"], t["can_review"]) for t in mine] == [("RESERVED", "RESERVED", False)]
    assert mine[0]["agent"]["agent_id"] == "AGT-0006"

    sale_lines = without_client_id(build.SALE_LINES) + ["Email: michael.santos.test@example.com"]
    assert_success(upload(api, admin, "sale.docx", build.docx(sale_lines)))
    mine = {t["transaction_type"]: t for t in api.get("/api/v1/client/transactions", headers=michael).json()}
    assert mine["SOLD"]["status"] == "COMPLETED" and mine["SOLD"]["can_review"] is True
    review = api.post("/api/v1/client/reviews", headers=michael, json={
        "transaction_id": mine["SOLD"]["transaction_id"], "rating": 5, "review": "Smooth from viewing to signing."})
    assert review.status_code == 201, review.text
    assert review.json()["agent"]["agent_id"] == "AGT-0006"
    assert db.scalar(select(func.count()).select_from(Client)) == 1  # the account's record, no duplicate
