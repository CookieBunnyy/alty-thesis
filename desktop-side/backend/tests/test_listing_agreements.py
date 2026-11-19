"""Listing a new property from documents: the owner's listing agreement, then
the property information sheet (the demo PDFs in docs/demo-documents), and
reading a document's fields to fill the Add property form."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select

from app.models.branch import Branch
from app.models.document import Document
from app.models.listing_agreement import ListingAgreement
from app.models.partner import Partner
from app.models.property_listing import PropertyListing
from tests.test_document_pipeline import assert_success, upload

DEMO = Path(__file__).resolve().parents[3] / "docs" / "demo-documents"
AGREEMENT = DEMO / "11-listing-agreement.pdf"
SHEET = DEMO / "12-property-information-sheet.pdf"

pytestmark = pytest.mark.skipif(not (AGREEMENT.exists() and SHEET.exists()),
                                reason="run scripts/make_demo_documents.py first")


def test_listing_agreement_then_property_information(api, admin, db):
    developer = Partner(name="Amaia", partner_type="DEVELOPER", status="ACTIVE")
    team = Branch(name="Team Pinyas", code="PIN")
    db.add_all([developer, team])
    db.commit()

    # The agreement lists the property and records the owner's terms.
    doc = upload(api, admin, AGREEMENT.name, AGREEMENT.read_bytes())
    assert_success(doc)
    assert doc["document_type"] == "LISTING_AGREEMENT"
    db.expire_all()
    listing = db.scalar(select(PropertyListing).where(PropertyListing.external_listing_id == "ABR-26-0901"))
    assert listing is not None and listing.status == "AVAILABLE"
    assert float(listing.price_total) == 3_600_000
    agreement = db.scalar(select(ListingAgreement).where(ListingAgreement.listing_id == listing.listing_id))
    assert agreement.seller_name == "Ricardo T. Bautista"
    assert agreement.broker_name == "Juan Paolo Reyes"
    assert agreement.rights_to_sell == "EXCLUSIVE_RIGHT_TO_SELL"
    assert agreement.commission_type == "PERCENTAGE" and float(agreement.commission_rate) == 5
    assert float(agreement.cooperating_commission_rate) == 2 and agreement.extension_days == 90
    assert agreement.dual_agency_allowed is True
    assert agreement.listing_start < agreement.listing_end
    assert "For Sale sign" in agreement.marketing_permissions
    assert agreement.tct_number == "T-123-2019004512"

    # The information sheet fills every detail of the same property.
    doc = upload(api, admin, SHEET.name, SHEET.read_bytes())
    assert_success(doc)
    assert doc["document_type"] == "PROPERTY_INFORMATION"
    db.expire_all()
    listing = db.get(PropertyListing, listing.listing_id)
    assert listing.category == "House and Lot"
    assert listing.partner_id == developer.id and listing.branch_id == team.id
    assert listing.project_name == "Amaia Scapes General Trias"
    assert float(listing.lot_area_sqm) == 99 and float(listing.floor_area_sqm) == 46
    assert listing.num_bedrooms == 3 and listing.garage_spaces == 1
    assert listing.property_status == "RFO"
    assert listing.financing_options == ["BANK", "PAGIBIG", "CASH"]
    assert float(listing.reservation_fee) == 20_000 and listing.equity_terms_months == 12
    assert listing.amenity_list == ["Clubhouse", "Swimming pool", "Jogging path", "24/7 security"]
    assert listing.other_amenities == "Pocket garden; Bike lanes"

    # The property's history shows the agreement.
    history = api.get(f"/api/v1/property-listings/{listing.listing_id}/history", headers=admin).json()
    assert history["listing_agreement"]["seller_name"] == "Ricardo T. Bautista"
    assert history["listing_agreement"]["listing_price"] == 3_600_000


def test_unknown_developer_is_a_warning_not_a_failure(api, admin, db):
    upload(api, admin, AGREEMENT.name, AGREEMENT.read_bytes())
    doc = upload(api, admin, SHEET.name, SHEET.read_bytes())
    processing = assert_success(doc)
    assert any("Amaia" in warning for warning in processing["warnings"])
    db.expire_all()
    listing = db.scalar(select(PropertyListing).where(PropertyListing.external_listing_id == "ABR-26-0901"))
    assert listing.partner_id is None and listing.lot_area_sqm is not None


def test_read_fields_fills_a_form_without_saving(api, admin, db):
    db.add(Partner(name="Amaia", partner_type="DEVELOPER", status="ACTIVE"))
    db.commit()
    response = api.post("/api/v1/documents/read-fields", headers=admin,
                        files={"file": (SHEET.name, SHEET.read_bytes(), "application/pdf")})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["document_type"] == "PROPERTY_INFORMATION"
    assert body["fields"]["lot_area_sqm"] == "99" and body["fields"]["property_status"] == "RFO"
    assert body["resolved"]["partner_id"] is not None
    assert db.scalar(select(PropertyListing).where(PropertyListing.external_listing_id == "ABR-26-0901")) is None
    assert db.scalar(select(Document)) is None


def test_other_amenities_saved_with_the_listing(api, admin, db):
    developer = Partner(name="Amaia", partner_type="DEVELOPER", status="ACTIVE")
    db.add(developer)
    db.commit()
    response = api.post("/api/v1/property-listings", headers=admin, json={
        "title": "Test house", "category": "House and Lot", "partner_id": developer.id,
        "amenity_list": ["Swimming pool", "Clubhouse"], "other_amenities": "  Koi pond  "})
    assert response.status_code == 201, response.text
    assert response.json()["other_amenities"] == "Koi pond"
    listing_id = response.json()["listing_id"]
    response = api.put(f"/api/v1/property-listings/{listing_id}", headers=admin, json={"other_amenities": ""})
    assert response.status_code == 200, response.text
    assert response.json()["other_amenities"] is None
