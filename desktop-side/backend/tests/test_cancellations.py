"""Every cancelled reservation records why, who and when."""

from __future__ import annotations

from sqlalchemy import select

from app.models.client import Client
from app.models.property_listing import PropertyListing
from app.models.transaction import PropertyTransaction
from tests import documents as build
from tests.test_document_pipeline import assert_success, upload


def _reserve(api, admin, db) -> PropertyTransaction:
    assert_success(upload(api, admin, "property.docx", build.docx(build.PROPERTY_LINES)))
    assert_success(upload(api, admin, "reservation.docx", build.docx(build.RESERVATION_LINES)))
    return db.execute(select(PropertyTransaction)).scalar_one()


def test_cancelling_a_reservation_needs_and_keeps_a_reason(api, admin, employee, agents, db):
    reservation = _reserve(api, admin, db)
    path = f"/api/v1/transactions/{reservation.transaction_id}/cancel"

    assert api.post(path, headers=admin, json={"reason": ""}).status_code == 422
    assert api.post(path, headers=employee, json={"reason": "Buyer backed out"}).status_code == 403

    response = api.post(path, headers=admin, json={"reason": "Buyer's bank loan was not approved"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "CANCELLED"
    assert body["cancellation_reason"] == "Buyer's bank loan was not approved"
    assert body["cancelled_by"] and body["cancelled_at"]

    db.expire_all()
    assert db.get(PropertyListing, reservation.property_id).status == "AVAILABLE"
    assert db.get(Client, reservation.client_id).status == "CANCELLED"
    listed = api.get("/api/v1/transactions", headers=admin).json()[0]
    assert listed["cancellation_reason"] == "Buyer's bank loan was not approved"
    # Only an open reservation can be cancelled.
    assert api.post(path, headers=admin, json={"reason": "Again"}).status_code == 409


def test_property_edit_cancels_with_the_given_or_a_stated_reason(api, admin, agents, db):
    reservation = _reserve(api, admin, db)
    listing_id = reservation.property_id
    response = api.put(f"/api/v1/property-listings/{listing_id}", headers=admin,
                        json={"status": "AVAILABLE", "cancellation_reason": "Client moved abroad"})
    assert response.status_code == 200, response.text
    db.expire_all()
    cancelled = db.get(PropertyTransaction, reservation.transaction_id)
    assert cancelled.status == "CANCELLED" and cancelled.cancellation_reason == "Client moved abroad"


def test_property_edit_without_a_reason_records_what_happened(api, admin, agents, db):
    reservation = _reserve(api, admin, db)
    response = api.put(f"/api/v1/property-listings/{reservation.property_id}", headers=admin,
                       json={"status": "ON_HOLD"})
    assert response.status_code == 200, response.text
    db.expire_all()
    cancelled = db.get(PropertyTransaction, reservation.transaction_id)
    assert cancelled.cancellation_reason == "The property was changed from reserved to on hold."
