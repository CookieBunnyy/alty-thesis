from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

from app.services import client_sync
from app.services.client_sync import _client_values, reconcile_client_for_property


def test_client_sync_uses_property_sale_status_and_preserves_email() -> None:
    listing = SimpleNamespace(listing_id=5, status="SOLD")
    values = _client_values(
        {
            "client_id": str(uuid4()),
            "full_name": "Sample Client",
            "email": "SAMPLE@example.com",
            "agent_id": "AGT-0001",
            "property_id": 5,
            "transaction_type": "RESERVED",
            "status": "RESERVED",
            "transaction_date": "2026-08-12T10:00:00+08:00",
            "created_at": "2026-08-12T10:00:00+08:00",
        },
        listing,
        datetime(2026, 9, 29),
    )

    assert values["transaction_type"] == "SOLD"
    assert values["status"] == "SOLD"
    assert values["email"] == "sample@example.com"
    assert values["created_at"] == datetime(2026, 8, 12, 2, 0)


def test_sale_transition_completes_reservation_without_rewriting_history() -> None:
    reservation = SimpleNamespace(
        transaction_type="RESERVED",
        status="RESERVED",
    )
    completed_sale = SimpleNamespace(
        transaction_type="SOLD",
        status="COMPLETED",
    )
    client = SimpleNamespace(
        transaction_type="RESERVED",
        status="RESERVED",
        updated_at=None,
        transactions=[reservation, completed_sale],
    )
    db = Mock()
    db.execute.return_value.scalar_one_or_none.return_value = client

    reconcile_client_for_property(
        db,
        SimpleNamespace(listing_id=5, status="SOLD"),
    )

    assert client.transaction_type == "SOLD"
    assert client.status == "SOLD"
    assert reservation.transaction_type == "RESERVED"
    assert reservation.status == "COMPLETED"
    assert completed_sale.transaction_type == "SOLD"
    assert completed_sale.status == "COMPLETED"
    db.delete.assert_not_called()


def test_available_transition_cancels_active_transaction_only() -> None:
    reservation = SimpleNamespace(status="RESERVED")
    completed_sale = SimpleNamespace(status="COMPLETED")
    client = SimpleNamespace(
        property_id=5,
        status="RESERVED",
        updated_at=None,
        transactions=[reservation, completed_sale],
    )
    db = Mock()
    db.execute.return_value.scalar_one_or_none.return_value = client

    reconcile_client_for_property(
        db,
        SimpleNamespace(listing_id=5, status="AVAILABLE"),
    )

    assert client.status == "CANCELLED"
    assert reservation.status == "CANCELLED"
    assert completed_sale.status == "COMPLETED"
    db.delete.assert_not_called()


def test_client_sync_does_not_cancel_document_clients_missing_from_cloud(monkeypatch) -> None:
    class EmptyClientTable:
        def select(self, _columns):
            return self

        def execute(self):
            return SimpleNamespace(data=[])

    class FakeSupabase:
        def table(self, _table_name):
            return EmptyClientTable()

    class FakeDb:
        def commit(self):
            pass

    monkeypatch.setattr(
        client_sync.settings,
        "SUPABASE_URL",
        "https://supabase.example",
    )
    monkeypatch.setattr(client_sync.settings, "SUPABASE_SERVICE_ROLE_KEY", "test-key")
    monkeypatch.setattr(client_sync, "supabase", FakeSupabase())
    monkeypatch.setattr(client_sync, "sync_agents", lambda _db: {"errors": 0})
    monkeypatch.setattr(
        "app.services.property_listing_sync.sync_property_listings",
        lambda _db: {"errors": 0},
    )

    result = client_sync.sync_clients(FakeDb())

    assert result["cancelled"] == 0


def test_delete_client_removes_transactions_and_reopens_reserved_property(monkeypatch):
    from app.api.v1 import clients as clients_api
    from app.models.client import Client
    from app.models.property_listing import PropertyListing
    from app.models.transaction import PropertyTransaction

    transaction = SimpleNamespace(
        transaction_id="transaction-id",
        transaction_type="RESERVED",
    )
    client = SimpleNamespace(
        client_id="client-id",
        property_id=27,
        transactions=[transaction],
    )
    listing = SimpleNamespace(
        listing_id=27,
        status="RESERVED",
        sync_status="PENDING",
        last_synced_at=None,
    )

    class ScalarResult:
        def scalars(self):
            return self

        def all(self):
            return [transaction]

    class FakeDb:
        def __init__(self):
            self.deleted = []
            self.committed = False

        def get(self, model, _identifier):
            return client if model is Client else listing if model is PropertyListing else None

        def execute(self, _statement):
            return ScalarResult()

        def delete(self, record):
            self.deleted.append(record)

        def commit(self):
            self.committed = True

    monkeypatch.setattr(clients_api.settings, "SUPABASE_URL", "")
    monkeypatch.setattr(clients_api.settings, "SUPABASE_SERVICE_ROLE_KEY", "")
    db = FakeDb()

    response = clients_api.delete_client(
        "client-id", db=db, actor=SimpleNamespace(role="Administrator")
    )

    assert response.status_code == 204
    assert db.deleted == [transaction, client]
    assert listing.status == "AVAILABLE"
    assert listing.sync_status == "PENDING"
    assert db.committed
