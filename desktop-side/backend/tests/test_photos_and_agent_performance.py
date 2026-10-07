"""Profile photos (agents and staff) and agent performance / forecast."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from io import BytesIO

from PIL import Image

from app.models.agent import Agent
from app.models.client import Client
from app.models.property_listing import PropertyListing
from app.models.transaction import PropertyTransaction


def _image(width=640, height=420, fmt="PNG") -> bytes:
    out = BytesIO()
    Image.new("RGB", (width, height), (90, 140, 60)).save(out, format=fmt)
    return out.getvalue()


def _agent(db, agent_id="AGT-P", name="Photo Agent"):
    db.add(Agent(agent_id=agent_id, full_name=name, status="ACTIVE", sync_status="SYNCED"))
    db.commit()


def test_agent_photo_upload_public_view_and_removal(api, admin, employee, db):
    _agent(db)
    files = {"file": ("me.png", _image(), "image/png")}
    assert api.put("/api/v1/agents/AGT-P/photo", headers=employee, files=files).status_code == 403
    bad = api.put("/api/v1/agents/AGT-P/photo", headers=admin, files={"file": ("x.png", b"not an image", "image/png")})
    assert bad.status_code == 422

    response = api.put("/api/v1/agents/AGT-P/photo", headers=admin, files=files)
    assert response.status_code == 200, response.text
    version = response.json()["photo_version"]
    assert version
    photo = api.get("/api/v1/public/agents/AGT-P/photo")
    assert photo.status_code == 200 and photo.headers["content-type"] == "image/jpeg"
    assert Image.open(BytesIO(photo.content)).size == (512, 512)  # cropped to a square
    public = {a["agent_id"]: a for a in api.get("/api/v1/public/agents").json()}
    assert public["AGT-P"]["photo_url"] == f"/api/v1/public/agents/AGT-P/photo?v={version}"

    removed = api.delete("/api/v1/agents/AGT-P/photo", headers=admin).json()
    assert removed["photo_version"] is None
    assert api.get("/api/v1/public/agents/AGT-P/photo").status_code == 404


def test_staff_set_their_own_photo(api, admin, employee):
    me = api.put("/api/v1/users/me/photo", headers=employee, files={"file": ("me.jpg", _image(fmt="JPEG"), "image/jpeg")})
    assert me.status_code == 200, me.text
    assert me.json()["photo_version"]
    user_id = me.json()["id"]
    assert api.get("/api/v1/auth/me", headers=employee).json()["photo_version"] == me.json()["photo_version"]
    seen = api.get(f"/api/v1/users/{user_id}/photo", headers=admin)
    assert seen.status_code == 200 and seen.headers["content-type"] == "image/jpeg"
    assert api.get(f"/api/v1/users/{user_id}/photo").status_code == 401  # staff only
    assert api.delete("/api/v1/users/me/photo", headers=employee).json()["photo_version"] is None


def _deal(db, listing, agent_id, kind, status, when, amount="1000000"):
    client = Client(full_name=f"Buyer {when:%Y%m%d%H%M%S%f}", status="SOLD", source="DOCUMENT",
                    sync_status="SYNCED", agent_id=agent_id)
    db.add(client)
    db.flush()
    db.add(PropertyTransaction(client_id=client.client_id, property_id=listing.listing_id, agent_id=agent_id,
                               transaction_type=kind, status=status, amount=Decimal(amount),
                               source="DOCUMENT", transaction_date=when))


def test_performance_rate_and_agent_forecast(api, admin, db):
    _agent(db, "AGT-F", "Forecast Agent")
    _agent(db, "AGT-Q", "Quiet Agent")
    listing = PropertyListing(title="House", status="SOLD", sync_status="SYNCED")
    db.add(listing)
    db.flush()
    now = datetime.now(timezone.utc)
    # Ten complete months with sales for AGT-F (rising), plus one cancelled reservation.
    for months_back in range(1, 11):
        when = (now.replace(day=15) - timedelta(days=30 * months_back))
        for n in range(1 + (10 - months_back) // 3):
            _deal(db, listing, "AGT-F", "SOLD", "COMPLETED", when + timedelta(minutes=n))
    _deal(db, listing, "AGT-F", "RESERVED", "CANCELLED", now - timedelta(days=40))
    db.commit()

    agents = {a["agent_id"]: a for a in api.get("/api/v1/agents", headers=admin).json()}
    forecast_agent = agents["AGT-F"]
    sales = forecast_agent["recorded_completed_sales"]
    assert forecast_agent["recorded_deals"] == sales + 1
    assert forecast_agent["performance_rate"] == round(sales / (sales + 1) * 100, 1)
    assert agents["AGT-Q"]["performance_rate"] is None  # no deals: no rate, not 0%

    outlook = {a["agent_id"]: a for a in api.get("/api/v1/intelligence/agent-forecasts", headers=admin).json()["agents"]}
    assert outlook["AGT-F"]["status"] == "estimated"
    assert outlook["AGT-F"]["expected_sales"] is not None and len(outlook["AGT-F"]["forecast"]) == 3
    assert outlook["AGT-Q"]["status"] == "insufficient_data" and outlook["AGT-Q"]["expected_sales"] is None
    single = api.get("/api/v1/intelligence/agents/AGT-F/forecast", headers=admin).json()
    assert single["agent_id"] == "AGT-F" and single["status"] == "estimated"
