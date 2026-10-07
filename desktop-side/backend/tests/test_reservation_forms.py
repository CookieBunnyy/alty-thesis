"""Reservation forms laid out as tables (Word tables, PDF rows without colons)."""

from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO

from docx import Document as WordDocument
from sqlalchemy import select

from app.models.client import Client
from app.models.transaction import PropertyTransaction
from app.services.document_extraction import (
    extract_labeled_fields,
    extract_text,
    normalize_fields,
    parse_date,
)
from tests import documents as build
from tests.test_document_pipeline import assert_success, upload

# The sample "PROPERTY RESERVATION FORM": section headings, then label | value rows.
# The project is the test property's village; the consultant is agent AGT-0006.
SECTIONS = [
    ("PROPERTY DETAILS", [
        ("Project Name", "Azure Heights Village"),
        ("Property Type", "Two-Storey Single Detached House and Lot"),
        ("Block / Lot", "Block 18, Lot 6"),
        ("Property Location", "Brgy. Molino VI, Bacoor City, Cavite 4102"),
        ("Selling Price", "PHP 8,500,000.00"),
        ("Reservation Fee", "PHP 50,000.00"),
        ("Reservation Date", "October 7, 2026"),
    ]),
    ("BUYER / CO-BUYER", [
        ("Primary Buyer", "DANIEL JOSEPH NAVARRO"),
        ("Co-Buyer", "ELENA MARIE NAVARRO"),
        ("Primary Buyer DOB", "09/21/1987"),
        ("Co-Buyer DOB", "11/06/1990"),
        ("Civil Status", "Married"),
        ("Contact No.", "0920-555-1842"),
        ("Email", "daniel.navarro@example.com"),
        ("Residential Address", "Blk 4 Lot 22, Springdale Homes, Bacoor, Cavite"),
    ]),
    ("PAYMENT / FINANCING", [
        ("Payment Scheme", "Bank Financing"),
        ("Down Payment", "PHP 1,096,000.00 (20%)"),
        ("Reservation Payment Method", "Online Bank Transfer"),
        ("Reference No.", "TRX-20261007-18425"),
    ]),
    ("AGENT / BROKER INFORMATION", [
        ("Property Consultant", "DANIEL FLORES"),
        ("PRC / Accreditation No.", "PRC-RE-0009876"),
        ("Mobile", "0917-321-8844"),
        ("Email", "daniel.flores@example.com"),
        ("Branch", "Bacoor Sales Office"),
    ]),
]
TITLE = ["ABELLAR RESIDENTIAL PROPERTIES", "PROPERTY RESERVATION FORM"]
FOOTER = [
    "Special request / remarks: Buyer requests a corner-adjacent unit if available.",
    "Primary Buyer Signature: ______________    Co-Buyer Signature: ______________",
    "Sales Agent Signature: ______________    Date: 07 October 2026",
]


def form_docx() -> bytes:
    document = WordDocument()
    for line in TITLE:
        document.add_paragraph(line)
    for heading, rows in SECTIONS:
        document.add_paragraph(heading)
        table = document.add_table(rows=0, cols=2)
        for label, value in rows:
            cells = table.add_row().cells
            cells[0].text, cells[1].text = label, value
    for line in FOOTER:
        document.add_paragraph(line)
    out = BytesIO()
    document.save(out)
    return out.getvalue()


def form_pdf() -> bytes:
    """What a PDF of the form reads as: each row is "Label Value", no colon."""
    lines = [*TITLE]
    for heading, rows in SECTIONS:
        lines.append(heading)
        lines += [f"{label} {value}" for label, value in rows]
    return build.text_pdf(lines + FOOTER)


EXPECTED = {
    "property_title": "Azure Heights Village",
    "full_name": "Daniel Joseph Navarro",
    "co_buyer": "Elena Marie Navarro",
    "contact_number": "0920-555-1842",
    "email": "daniel.navarro@example.com",
    "agent_name": "Daniel Flores",
    "phone_number": "0917-321-8844",
    "agent_email": "daniel.flores@example.com",
    "agent_location": "Bacoor Sales Office",
    "reference_number": "TRX-20261007-18425",
    "block_lot": "Block 18, Lot 6",
}


def test_table_form_fields_from_word_and_pdf():
    for kind, content in (("DOCX", form_docx()), ("PDF", form_pdf())):
        labeled = extract_labeled_fields(extract_text(kind, content).text)
        assert labeled.conflicts == {}, kind
        values = normalize_fields(labeled.values).values
        for name, expected in EXPECTED.items():
            assert values.get(name) == expected, (kind, name, values.get(name))
        assert str(values["amount"]) == "50000.00", kind
        assert values["transaction_date"].date().isoformat() == "2026-10-07", kind


def test_transaction_time_is_read_as_philippine_time():
    cases = {
        "October 7, 2026": "2026-10-07T00:00:00+00:00",          # date only: no time stated
        "October 7, 2026 2:30 PM": "2026-10-07T06:30:00+00:00",  # 2:30 PM PHT = 06:30 UTC
        "10/07/2026 14:30": "2026-10-07T06:30:00+00:00",
        "07 October 2026, 9 am": "2026-10-07T01:00:00+00:00",
    }
    for raw, expected in cases.items():
        assert parse_date(raw).isoformat() == expected, raw
    # a separate time row joins the date; an unreadable one is ignored
    joined = normalize_fields({"transaction_date": "October 7, 2026", "transaction_time": "2:30 PM"})
    assert joined.values["transaction_date"].isoformat() == "2026-10-07T06:30:00+00:00"
    ignored = normalize_fields({"transaction_date": "October 7, 2026", "transaction_time": "TBD"})
    assert ignored.invalid == {} and ignored.values["transaction_date"].isoformat() == "2026-10-07T00:00:00+00:00"


def test_reservation_time_is_recorded(api, admin, agents, db):
    assert_success(upload(api, admin, "property.docx", build.docx(build.PROPERTY_LINES)))
    lines = [line.replace("September 30, 2026", "September 30, 2026 3:45 PM") for line in build.RESERVATION_LINES]
    doc = upload(api, admin, "reservation.docx", build.docx(lines))
    assert_success(doc)
    assert doc["extracted_fields"]["transaction_date"] == "2026-09-30 3:45 PM"
    transaction = api.get("/api/v1/transactions", headers=admin).json()[0]
    stored = datetime.fromisoformat(transaction["transaction_date"])
    assert stored == datetime(2026, 9, 30, 7, 45, tzinfo=timezone.utc)  # 3:45 PM PHT


def test_prose_is_not_read_as_a_field():
    # "Buyer requests …" is a sentence, not "Buyer: requests …".
    labeled = extract_labeled_fields("Buyer requests a corner unit\nProperty of the month")
    assert labeled.values == {}


def test_reservation_form_records_the_reservation(api, admin, agents, db):
    assert_success(upload(api, admin, "property.docx", build.docx(build.PROPERTY_LINES)))
    doc = upload(api, admin, "reservation-form.docx", form_docx())
    processing = assert_success(doc)
    assert doc["document_type"] == "RESERVATION_AGREEMENT"
    assert processing["matched_entities"]["property"]["matched_by"] == "PROJECT"
    assert processing["matched_entities"]["agent"]["id"] == "AGT-0006"
    assert doc["folder_path"] == "Buyers / Daniel Joseph Navarro"
    client = db.execute(select(Client)).unique().scalar_one()
    assert client.full_name == "Daniel Joseph Navarro"
    transaction = db.execute(select(PropertyTransaction)).scalar_one()
    assert transaction.transaction_type == "RESERVED" and float(transaction.amount) == 50_000


def test_unknown_property_and_agent_are_reported_together(api, admin, agents):
    lines = [*TITLE]
    for heading, rows in SECTIONS:
        lines.append(heading)
        lines += [f"{label} {'Mark Del Rosario' if label == 'Property Consultant' else value}"
                  for label, value in rows]
    pdf = build.text_pdf(lines + FOOTER)
    doc = upload(api, admin, "reservation-form.pdf", pdf)
    assert doc["status"] == "FAILED"
    assert doc["processing"]["stage"] == "ENTITY_MATCHING"
    reason = doc["processing_error"]
    assert "No property is titled 'Azure Heights Village'" in reason
    assert "Agent name 'Mark Del Rosario' matches 0 agents" in reason
