"""End-to-end document ingestion against the real (test) database."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select

from app.models.client import Client
from app.models.document import Document
from app.models.property_listing import PropertyListing
from app.models.transaction import PropertyTransaction
from tests import documents as build

DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def upload(api, headers, name: str, content: bytes, document_type: str | None = None,
           allow_duplicate: bool = False, expected: int = 201) -> dict:
    mime = DOCX if name.endswith(".docx") else "application/pdf" if name.endswith(".pdf") else "image/png"
    data = {"allow_duplicate": str(allow_duplicate).lower()}
    if document_type:
        data["document_type"] = document_type
    response = api.post("/api/v1/documents/upload", headers=headers,
                        files={"file": (name, content, mime)}, data=data)
    assert response.status_code == expected, response.text
    return response.json()


def assert_success(document: dict) -> dict:
    processing = document["processing"]
    assert document["status"] == "SUCCESS", (
        f"{processing.get('stage')}: {processing.get('error_reason')}"
    )
    assert processing["stage"] == "COMPLETE"
    return processing


# ---------------------------------------------------------------------------
# TEST 1-5: the document-first chain
# ---------------------------------------------------------------------------

def test_full_chain_property_buyer_reservation_sale_and_duplicate(api, admin, agents, db):
    # TEST 1 — Property Information -> property_listings, AVAILABLE
    doc = upload(api, admin, "property.docx", build.docx(build.PROPERTY_LINES))
    processing = assert_success(doc)
    assert doc["document_type"] == "PROPERTY_INFORMATION"
    assert processing["extraction"]["method"] == "TEXT"
    listing = db.execute(select(PropertyListing).where(
        PropertyListing.external_listing_id == "PROP-TEST-0001")).scalar_one()
    assert listing.status == "AVAILABLE"
    assert listing.num_bedrooms == 3 and listing.num_bathrooms == 2
    assert float(listing.price_total) == 8_500_000
    assert listing.amenity_list == ["Clubhouse", "Swimming Pool", "Basketball Court"]
    assert listing.has_garage is True and listing.garage_spaces == 2

    # TEST 2 — Buyer Document -> clients (created, no transaction)
    doc = upload(api, admin, "buyer.docx", build.docx(build.BUYER_LINES))
    processing = assert_success(doc)
    assert doc["document_type"] == "BUYER_DOCUMENT"
    clients = db.execute(select(Client)).unique().scalars().all()
    assert len(clients) == 1
    client = clients[0]
    assert (client.external_client_id, client.full_name) == ("CLI-TEST-0001", "Michael Santos")
    assert client.status == "PROSPECT" and client.property_id == listing.listing_id
    assert client.agent_id == "AGT-0006" and client.occupation == "Business Owner"
    assert db.execute(select(PropertyTransaction)).first() is None

    # TEST 3 — Reservation -> same client, reservation created, RESERVED
    doc = upload(api, admin, "reservation.docx", build.docx(build.RESERVATION_LINES))
    processing = assert_success(doc)
    assert doc["document_type"] == "RESERVATION_AGREEMENT"
    assert processing["matched_entities"]["client"]["matched_by"] == "CLIENT_ID"
    db.expire_all()
    assert len(db.execute(select(Client)).unique().scalars().all()) == 1
    reservation = db.execute(select(PropertyTransaction)).scalar_one()
    assert reservation.transaction_type == "RESERVED" and reservation.status == "RESERVED"
    assert reservation.external_transaction_id == "RSV-TEST-0001"
    assert float(reservation.amount) == 50_000
    assert reservation.source == "DOCUMENT" and reservation.source_document_id == doc["document_id"]
    assert db.get(PropertyListing, listing.listing_id).status == "RESERVED"

    # TEST 4 — Sale -> same client, sale added, reservation preserved, SOLD
    sale = build.docx(build.SALE_LINES)  # the same bytes are re-sent in TEST 5
    doc = upload(api, admin, "sale.docx", sale)
    processing = assert_success(doc)
    assert doc["document_type"] == "SALE_AGREEMENT"
    db.expire_all()
    assert len(db.execute(select(Client)).unique().scalars().all()) == 1
    rows = db.execute(select(PropertyTransaction).order_by(PropertyTransaction.transaction_date)).scalars().all()
    assert [(t.transaction_type, t.status) for t in rows] == [("RESERVED", "COMPLETED"), ("SOLD", "COMPLETED")]
    assert db.get(PropertyListing, listing.listing_id).status == "SOLD"
    assert db.get(Client, client.client_id).status == "SOLD"

    # TEST 5 — Same sale agreement again -> no duplicate transaction
    duplicate = api.post("/api/v1/documents/upload", headers=admin,
                         files={"file": ("sale.docx", sale, DOCX)})
    assert duplicate.status_code == 409  # exact file already uploaded
    doc = upload(api, admin, "sale.docx", build.docx(build.SALE_LINES), allow_duplicate=True)
    processing = assert_success(doc)
    assert processing["idempotent"] is True and processing["created_records"] == []
    db.expire_all()
    assert db.execute(select(PropertyTransaction)).scalars().all().__len__() == 2

    # Revenue counts the sale only (not the fulfilled reservation).
    summary = api.get("/api/v1/transactions/summary", headers=admin).json()
    assert float(summary["amount_total"]) == 8_500_000 and summary["completed"] == 1

    # Client profile shows both transactions and the related documents.
    profile = api.get(f"/api/v1/clients/{client.client_id}/profile", headers=admin).json()
    assert len(profile["transactions"]) == 2
    assert {d["document_type"] for d in profile["documents"]} >= {"RESERVATION_AGREEMENT", "SALE_AGREEMENT"}


def test_buyer_document_with_reservation_records_it(api, admin, agents, db):
    upload(api, admin, "property.docx", build.docx(build.PROPERTY_LINES))
    lines = build.BUYER_LINES + ["Transaction Type: RESERVATION", "Transaction Date: 2026-09-30",
                                 "Transaction Amount: PHP 50,000.00"]
    doc = upload(api, admin, "buyer-with-reservation.docx", build.docx(lines))
    assert_success(doc)
    transaction = db.execute(select(PropertyTransaction)).scalar_one()
    assert transaction.transaction_type == "RESERVED"
    # A later reservation agreement for the same reservation reuses it.
    doc = upload(api, admin, "reservation.docx", build.docx(build.RESERVATION_LINES))
    processing = assert_success(doc)
    assert processing["matched_entities"]["transaction"]["matched_by"] == "CLIENT_PROPERTY_TYPE"
    db.expire_all()
    transaction = db.execute(select(PropertyTransaction)).scalar_one()
    assert transaction.external_transaction_id == "RSV-TEST-0001"


def test_agent_document_creates_then_updates_without_duplicates(api, admin, db):
    doc = upload(api, admin, "agent.docx", build.docx(build.AGENT_LINES))
    processing = assert_success(doc)
    assert processing["created_records"] == ["agents:AGT-0003"]
    updated = [line.replace("Star Rating: 4.9", "Star Rating: 4.7") for line in build.AGENT_LINES]
    doc = upload(api, admin, "agent-v2.docx", build.docx(updated))
    processing = assert_success(doc)
    assert processing["updated_records"] == ["agents:AGT-0003"]
    assert processing["changes"]["agents:AGT-0003"]["star_rating"]["new"] == "4.7"
    agents = api.get("/api/v1/agents", headers=admin).json()
    assert [a["agent_id"] for a in agents] == ["AGT-0003"]


def test_duplicate_client_matched_by_email_not_duplicated(api, admin, agents, db):
    upload(api, admin, "property.docx", build.docx(build.PROPERTY_LINES))
    upload(api, admin, "buyer.docx", build.docx(build.BUYER_LINES))
    # Same person, no client id, different formatting of the same email.
    lines = ["BUYER INFORMATION", "Full Name: MICHAEL  SANTOS",
             "Email: Michael.Santos.Test@Example.com", "Occupation: Engineer"]
    doc = upload(api, admin, "buyer-again.docx", build.docx(lines))
    processing = assert_success(doc)
    assert processing["matched_entities"]["client"]["matched_by"] == "EMAIL"
    assert any("occupation kept" in warning for warning in processing["warnings"])
    assert len(db.execute(select(Client)).unique().scalars().all()) == 1


def test_contact_details_of_another_person_fail_matching(api, admin, agents, db):
    upload(api, admin, "buyer.docx", build.docx(build.BUYER_LINES[:6]))
    lines = ["BUYER INFORMATION", "Full Name: Jennifer Cruz", "Contact Number: 0917 555 0101"]
    doc = upload(api, admin, "conflict.docx", build.docx(lines))
    assert doc["status"] == "FAILED"
    assert doc["processing"]["stage"] == "ENTITY_MATCHING"
    assert "belong to existing client 'Michael Santos'" in doc["processing"]["error_reason"]


# ---------------------------------------------------------------------------
# Failures are explicit and traceable
# ---------------------------------------------------------------------------

def test_failed_entity_matching_then_reprocess_after_property_arrives(api, admin, agents, db):
    doc = upload(api, admin, "reservation.docx", build.docx(build.RESERVATION_LINES))
    assert doc["status"] == "FAILED"
    assert doc["processing"]["stage"] == "ENTITY_MATCHING"
    assert doc["processing_error"] == "Property PROP-TEST-0001 not found"
    assert doc["processing"]["extracted_fields"]["listing_id"] == "PROP-TEST-0001"
    assert db.execute(select(Client)).first() is None  # nothing half-written

    upload(api, admin, "property.docx", build.docx(build.PROPERTY_LINES))
    response = api.post(f"/api/v1/documents/{doc['document_id']}/reprocess", headers=admin)
    assert response.status_code == 200, response.text
    assert_success(response.json())
    assert db.execute(select(PropertyTransaction)).scalar_one().transaction_type == "RESERVED"


def test_invalid_document_reports_validation_errors(api, admin):
    lines = ["RESERVATION AGREEMENT", "Buyer Name: Someone", "Reservation Amount: lots"]
    doc = upload(api, admin, "invalid.docx", build.docx(lines))
    assert doc["status"] == "FAILED" and doc["processing"]["stage"] == "VALIDATION"
    fields = doc["processing"]["validation_result"]["missing_or_invalid_fields"]
    assert "amount" in fields and "listing_id or property_title" in fields
    assert "transaction_date" in fields


def test_unclassifiable_document_fails_classification(api, admin):
    doc = upload(api, admin, "notes.docx", build.docx(["Meeting notes", "Discussed the weather."]))
    assert doc["status"] == "FAILED" and doc["processing"]["stage"] == "CLASSIFICATION"


def test_declared_type_conflicting_with_content_fails(api, admin):
    doc = upload(api, admin, "p.docx", build.docx(build.PROPERTY_LINES), document_type="AGENT_INFORMATION")
    assert doc["status"] == "FAILED" and doc["processing"]["stage"] == "CLASSIFICATION"
    assert "content is a PROPERTY_INFORMATION" in doc["processing_error"]


def test_reservation_rejected_when_property_already_reserved_by_other_client(api, admin, agents, db):
    upload(api, admin, "property.docx", build.docx(build.PROPERTY_LINES))
    upload(api, admin, "reservation.docx", build.docx(build.RESERVATION_LINES))
    other = ["RESERVATION AGREEMENT", "Buyer Name: Jennifer Cruz", "Email: jennifer.cruz.test@example.com",
             "Listing ID: PROP-TEST-0001", "Agent ID: AGT-0003", "Reservation Date: 2026-10-01",
             "Reservation Amount: 75000"]
    doc = upload(api, admin, "reservation-2.docx", build.docx(other))
    assert doc["status"] == "FAILED" and doc["processing"]["stage"] == "ENTITY_MATCHING"
    assert "is RESERVED by client Michael Santos" in doc["processing_error"]
    assert db.execute(select(Client)).unique().scalars().all().__len__() == 1


@pytest.mark.parametrize("name,content,fragment", [
    ("tool.exe", b"MZ\x90\x00binary", "Unsupported file type"),
    ("notes.txt", b"Listing ID: 1", "Unsupported file type"),
    ("fake.pdf", build.docx(["x"]), "Only .docx"),
    ("renamed.docx", build.text_pdf(["x"]), "extension is not .pdf"),
], ids=["exe", "txt", "docx-named-pdf", "pdf-named-docx"])
def test_unsupported_or_mismatched_files_rejected(api, admin, name, content, fragment):
    response = api.post("/api/v1/documents/upload", headers=admin,
                        files={"file": (name, content, "application/octet-stream")})
    assert response.status_code == 415
    assert fragment in response.json()["detail"]


def test_text_pdf_property_document(api, admin, db):
    lines = [line.replace("PROP-TEST-0001", "PROP-TEST-PDF") for line in build.PROPERTY_LINES]
    doc = upload(api, admin, "property.pdf", build.text_pdf(lines))
    processing = assert_success(doc)
    assert processing["extraction"]["method"] == "TEXT"
    assert doc["source_format"] == "TEXT_PDF"


def test_scanned_pdf_uses_ocr(api, admin, db):
    lines = ["PROPERTY INFORMATION", "Listing ID: PROP-SCAN-0001", "Property Title: Scanned Villa",
             "Category: Townhouse", "Price: PHP 4,200,000", "Number of Bedrooms: 2"]
    doc = upload(api, admin, "scanned.pdf", build.scanned_pdf(lines))
    processing = assert_success(doc)
    assert processing["extraction"]["method"] == "OCR" and doc["source_format"] == "SCANNED_PDF"
    listing = db.execute(select(PropertyListing).where(
        PropertyListing.external_listing_id == "PROP-SCAN-0001")).scalar_one()
    # OCR may drop inter-word spaces on synthetic renders; identifiers and
    # amounts (what matching depends on) must be exact.
    assert listing.title.replace(" ", "") == "ScannedVilla"
    assert float(listing.price_total) == 4_200_000 and listing.num_bedrooms == 2


def test_image_document_uses_ocr(api, admin, db):
    lines = ["AGENT INFORMATION", "Agent ID: AGT-0099", "Full Name: Ramon Diaz", "Star Rating: 4.2"]
    doc = upload(api, admin, "agent.png", build.png(lines))
    processing = assert_success(doc)
    assert processing["extraction"]["method"] == "OCR" and doc["source_format"] == "IMAGE"


def test_document_delete_keeps_audit_trail(api, admin, db):
    doc = upload(api, admin, "agent.docx", build.docx(build.AGENT_LINES))
    assert api.delete(f"/api/v1/documents/{doc['document_id']}", headers=admin).status_code == 204
    assert db.execute(select(Document)).first() is None
    audit = api.get("/api/v1/audit", headers=admin, params={"entity_id": doc["document_id"]}).json()
    actions = {item["action"] for item in audit["items"]}
    assert {"DOCUMENT_UPLOADED", "DOCUMENT_PROCESSED", "DOCUMENT_DELETED"} <= actions


def test_document_types_endpoint_lists_only_processable_types(api, admin):
    codes = [item["code"] for item in api.get("/api/v1/documents/types", headers=admin).json()]
    assert codes[0] == "AUTO"
    for code in ("PROPERTY_INFORMATION", "BUYER_DOCUMENT", "RESERVATION_AGREEMENT", "SALE_AGREEMENT",
                 "AGENT_INFORMATION", "SELLER_DOCUMENT", "TRANSACTION_DOCUMENT", "RECEIPT", "VOUCHER",
                 "PROOF_OF_PAYMENT", "CONTRACT", "DEED", "INVOICE", "OTHER"):
        assert code in codes


def test_receipt_links_to_existing_transaction(api, admin, agents, db):
    upload(api, admin, "property.docx", build.docx(build.PROPERTY_LINES))
    upload(api, admin, "reservation.docx", build.docx(build.RESERVATION_LINES))
    lines = ["OFFICIAL RECEIPT", "Receipt No: OR-5521", "Reservation ID: RSV-TEST-0001",
             "Received From: Michael Santos", "Amount Paid: PHP 50,000.00", "Payment Date: 2026-09-30"]
    doc = upload(api, admin, "receipt.docx", build.docx(lines))
    assert_success(doc)
    assert doc["document_type"] == "RECEIPT"
    assert doc["transaction_reference"] == "RSV-TEST-0001"
    assert doc["related_party_name"] == "Michael Santos"


# ---------------------------------------------------------------------------
# The synthetic test documents supplied for this project (skipped if absent)
# ---------------------------------------------------------------------------

DOWNLOADS = Path.home() / "Downloads"


@pytest.mark.skipif(not (DOWNLOADS / "ALTY_Property_Information_Test.docx").exists(),
                    reason="supplied test documents not present")
def test_supplied_documents(api, admin, agents, db):
    read = lambda name: (DOWNLOADS / name).read_bytes()  # noqa: E731
    doc = upload(api, admin, "ALTY_Property_Information_Test.docx", read("ALTY_Property_Information_Test.docx"))
    assert_success(doc)
    # Buyer 01 references PROP-TEST-0001 (now present) and states a reservation.
    doc = upload(api, admin, "ALTY_Buyer_Document_Test.docx", read("ALTY_Buyer_Document_Test.docx"))
    processing = assert_success(doc)
    assert doc["document_type"] == "BUYER_DOCUMENT"
    assert "clients:" in " ".join(processing["created_records"])
    # Buyers 02/03 reference properties that do not exist -> explicit failure.
    for name, missing in (("ALTY_Buyer_Document_Test_02.docx", "PROP-TEST-0002"),
                          ("ALTY_Buyer_Document_Test_03.docx", "PROP-TEST-0003")):
        doc = upload(api, admin, name, read(name))
        assert doc["status"] == "FAILED" and doc["processing"]["stage"] == "ENTITY_MATCHING"
        assert doc["processing_error"] == f"Property {missing} not found"
        assert doc["document_type"] == "BUYER_DOCUMENT"
