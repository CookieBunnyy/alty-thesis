from types import SimpleNamespace

from app.api.v1 import property_listings as property_listings_api
from app.models.property_listing import PropertyListing
from app.services import property_listing_sync as property_listing_sync_service


class SyncResult:
    def __init__(self, record=None):
        self.record = record

    def scalar_one_or_none(self):
        return self.record


class FakeDb:
    def __init__(self, existing=None):
        self.existing = existing
        self.execute_count = 0
        self.added = []
        self.committed = False
        self.rolled_back = False

    def execute(self, _statement):
        self.execute_count += 1
        if self.execute_count == 1:
            return SyncResult(self.existing)
        return SyncResult()

    def add(self, record):
        self.added.append(record)

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


class FakeSupabase:
    def __init__(self, rows):
        self.rows = rows

    def table(self, _table_name):
        return self

    def select(self, _columns):
        return self

    def execute(self):
        return SimpleNamespace(data=self.rows)


def _cloud_listing(status="AVAILABLE"):
    return {
        "listing_id": 804,
        "external_listing_id": "PROP-TEST-0804",
        "title": "Cloud Test Property",
        "category": "Townhouse",
        "status": status,
    }


def test_cloud_listing_is_imported_to_local_cache(monkeypatch):
    monkeypatch.setattr(
        property_listings_api, "supabase", FakeSupabase([_cloud_listing()])
    )
    db = FakeDb()

    result = property_listings_api.sync_property_listings(db)

    listing = next(record for record in db.added if isinstance(record, PropertyListing))
    assert result == {"total": 1, "inserted": 1, "updated": 0, "errors": 0}
    assert listing.listing_id == 804
    assert listing.external_listing_id == "PROP-TEST-0804"
    assert listing.sync_status == "SYNCED"
    assert db.committed


def test_cloud_refresh_preserves_pending_document_reservation(monkeypatch):
    pending = SimpleNamespace(
        listing_id=804,
        external_listing_id="PROP-TEST-0804",
        title="Document Test Property",
        category="Townhouse",
        status="RESERVED",
        sync_status="PENDING",
    )
    monkeypatch.setattr(
        property_listings_api, "supabase", FakeSupabase([_cloud_listing()])
    )
    db = FakeDb(existing=pending)

    result = property_listings_api.sync_property_listings(db)

    assert result == {"total": 1, "inserted": 0, "updated": 1, "errors": 0}
    assert pending.status == "RESERVED"
    assert pending.title == "Document Test Property"
    assert pending.sync_status == "PENDING"
    assert db.committed


def test_client_sync_listing_service_preserves_pending_reservation(monkeypatch):
    pending = SimpleNamespace(
        listing_id=804,
        external_listing_id="PROP-TEST-0804",
        title="Document Test Property",
        category="Townhouse",
        status="RESERVED",
        sync_status="PENDING",
        last_synced_at=None,
    )

    class ServiceDb(FakeDb):
        def execute(self, _statement):
            return SyncResult(pending)

    monkeypatch.setattr(
        property_listing_sync_service,
        "supabase",
        FakeSupabase([_cloud_listing(status="AVAILABLE")]),
    )
    monkeypatch.setattr(
        property_listing_sync_service,
        "reconcile_client_for_property",
        lambda _db, _listing: None,
    )
    db = ServiceDb()

    result = property_listing_sync_service.sync_property_listings(db)

    assert result == {"total": 1, "inserted": 0, "updated": 1, "errors": 0}
    assert pending.status == "RESERVED"
    assert pending.sync_status == "PENDING"
    assert db.committed