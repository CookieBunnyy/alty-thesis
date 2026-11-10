"""Commission vouchers in the document repository: classification, every
label/value pair kept, a configurable schema, human verification and
correction, and the link to the commission record."""

import pytest

from tests import documents as build
from tests.test_commissions import _sale
from tests.test_document_pipeline import upload

API = "/api/v1"
# Invented labels on purpose: ALTY must not assume the real voucher's wording.
VOUCHER = [
    "COMMISSION VOUCHER",
    "Voucher No.: CV-0912",
    "Payee: Angela Cruz",
    "Project: Acacia Estates Phase 2",
    "Gross Commission: PHP 84,000.00",
    "Released On: October 30, 2026",
]


@pytest.fixture
def empty_schema(api, admin):
    yield
    api.put(f"{API}/documents/schemas/COMMISSION_VOUCHER", headers=admin, json={"fields": []})


def test_voucher_is_read_for_review_and_linked_after_verification(api, admin, employee, agents, db, empty_schema):
    sale = _sale(api, admin, db)
    commission = api.post(f"{API}/commissions", headers=admin, json={"transaction_id": sale["transaction_id"],
                                                                     "amount": "84000"}).json()
    original = build.docx(VOUCHER)
    doc = upload(api, employee, "voucher.docx", original)
    assert doc["document_type"] == "COMMISSION_VOUCHER" and doc["processing_stage"] == "COMPLETE", doc
    assert doc["folder_path"] == "Commission Documents"
    path = f"{API}/documents/{doc['document_id']}/extraction"
    review = api.get(path, headers=employee).json()
    labels = {p["label"]: p["value"] for p in review["detected_pairs"]}
    assert labels["Voucher No."] == "CV-0912" and labels["Gross Commission"] == "PHP 84,000.00"
    assert review["schema"] == [] and review["mapped_fields"] == {}          # nothing assumed
    assert review["verification_status"] == "NEEDS_REVIEW"

    # Management configures the schema from a real sample; existing reads are re-mapped.
    schema = {"fields": [
        {"key": "voucher_number", "label": "Voucher No.", "required": True},
        {"key": "amount", "label": "Commission Amount", "aliases": ["Gross Commission"], "type": "money"},
        {"key": "payee", "label": "Payee"},
    ]}
    assert api.put(f"{API}/documents/schemas/COMMISSION_VOUCHER", headers=employee, json=schema).status_code == 403
    assert api.put(f"{API}/documents/schemas/COMMISSION_VOUCHER", headers=admin, json=schema).status_code == 200
    remapped = api.post(f"{path}/remap", headers=employee).json()
    assert remapped["mapped_fields"] == {"voucher_number": "CV-0912", "amount": "PHP 84,000.00",
                                         "payee": "Angela Cruz"}

    # A person corrects a misread value and links the commission; the original file is kept.
    assert api.put(path, headers=employee, json={"fields": {"not_a_field": "x"}}).status_code == 422
    verified = api.put(path, headers=employee, json={"fields": {"payee": "Angela P. Cruz"},
                                                     "commission_id": commission["id"]})
    assert verified.status_code == 200, verified.text
    body = verified.json()
    assert body["verification_status"] == "VERIFIED" and body["verified_fields"]["payee"] == "Angela P. Cruz"
    assert body["links"]["commission_id"] == commission["id"] and body["links"]["agent_id"] == sale["agent_id"]
    linked = api.get(f"{API}/commissions/{commission['id']}", headers=admin).json()
    assert linked["voucher"]["document_id"] == doc["document_id"]
    download = api.get(f"{API}/documents/{doc['document_id']}/download", headers=employee)
    assert download.status_code == 200 and download.content == original
    history = [e["event_type"] for e in api.get(f"{API}/documents/{doc['document_id']}/audit", headers=employee).json()]
    assert "DOCUMENT_VERIFIED" in history


def test_required_schema_fields_block_verification(api, admin, employee, agents, db, empty_schema):
    api.put(f"{API}/documents/schemas/COMMISSION_VOUCHER", headers=admin, json={"fields": [
        {"key": "approved_by", "label": "Approved By", "required": True}]})
    doc = upload(api, employee, "voucher2.docx", build.docx(VOUCHER[:3]))
    path = f"{API}/documents/{doc['document_id']}/extraction"
    refused = api.put(path, headers=employee, json={"fields": {}})
    assert refused.status_code == 422 and "Approved By" in refused.json()["detail"]
    assert api.put(path, headers=employee, json={"fields": {"approved_by": "M. Abellar"}}).json()["verification_status"] == "VERIFIED"
