"""Seller accounts and listings, developer images, the bulletin board and the
tripping schedule."""

from datetime import date, datetime, timedelta
from decimal import Decimal

import cv2
import numpy as np
import pytest

from app.api.v1 import client_portal
from app.models.agent import Agent
from app.models.client import Client
from app.models.partner import Partner
from app.models.transaction import PropertyTransaction
from tests.conftest import _make_user, login

API = "/api/v1"


def _image(width=1600, height=1000, drawing=False) -> bytes:
    """A sharp test picture (a floor-plan-like drawing on white, or a photo-like pattern)."""
    rng = np.random.default_rng(7)
    if drawing:
        image = np.full((height, width, 3), 250, np.uint8)
        for x in range(0, width, 40):
            cv2.line(image, (x, 0), (x, height), (20, 20, 20), 2)
        for y in range(0, height, 40):
            cv2.line(image, (0, y), (width, y), (20, 20, 20), 2)
    else:
        image = rng.integers(40, 220, (height, width, 3), dtype=np.uint8)
    return cv2.imencode(".png", image)[1].tobytes()


def _developer(db, name="Metrotowne Land", kind="DEVELOPER") -> int:
    partner = Partner(name=name, partner_type=kind, status="ACTIVE")
    db.add(partner)
    db.commit()
    return partner.id


def _new_seller(api, admin, username="cara", name="Cara Villanueva"):
    made = api.post(f"{API}/users", headers=admin, json={"username": username, "full_name": name, "role": "Seller",
                                                         "password": "password123", "phone_number": "0917 555 0101"})
    assert made.status_code == 201, made.text
    return made.json(), login(api, username)


LISTING = {"title": "Metrotowne Studio Unit", "category": "Condominium", "project_name": "Metrotowne",
           "price_total": "3600000", "floor_area_sqm": "22.92", "village_name": "Las Pinas City",
           "amenity_list": ["Swimming pool", "Basketball court"]}


def test_admin_adds_seller_accounts_without_existing_records(api, admin, db):
    user, _ = _new_seller(api, admin)
    agent = db.get(Agent, user["agent_id"])
    assert agent is not None and agent.full_name == "Cara Villanueva" and agent.status == "ACTIVE"
    assert agent.phone_number == "0917 555 0101" and user["agent_id"].startswith("AGT-")
    second, _ = _new_seller(api, admin, "nina", "Nina Castillo")
    assert second["agent_id"] != user["agent_id"]


def test_seller_adds_a_property_for_a_developer(api, admin, db):
    developer = _developer(db)
    bank = _developer(db, "Some Bank", "BANK")
    user, seller = _new_seller(api, admin)
    # The developer is required, and must be a developer.
    assert api.post(f"{API}/property-listings", headers=seller, json=LISTING).status_code == 422
    assert api.post(f"{API}/property-listings", headers=seller, json={**LISTING, "partner_id": bank}).status_code == 422
    options = api.get(f"{API}/seller/developers", headers=seller).json()
    assert [o["name"] for o in options] == ["Metrotowne Land"]

    created = api.post(f"{API}/property-listings", headers=seller, json={**LISTING, "partner_id": developer})
    assert created.status_code == 201, created.text
    listing = created.json()
    assert listing["marketing_status"] == "DRAFT" and listing["partner_id"] == developer
    mine = [l for l in api.get(f"{API}/seller/listings", headers=seller).json() if l["listing_id"] == listing["listing_id"]]
    assert mine and mine[0]["assigned"] and mine[0]["submitted_by_me"] and "price_total" in mine[0]["editable_fields"]

    # Their own draft is fully editable; once approved only the usual fields are.
    edit = api.put(f"{API}/seller/listings/{listing['listing_id']}", headers=seller, json={"price_total": "3550000"})
    assert edit.status_code == 200, edit.text
    assert float(edit.json()["price_total"]) == 3550000
    assert api.post(f"{API}/property-listings/{listing['listing_id']}/marketing", headers=admin,
                    json={"action": "approve"}).status_code == 200
    late = api.put(f"{API}/seller/listings/{listing['listing_id']}", headers=seller, json={"price_total": "1"})
    assert late.status_code == 403
    # Sellers can't add properties to other sellers or company records they don't own.
    _make_user("filer", "Filing Manager")
    assert api.post(f"{API}/property-listings", headers=login(api, "filer"),
                    json={**LISTING, "partner_id": developer}).status_code == 403


def test_floor_plans_and_amenity_pictures_with_quality_check(api, admin, db):
    developer = _developer(db)
    _, seller = _new_seller(api, admin)
    listing = api.post(f"{API}/property-listings", headers=seller, json={**LISTING, "partner_id": developer}).json()
    lid = listing["listing_id"]

    def upload(content, kind, caption=None, headers=seller):
        data = {"kind": kind, **({"caption": caption} if caption else {})}
        return api.post(f"{API}/media/properties/{lid}", headers=headers, data=data,
                        files={"file": ("image.png", content, "image/png")})

    plan = upload(_image(drawing=True), "FLOOR_PLAN", "Studio unit (22.92 sqm) - suggested layout")
    assert plan.status_code == 201, plan.text
    # A drawing isn't marked down for being bright or low in contrast.
    assert plan.json()["quality_status"] in ("GOOD", "ACCEPTABLE"), plan.json()
    assert not any("exposed" in issue or "contrast" in issue for issue in plan.json()["quality_issues"])
    assert upload(_image(), "AMENITY").status_code == 422  # an amenity needs its name
    pool = upload(_image(), "AMENITY", "Swimming pool")
    assert pool.status_code == 201 and pool.json()["caption"] == "Swimming pool"
    tiny = upload(_image(300, 200), "PHOTO")
    assert tiny.json()["quality_status"] == "POOR" and "Low resolution" in tiny.json()["quality_issues"][0]

    # Another seller can't touch these images.
    _, other = _new_seller(api, admin, "nina", "Nina Castillo")
    assert upload(_image(), "PHOTO", headers=other).status_code == 403
    assert api.delete(f"{API}/media/{pool.json()['id']}", headers=other).status_code == 403
    assert api.get(f"{API}/media?listing_id={lid}", headers=seller).status_code == 200

    api.post(f"{API}/property-listings/{lid}/marketing", headers=admin, json={"action": "approve"})
    public = api.get(f"{API}/public/properties/{lid}").json()
    assert [m["caption"] for m in public["floor_plans"]] == ["Studio unit (22.92 sqm) - suggested layout"]
    assert [m["caption"] for m in public["amenity_media"]] == ["Swimming pool"]
    assert public["media"] == []  # the poor photo stays off the website; plans and amenities aren't in the gallery
    assert api.get(public["amenity_media"][0]["url"]).status_code == 200


def _sale(db, agent_id, amount, when, client_name="Sarah Arumbo"):
    from app.models.property_listing import PropertyListing

    client = Client(full_name=client_name, source="TEST")
    listing = PropertyListing(title="Masaito", project_name="Masaito, Naic", category="House", status="RESERVED")
    db.add_all([client, listing])
    db.flush()
    tx = PropertyTransaction(client_id=client.client_id, property_id=listing.listing_id, agent_id=agent_id,
                             transaction_type="RESERVED", transaction_date=when, amount=Decimal(amount),
                             status="RESERVED", source="TEST")
    db.add(tx)
    db.commit()
    return str(tx.transaction_id)


def test_bulletin_posts_notify_everyone_and_memos_count_recorded_sales(api, admin, db):
    user, seller = _new_seller(api, admin)
    today = date.today()
    _sale(db, user["agent_id"], "80000000", datetime.combine(today, datetime.min.time()))
    tx = _sale(db, user["agent_id"], "714000", datetime.combine(today, datetime.min.time()), "Joyce Reyes")

    meeting = api.post(f"{API}/bulletin", headers=admin, json={
        "board": "ANNOUNCEMENT", "category": "MEETING", "title": "Monthly meeting",
        "event_at": f"{today + timedelta(days=3)}T09:00:00"})
    assert meeting.status_code == 201, meeting.text
    assert api.post(f"{API}/bulletin", headers=seller, json={"board": "ANNOUNCEMENT", "category": "UPDATE",
                                                             "title": "x"}).status_code == 403
    bell = api.get(f"{API}/notifications", headers=seller).json()["items"]
    assert any(item["key"] == f"bulletin:{meeting.json()['id']}" for item in bell)

    target = api.post(f"{API}/bulletin", headers=admin, json={
        "board": "MEMO", "category": "TARGET", "title": "Target sales 1.5 billion", "target_amount": "1500000000",
        "valid_from": str(today.replace(month=1, day=1)), "valid_until": str(today.replace(month=12, day=31))}).json()
    assert target["progress"]["company"]["sales"] == 80714000
    incentive = api.post(f"{API}/bulletin", headers=admin, json={
        "board": "MEMO", "category": "INCENTIVE", "title": "Travel incentives",
        "valid_from": str(today - timedelta(days=30)), "valid_until": str(today + timedelta(days=30)),
        "tiers": [{"label": "Bohol", "minimum_sales": "75000000", "reward": "3 days 2 nights for 2"},
                  {"label": "Boracay", "minimum_sales": "100000000"},
                  {"label": "Thailand", "minimum_sales": "150000000"}]}).json()
    assert incentive["progress"]["leaders"][0]["reached"] == "Bohol"
    notice = api.post(f"{API}/bulletin", headers=admin, json={
        "board": "MEMO", "category": "SALES_NOTICE", "title": "New reservation", "transaction_id": tx}).json()
    assert notice["sale"]["buyer"] == "Joyce Reyes" and notice["sale"]["project"] == "Masaito, Naic"

    # The seller sees the target and their own figures, never the company total or other sellers.
    seen = {p["id"]: p for p in api.get(f"{API}/bulletin?board=MEMO", headers=seller).json()}
    assert "company" not in seen[target["id"]]["progress"] and "leaders" not in seen[incentive["id"]]["progress"]
    assert seen[incentive["id"]]["progress"]["mine"]["reached"] == "Bohol"
    assert seen[incentive["id"]]["progress"]["mine"]["next"]["label"] == "Boracay"


def test_tripping_schedule_live_updates_and_buyer_notices(api, admin, db):
    seller_user, seller = _new_seller(api, admin)
    _, other = _new_seller(api, admin, "nina", "Nina Castillo")
    client_portal.auth_limiter._hits.clear()
    signup = api.post(f"{API}/client/register", json={"full_name": "Leonor Ogdan", "email": "leonor@example.com",
                                                      "phone_number": "0917 222 3333", "location": "Lipa",
                                                      "password": "s3cret-pass"})
    buyer_headers = {"Authorization": f"Bearer {signup.json()['access_token']}"}
    client = db.query(Client).filter(Client.email == "leonor@example.com").one()
    client.agent_id = seller_user["agent_id"]
    db.commit()

    version = api.get(f"{API}/trips/version", headers=admin).json()["version"]
    options = api.get(f"{API}/trips/buyer-options", headers=seller).json()
    assert [o["name"] for o in options] == ["Leonor Ogdan"] and options[0]["has_account"]
    assert api.get(f"{API}/trips/buyer-options", headers=other).json() == []
    trip = api.post(f"{API}/trips", headers=seller, json={
        "trip_date": str(date.today() + timedelta(days=1)), "pickup_time": "08:30", "pickup_point": "Abellar office",
        "subdivision": "Casa Feliz", "agent_id": "AGT-9999",  # ignored: a seller schedules their own trips
        "buyers": [{"client_id": client.client_id}, {"name": "Jennifer Koken", "phone": "0918 000 1111"}]})
    assert trip.status_code == 201, trip.text
    trip = trip.json()
    assert trip["agent_id"] == seller_user["agent_id"] and trip["needs_notice"]
    assert api.get(f"{API}/trips/version", headers=admin).json()["version"] != version
    assert [t["id"] for t in api.get(f"{API}/trips", headers=admin).json()["trips"]] == [trip["id"]]
    assert api.get(f"{API}/trips", headers=other).json()["trips"] == []
    assert api.put(f"{API}/trips/{trip['id']}", headers=other, json={**trip, "buyers": []}).status_code in (404, 422)

    sent = api.post(f"{API}/trips/{trip['id']}/notify", headers=seller, json={}).json()
    assert sent["sent_in_app"] == 1
    sms = [m for m in sent["messages"] if m["name"] == "Jennifer Koken"][0]
    assert sms["sms_link"].startswith("sms:09180001111?body=") and "Casa Feliz" in sms["text"]
    portal = api.get(f"{API}/client/trips", headers=buyer_headers).json()
    assert portal["unread"] == 1 and portal["trips"][0]["subdivision"] == "Casa Feliz"
    assert "8:30 AM" in portal["trips"][0]["notices"][0]["message"]

    # Rescheduling flags the buyers as not yet told.
    moved = api.post(f"{API}/trips/{trip['id']}/status", headers=seller, json={"status": "CONFIRMED"}).json()
    assert moved["status"] == "CONFIRMED" and moved["needs_notice"]
    assert any(n["page"] == "trips" for n in api.get(f"{API}/notifications", headers=admin).json()["items"])
    assert api.post(f"{API}/client/trips/read", headers=buyer_headers).status_code == 204
    assert api.get(f"{API}/client/trips", headers=buyer_headers).json()["unread"] == 0


def test_sellers_pin_their_location_and_draw_their_own_lot(api, admin, db):
    from tests.test_lot_boundary import LOT, polygon

    user, seller = _new_seller(api, admin)
    other_user, other = _new_seller(api, admin, "nina", "Nina Castillo")
    # Their own location (buyers see the nearest agents), not anyone else's.
    pin = {"agent_location": "Dasmariñas, Cavite", "latitude": "14.3294", "longitude": "120.9367"}
    saved = api.put(f"{API}/agents/{user['agent_id']}/location", headers=seller, json=pin)
    assert saved.status_code == 200, saved.text
    assert float(saved.json()["latitude"]) == 14.3294
    assert api.put(f"{API}/agents/{other_user['agent_id']}/location", headers=seller, json=pin).status_code == 403
    assert api.put(f"{API}/agents/{other_user['agent_id']}/location", headers=admin, json=pin).status_code == 200
    assert api.put(f"{API}/agents/{user['agent_id']}/location", headers=seller,
                   json={"latitude": "14.3"}).status_code == 422

    # The lot of the property they added, until it is approved.
    developer = _developer(db)
    listing = api.post(f"{API}/property-listings", headers=seller,
                       json={**LISTING, "partner_id": developer, "category": "House and Lot"}).json()
    path = f"{API}/property-listings/{listing['listing_id']}/boundary"
    body = {"geometry": polygon(LOT), "use_as_lot_area": True}
    assert api.put(path, headers=other, json=body).status_code == 403
    drawn = api.put(path, headers=seller, json=body)
    assert drawn.status_code == 200, drawn.text
    assert float(drawn.json()["lot_area_sqm"]) > 0
    api.post(f"{API}/property-listings/{listing['listing_id']}/marketing", headers=admin, json={"action": "approve"})
    assert api.put(path, headers=seller, json=body).status_code == 403
    assert api.delete(path, headers=admin).status_code == 200
