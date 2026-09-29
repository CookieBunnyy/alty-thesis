from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from app.models.agent import Agent
from app.models.document import DocumentAuditEvent
from app.models.property_listing import PropertyListing
from app.models.transaction import PropertyTransaction
from app.services import document_processing


class FakeResult:
    def __init__(self, record=None):
        self.record = record

    def scalar_one_or_none(self):
        return self.record


class FakeSavepoint:
    def __init__(self):
        self.rolled_back = False
        self.committed = False

    def rollback(self):
        self.rolled_back = True

    def commit(self):
        self.committed = True


class FakeSession:
    def __init__(self):
        self.added = []
        self.results = []
        self.savepoint = FakeSavepoint()

    def execute(self, _statement):
        return FakeResult(self.results.pop(0) if self.results else None)

    def add(self, record):
        self.added.append(record)

    def flush(self):
        for record in self.added:
            if isinstance(record, PropertyListing) and record.listing_id is None:
                record.listing_id = 901
            if isinstance(record, PropertyTransaction) and record.transaction_id is None:
                record.transaction_id = str(uuid4())

    def begin_nested(self):
        return self.savepoint

    def get(self, model, identifier):
        if model is Agent:
            names = {
                "AGT-0006": "Daniel Flores",
                "AGT-0007": "Patricia Ramos",
            }
            return SimpleNamespace(agent_id=identifier, full_name=names[identifier])
        return None


def test_property_document_creates_available_listing_and_json_safe_audit(monkeypatch):
    fields = {
        "listing_id": "PROP-TEST-0001",
        "property_title": "Test Property",
        "category": "Townhouse",
        "price_total": Decimal("3500000.00"),
    }
    monkeypatch.setattr(
        document_processing,
        "classify_and_extract",
        lambda _filename, _content: ("PROPERTY_INFORMATION", fields),
    )
    db = FakeSession()
    document = SimpleNamespace(document_id="document-1", document_type="Other")

    result = document_processing.process_document_content(
        db, document, "property.docx", b"test"
    )

    listing = next(record for record in db.added if isinstance(record, PropertyListing))
    assert result["status"] == "SUCCESS"
    assert result["created_records"] == ["property_listings:901"]
    assert listing.external_listing_id == "PROP-TEST-0001"
    assert listing.status == "AVAILABLE"
    assert document.property_listing_id == 901
    assert document.property_listing_external_id == "PROP-TEST-0001"
    assert document.property_listing_title == "Test Property"
    assert result["extracted_fields"]["price_total"] == "3500000.00"
    assert db.savepoint.committed


def test_invalid_property_document_rolls_back_without_partial_records(monkeypatch):
    monkeypatch.setattr(
        document_processing,
        "classify_and_extract",
        lambda _filename, _content: (
            "PROPERTY_INFORMATION",
            {"property_title": "Missing ID", "category": "Townhouse"},
        ),
    )
    db = FakeSession()
    document = SimpleNamespace(document_id="document-2", document_type="Other")

    result = document_processing.process_document_content(
        db, document, "property.docx", b"test"
    )

    assert result["status"] == "FAILED"
    assert "listing_id" in result["validation_result"]["missing_or_invalid_fields"]
    assert not db.added
    assert db.savepoint.rolled_back


def test_same_client_can_receive_reservation_then_sale(monkeypatch):
    client = SimpleNamespace(
        client_id="CLI-TEST-0001",
        property_id=901,
        agent_id="AGT-0006",
        transaction_type="RESERVED",
        status="RESERVED",
        transaction_date=None,
    )
    monkeypatch.setattr(
        document_processing,
        "_client",
        lambda _db, _fields, _listing_id, _agent_id: (client, False),
    )
    db = FakeSession()
    listing = SimpleNamespace(listing_id=901, title="Test Property", status="AVAILABLE")
    shared_fields = {
        "client_id": "CLI-TEST-0001",
        "full_name": "Taylor Example",
        "listing_id": "PROP-TEST-0001",
        "property_title": "Test Property",
        "agent_id": "AGT-0006",
        "agent_name": "Daniel Flores",
        "transaction_date": "2026-09-12T10:00:00+08:00",
        "amount": Decimal("50000.00"),
    }

    _, reservation, _, reservation_created = document_processing._process_transaction(
        db,
        {**shared_fields, "transaction_id": "RES-TEST-0001", "transaction_type": "RESERVED"},
        "RESERVATION_AGREEMENT",
        listing,
    )
    _, sale, _, sale_created = document_processing._process_transaction(
        db,
        {**shared_fields, "transaction_id": "TRX-TEST-0001", "transaction_type": "SOLD"},
        "SALE_AGREEMENT",
        listing,
    )
    db.results.append(sale)
    _, repeated_sale, _, repeated_sale_created = document_processing._process_transaction(
        db,
        {**shared_fields, "transaction_id": "TRX-TEST-0001", "transaction_type": "SOLD"},
        "SALE_AGREEMENT",
        listing,
    )

    assert reservation_created and sale_created
    assert not repeated_sale_created
    assert repeated_sale is sale
    assert len([record for record in db.added if isinstance(record, PropertyTransaction)]) == 2
    assert reservation.client_id == sale.client_id == client.client_id
    assert reservation.external_transaction_id == "RES-TEST-0001"
    assert sale.external_transaction_id == "TRX-TEST-0001"
    assert reservation.status == "RESERVED"
    assert sale.status == "COMPLETED"
    assert client.status == "SOLD"
    assert listing.status == "SOLD"


def test_reservation_processing_populates_repository_match_fields(monkeypatch):
    client = SimpleNamespace(
        client_id="e31e28ae-e0e8-468a-8427-4726dd51de5c",
        external_client_id="CLI-TEST-0004",
        full_name="Carla Villanueva",
        property_id=901,
        agent_id="AGT-0007",
        transaction_type="RESERVED",
        status="RESERVED",
        transaction_date=None,
    )
    listing = SimpleNamespace(
        listing_id=901,
        external_listing_id="PROP-TEST-0004",
        title="Test Property - Lakeside Garden Homes",
        status="AVAILABLE",
    )
    monkeypatch.setattr(
        document_processing,
        "classify_and_extract",
        lambda _filename, _content: (
            "RESERVATION_AGREEMENT",
            {
                "listing_id": "PROP-TEST-0004",
                "property_title": "Test Property - Lakeside Garden Homes",
                "client_id": "CLI-TEST-0004",
                "full_name": "Carla Villanueva",
                "agent_id": "AGT-0007",
                "agent_name": "Patricia Ramos",
                "transaction_type": "RESERVATION",
                "transaction_date": "2026-09-30",
                "amount": Decimal("125000.00"),
            },
        ),
    )
    monkeypatch.setattr(
        document_processing,
        "_client",
        lambda _db, _fields, _listing_id, _agent_id: (client, False),
    )
    db = FakeSession()
    db.results = [listing]
    document = SimpleNamespace(document_id="document-4", document_type="Other")

    result = document_processing.process_document_content(
        db, document, "reservation.docx", b"test"
    )

    assert result["status"] == "SUCCESS"
    assert document.property_listing_id == 901
    assert document.property_listing_external_id == "PROP-TEST-0004"
    assert document.property_listing_title == "Test Property - Lakeside Garden Homes"
    assert document.related_party_name == "Carla Villanueva"
    assert document.related_party_external_id == "CLI-TEST-0004"
    assert document.transaction_reference == result["matched_entities"]["transaction"]


def test_delete_document_removes_all_versions_and_writes_audit(monkeypatch):
    from app.api.v1 import documents as documents_api

    versions = [
        SimpleNamespace(id=4, document_id="document-old", version=2, storage_path="v2"),
        SimpleNamespace(id=3, document_id="document-old", version=1, storage_path="v1"),
    ]

    class VersionResult:
        def scalars(self):
            return self

        def all(self):
            return versions

    class FakeDeleteSession:
        def __init__(self):
            self.deleted = []
            self.added = []
            self.committed = False

        def execute(self, _statement):
            return VersionResult()

        def delete(self, record):
            self.deleted.append(record)

        def add(self, record):
            self.added.append(record)

        def commit(self):
            self.committed = True

    storage_paths = []
    metadata_versions = []
    monkeypatch.setattr(documents_api, "_require_filing_manager", lambda _actor: None)
    monkeypatch.setattr(
        documents_api,
        "remove_document_file",
        lambda path: storage_paths.append(path),
    )
    monkeypatch.setattr(
        documents_api,
        "delete_document_metadata",
        lambda version: metadata_versions.append(version.version),
    )
    db = FakeDeleteSession()

    response = documents_api.delete_document(
        "document-old", db=db, actor=SimpleNamespace(id=1, role="Administrator")
    )

    assert response.status_code == 204
    assert storage_paths == ["v2", "v1"]
    assert metadata_versions == [2, 1]
    assert db.deleted == versions
    assert isinstance(db.added[0], DocumentAuditEvent)
    assert db.added[0].event_type == "DOCUMENT_DELETED"
    assert db.committed