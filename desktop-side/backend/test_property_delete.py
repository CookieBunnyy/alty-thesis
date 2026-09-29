from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.v1.property_listings import delete_property_listing


def test_property_delete_with_transaction_history_returns_conflict():
    class FakeDb:
        deleted = False

        def get(self, _model, _listing_id):
            return SimpleNamespace(listing_id=27, sync_status="PENDING")

        def scalar(self, _statement):
            return 1

        def delete(self, _listing):
            self.deleted = True

    db = FakeDb()

    with pytest.raises(HTTPException) as error:
        delete_property_listing(27, db, SimpleNamespace(id=1))

    assert error.value.status_code == 409
    assert "transaction history" in error.value.detail
    assert not db.deleted