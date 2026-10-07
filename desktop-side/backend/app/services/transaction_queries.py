"""Shared loading options for transaction lists.

A transaction row needs its client, property and agent names. Loading them in
the same query (instead of one query per row) matters because every query is
a network round trip to the database. The client's own transaction history
(loaded automatically elsewhere) is not needed in a list, so it is skipped.
"""

from sqlalchemy.orm import joinedload, lazyload

from app.models.client import Client
from app.models.transaction import PropertyTransaction

WITH_PARTIES = (
    joinedload(PropertyTransaction.client).options(lazyload(Client.transactions)),
    joinedload(PropertyTransaction.property_listing),
    joinedload(PropertyTransaction.agent),
)
