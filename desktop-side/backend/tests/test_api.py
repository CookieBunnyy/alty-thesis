"""API behaviour: auth/roles, website flow, lifecycle, analytics, users, media."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import cv2
import numpy as np
from sqlalchemy import select

from app.models.client import Client
from app.models.property_listing import PropertyListing
from app.models.transaction import PropertyTransaction
from tests import documents as build
from tests.conftest import _make_user, login
from tests.test_document_pipeline import assert_success, upload


def _listing(db, **values) -> PropertyListing:
    listing = PropertyListing(sync_status="SYNCED", status=values.pop("status", "AVAILABLE"), **values)
    db.add(listing)
    db.commit()
    return listing


# ---- authentication & authorization --------------------------------------------

def test_protected_endpoints_require_authentication(api):
    for path in ("/api/v1/property-listings", "/api/v1/clients", "/api/v1/transactions",
                 "/api/v1/dashboard/summary", "/api/v1/documents", "/api/v1/audit"):
        assert api.get(path).status_code == 401, path
    assert api.post("/api/v1/property-listings/sync").status_code == 401


def test_me_returns_real_role_and_permissions(api, employee):
    me = api.get("/api/v1/auth/me", headers=employee).json()
    assert me["role"] == "Employee"
    assert "users" not in me["permissions"] and "documents" in me["permissions"]


def test_role_restrictions(api, admin, employee):
    assert api.get("/api/v1/users", headers=employee).status_code == 403
    assert api.get("/api/v1/audit", headers=employee).status_code == 403
    assert api.post("/api/v1/system/sync/push", headers=employee).status_code == 403
    assert api.get("/api/v1/users", headers=admin).status_code == 200


def test_audit_and_system_settings_are_administrator_only(api, admin, employee):
    _make_user("gm", "General Manager")
    _make_user("pres", "President")
    for username in ("gm", "pres"):
        headers = login(api, username)
        me = api.get("/api/v1/auth/me", headers=headers).json()
        assert "audit" not in me["permissions"] and "settings" in me["permissions"]
        assert api.get("/api/v1/audit", headers=headers).status_code == 403
        assert api.get("/api/v1/system/settings", headers=headers).status_code == 403
        assert api.post("/api/v1/system/sync/push", headers=headers).status_code == 403
    assert api.get("/api/v1/system/settings", headers=employee).status_code == 403
    # Everyone still sees the sync status shown in the header.
    assert api.get("/api/v1/system/sync", headers=employee).status_code == 200
    me = api.get("/api/v1/auth/me", headers=admin).json()
    assert "audit" in me["permissions"]
    assert api.get("/api/v1/audit", headers=admin).status_code == 200
    assert api.get("/api/v1/system/settings", headers=admin).status_code == 200


def test_failed_login_is_audited_and_register_is_least_privilege(api, admin):
    assert api.post("/api/v1/auth/login", data={"username": "admin", "password": "wrong"}).status_code == 401
    response = api.post("/api/v1/auth/register",
                        json={"username": "newbie", "password": "longpassword", "full_name": "New Person"})
    assert response.status_code == 201 and response.json()["user"]["role"] == "Employee"
    actions = [item["action"] for item in api.get("/api/v1/audit", headers=admin).json()["items"]]
    assert "LOGIN_FAILED" in actions and "LOGIN" in actions and "USER_REGISTERED" in actions


def test_user_management_and_last_admin_protection(api, admin):
    created = api.post("/api/v1/users", headers=admin, json={
        "username": "filing", "full_name": "Filing Manager", "password": "password123",
        "role": "filing manager"})
    assert created.status_code == 201 and created.json()["role"] == "Filing Manager"
    user_id = created.json()["id"]
    assert api.put(f"/api/v1/users/{user_id}", headers=admin, json={"is_active": False}).json()["is_active"] is False
    login = api.post("/api/v1/auth/login", data={"username": "filing", "password": "password123"})
    assert login.status_code == 403
    me = api.get("/api/v1/auth/me", headers=admin).json()
    demote = api.put(f"/api/v1/users/{me['id']}", headers=admin, json={"role": "Employee"})
    assert demote.status_code == 409
    assert api.post("/api/v1/users", headers=admin, json={
        "username": "x1", "full_name": "X", "password": "password123", "role": "Wizard"}).status_code == 422


# ---- website transaction flow ------------------------------------------------------

def test_website_cannot_create_transactions(api, agents, db):
    """Reservations and purchases come only from agents' documents: the
    public website can browse but has no way to record a transaction."""
    listing = _listing(db, title="Garden Home", price_total=Decimal("3500000"), lat=14.5, lng=121.0)
    properties = api.get("/api/v1/public/properties").json()
    assert [p["listing_id"] for p in properties] == [listing.listing_id]
    assert "sync_status" not in properties[0]
    assert "AGT-0003" in [a["agent_id"] for a in api.get("/api/v1/public/agents").json()]

    signup = api.post("/api/v1/client/register", json={
        "full_name": "Ana Reyes", "email": "ana.reyes@example.com", "phone_number": "0917 111 2222",
        "password": "s3cret-pass"})
    ana = {"Authorization": f"Bearer {signup.json()['access_token']}"}
    payload = {"property_id": listing.listing_id, "agent_id": "AGT-0003", "transaction_type": "RESERVED"}
    assert api.post("/api/v1/public/transactions", json=payload).status_code in {404, 405}
    assert api.post("/api/v1/client/transactions", json=payload, headers=ana).status_code in {404, 405}
    db.expire_all()
    assert db.execute(select(PropertyTransaction)).first() is None
    assert db.get(PropertyListing, listing.listing_id).status == "AVAILABLE"


# ---- property lifecycle via management edits ---------------------------------------

def test_manual_status_edits_respect_lifecycle(api, admin, agents, db):
    upload(api, admin, "property.docx", build.docx(build.PROPERTY_LINES))
    upload(api, admin, "reservation.docx", build.docx(build.RESERVATION_LINES))
    listing = db.execute(select(PropertyListing)).scalar_one()
    path = f"/api/v1/property-listings/{listing.listing_id}"
    assert api.put(path, headers=admin, json={"status": "SOLD"}).status_code == 409
    response = api.put(path, headers=admin, json={"status": "AVAILABLE"})
    assert response.status_code == 200 and response.json()["status"] == "AVAILABLE"
    db.expire_all()
    assert db.execute(select(PropertyTransaction)).scalar_one().status == "CANCELLED"
    history = api.get(f"{path}/history", headers=admin).json()
    assert history["transactions"][0]["status"] == "CANCELLED" and len(history["documents"]) == 2


# ---- dashboard, analytics, forecasting, DSS -----------------------------------------

def test_dashboard_reflects_real_records(api, admin, agents):
    empty = api.get("/api/v1/dashboard/summary", headers=admin).json()
    assert empty["total_properties"] == 0 and empty["completed_revenue"] == 0
    upload(api, admin, "property.docx", build.docx(build.PROPERTY_LINES))
    upload(api, admin, "reservation.docx", build.docx(build.RESERVATION_LINES))
    upload(api, admin, "bad.docx", build.docx(["RESERVATION AGREEMENT", "Buyer Name: Nobody"]))
    summary = api.get("/api/v1/dashboard/summary", headers=admin).json()
    assert summary["total_properties"] == 1 and summary["reserved_properties"] == 1
    assert summary["total_clients"] == 1 and summary["total_transactions"] == 1
    assert summary["failed_documents"] == 1 and summary["successful_documents"] == 2
    assert summary["completed_revenue"] == 0  # a reservation is not revenue


def test_forecast_reports_insufficient_history(api, admin):
    result = api.get("/api/v1/analytics/forecast", headers=admin).json()
    assert result["status"] == "insufficient_data"
    assert result["message"] == "Insufficient historical data for forecasting."
    assert result["forecast"] == []


def test_forecast_estimates_with_enough_history(api, admin, agents, db):
    now = datetime.now(timezone.utc)
    client = Client(full_name="History Buyer", status="SOLD", sync_status="SYNCED")
    db.add(client)
    db.flush()
    for months_ago in range(1, 9):
        listing = _listing(db, title=f"H{months_ago}", status="SOLD")
        db.add(PropertyTransaction(
            client_id=client.client_id, property_id=listing.listing_id, agent_id="AGT-0003",
            transaction_type="SOLD", status="COMPLETED",
            # One sale on the 15th of each of the previous 8 months (calendar-safe).
            transaction_date=datetime((now.year * 12 + now.month - 1 - months_ago) // 12,
                                      (now.month - 1 - months_ago) % 12 + 1, 15, tzinfo=timezone.utc),
            amount=Decimal(1_000_000 + 100_000 * (9 - months_ago)), sync_status="SYNCED"))
    db.commit()
    result = api.get("/api/v1/analytics/forecast", headers=admin).json()
    assert result["status"] == "estimated" and result["observations"] >= 6
    assert len(result["forecast"]) == 3 and result["slope_per_month"] > 0


def test_dss_distinguishes_data_analysis_recommendation(api, admin, agents):
    upload(api, admin, "reservation.docx", build.docx(build.RESERVATION_LINES))  # fails: no property
    items = api.get("/api/v1/analytics/dss", headers=admin).json()["items"]
    kinds = {item["kind"] for item in items}
    assert kinds <= {"DATA", "ANALYSIS", "RECOMMENDATION"} and {"DATA", "ANALYSIS"} <= kinds
    recommendation = next(i for i in items if i["title"] == "Resolve unmatched document references")
    assert recommendation["kind"] == "RECOMMENDATION" and recommendation["rule"]


def test_workforce_and_settings_do_not_expose_secrets(api, admin, agents):
    workforce = api.get("/api/v1/analytics/workforce", headers=admin).json()
    assert workforce["users"]["total"] == 1 and workforce["agents"]["total"] == 4
    settings = api.get("/api/v1/system/settings", headers=admin).json()
    text = str(settings)
    assert "test-secret-key" not in text and "password" not in text.lower()
    assert settings["storage"]["backend"] == "local"
    assert settings["processing"]["ocr"]["available"] is True


# ---- media quality analysis ----------------------------------------------------------

def _image(sharp: bool) -> bytes:
    rng = np.random.default_rng(7)
    image = (rng.random((900, 1400, 3)) * 255).astype(np.uint8)
    cv2.rectangle(image, (200, 200), (1200, 700), (255, 255, 255), 12)
    if not sharp:
        image = cv2.GaussianBlur(image, (51, 51), 25)
    return cv2.imencode(".jpg", image)[1].tobytes()


def test_media_quality_analysis(api, admin, db):
    listing = _listing(db, title="Photo Home", price_total=Decimal("1"))
    path = f"/api/v1/media/properties/{listing.listing_id}"
    sharp = api.post(path, headers=admin, files={"file": ("sharp.jpg", _image(True), "image/jpeg")}).json()
    blurry = api.post(path, headers=admin, files={"file": ("blurry.jpg", _image(False), "image/jpeg")}).json()
    assert sharp["width"] == 1400 and sharp["orientation"] == "LANDSCAPE"
    assert sharp["quality_status"] in {"GOOD", "ACCEPTABLE"}
    assert blurry["quality_status"] == "POOR" and any("blurry" in i for i in blurry["quality_issues"])
    assert blurry["blur_score"] < sharp["blur_score"]
    duplicate = api.post(path, headers=admin, files={"file": ("again.jpg", _image(True), "image/jpeg")})
    assert duplicate.status_code == 409
    not_image = api.post(path, headers=admin, files={"file": ("doc.pdf", build.text_pdf(["x"]), "application/pdf")})
    assert not_image.status_code == 415
    public = api.get("/api/v1/public/properties").json()[0]
    assert public["media"] == [f"/api/v1/public/media/{sharp['id']}"]  # POOR images are not published
    assert api.get(public["media"][0]).status_code == 200


def test_global_search_spans_entities(api, admin, agents):
    upload(api, admin, "property.docx", build.docx(build.PROPERTY_LINES))
    upload(api, admin, "reservation.docx", build.docx(build.RESERVATION_LINES))
    data = api.get("/api/v1/search", headers=admin, params={"q": "santos"}).json()
    results = data["results"]
    assert [c["title"] for c in results["clients"]] == ["Michael Santos"]
    assert results["clients"][0]["page"] == "clients"
    assert results["transactions"] and results["transactions"][0]["page"] == "transactions"
    azure = api.get("/api/v1/search", headers=admin, params={"q": "PROP-TEST-0001"}).json()["results"]
    assert azure["properties"][0]["title"].startswith("Test Property - Azure")
    assert api.get("/api/v1/search", params={"q": "santos"}).status_code == 401
    assert api.get("/api/v1/search", headers=admin, params={"q": "x"}).status_code == 422


def test_staff_login_failures_are_throttled(api):
    _make_user("throttled", "Employee")
    for _ in range(10):
        bad = api.post("/api/v1/auth/login", data={"username": "throttled", "password": "wrong"})
        assert bad.status_code == 401
    # Locked for this username, even with the right password; other accounts still work.
    locked = api.post("/api/v1/auth/login", data={"username": "throttled", "password": "password123"})
    assert locked.status_code == 429
    _make_user("other", "Employee")
    assert login(api, "other")
