"""Match extracted references to existing properties, agents, clients and
transactions.

Rules:
  * an explicit identifier that does not resolve is a failure, never a new
    record (except where the document type *defines* the entity, e.g. a
    Property Information document creating its listing);
  * fallbacks on names/contact details must be unambiguous;
  * contradicting evidence (id says A, email says B) is a failure.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.models.client import Client
from app.models.property_listing import PropertyListing
from app.models.transaction import PropertyTransaction
from app.services.document_extraction import normalize_name, normalize_phone_digits


class MatchError(ValueError):
    def __init__(self, entity: str, message: str, fields: list[str] | None = None):
        super().__init__(message)
        self.entity = entity
        self.fields = fields or []


@dataclass
class Match:
    record: Any
    method: str  # e.g. LISTING_ID, TITLE, AGENT_ID, EMAIL

    def describe(self, key: str) -> dict:
        return {"id": str(getattr(self.record, key)), "matched_by": self.method}


def _uuid(value: str) -> str | None:
    try:
        return str(UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        return None


# ---- property ----------------------------------------------------------------

def find_property_by_reference(db: Session, reference: str) -> PropertyListing | None:
    reference = reference.strip()
    listing = db.execute(
        select(PropertyListing).where(PropertyListing.external_listing_id == reference)
    ).scalar_one_or_none()
    if listing is None and reference.isdecimal():
        listing = db.get(PropertyListing, int(reference))
    return listing


def match_property(db: Session, fields: dict, *, required: bool = True) -> Match | None:
    reference = str(fields.get("listing_id") or "").strip()
    title = fields.get("property_title")
    if reference:
        listing = find_property_by_reference(db, reference)
        if listing is None:
            raise MatchError("property", f"Property {reference} not found", ["listing_id"])
        if title and listing.title and normalize_name(listing.title) != normalize_name(title):
            raise MatchError(
                "property",
                f"Property {reference} is '{listing.title}', but the document names '{title}'",
                ["property_title"],
            )
        return Match(listing, "LISTING_ID")
    if title:
        candidates = db.execute(
            select(PropertyListing).where(
                func.lower(func.trim(PropertyListing.title)) == title.strip().casefold()
            )
        ).scalars().all()
        village = fields.get("village_name")
        if village and len(candidates) > 1:
            candidates = [
                item for item in candidates
                if normalize_name(item.village_name) == normalize_name(village)
            ]
        if len(candidates) == 1:
            return Match(candidates[0], "TITLE")
        if len(candidates) > 1:
            raise MatchError(
                "property", f"Property title '{title}' matches {len(candidates)} listings; "
                "the document must state the Listing ID", ["listing_id"],
            )
        raise MatchError("property", f"No property is titled '{title}'", ["property_title"])
    if required:
        raise MatchError("property", "The document does not identify a property", ["listing_id"])
    return None


# ---- agent -------------------------------------------------------------------

def match_agent(db: Session, fields: dict, *, required: bool = True) -> Match | None:
    agent_id = str(fields.get("agent_id") or "").strip()
    name = fields.get("agent_name")
    if agent_id:
        agent = db.get(Agent, agent_id)
        if agent is None:
            raise MatchError("agent", f"Agent {agent_id} not found", ["agent_id"])
        if name and normalize_name(agent.full_name) != normalize_name(name):
            raise MatchError(
                "agent",
                f"Agent {agent_id} is '{agent.full_name}', but the document names '{name}'",
                ["agent_name"],
            )
        return Match(agent, "AGENT_ID")
    if name:
        candidates = [
            agent for agent in db.execute(select(Agent)).scalars()
            if normalize_name(agent.full_name) == normalize_name(name)
        ]
        if len(candidates) == 1:
            return Match(candidates[0], "AGENT_NAME")
        raise MatchError(
            "agent",
            f"Agent name '{name}' matches {len(candidates)} agents; the document must state the Agent ID",
            ["agent_id"],
        )
    if required:
        raise MatchError("agent", "The document does not identify an agent", ["agent_id"])
    return None


# ---- client ------------------------------------------------------------------

def _identity_candidates(db: Session, email: str | None, phone: str | None,
                         name: str | None, address: str | None) -> dict[str, list[Client]]:
    found: dict[str, list[Client]] = {}
    if email:
        found["EMAIL"] = db.execute(
            select(Client).where(func.lower(Client.email) == email.casefold())
        ).scalars().all()
    digits = normalize_phone_digits(phone)
    if len(digits) >= 7:
        found["PHONE"] = [
            client for client in db.execute(
                select(Client).where(Client.phone_number.is_not(None))
            ).scalars()
            if normalize_phone_digits(client.phone_number) == digits
        ]
    if name and address:
        found["NAME_ADDRESS"] = [
            client for client in db.execute(
                select(Client).where(Client.location.is_not(None))
            ).scalars()
            if normalize_name(client.full_name) == normalize_name(name)
            and normalize_name(client.location) == normalize_name(address)
        ]
    return {key: value for key, value in found.items() if value}


def match_client(db: Session, fields: dict) -> Match | None:
    """Return the existing client, or None when the document describes a new one."""
    external_id = str(fields.get("client_id") or "").strip() or None
    name = fields.get("full_name")
    by_id = None
    if external_id:
        by_id = db.execute(
            select(Client).where(Client.external_client_id == external_id)
        ).scalar_one_or_none()
        if by_id is None and _uuid(external_id):
            by_id = db.get(Client, _uuid(external_id))

    candidates = _identity_candidates(
        db, fields.get("email"), fields.get("contact_number"), name, fields.get("address")
    )
    identity_matches = {client.client_id: client for group in candidates.values() for client in group}

    if by_id is not None:
        others = [client for key, client in identity_matches.items() if key != by_id.client_id]
        if others:
            raise MatchError(
                "client",
                f"Client {external_id} conflicts with existing client '{others[0].full_name}' "
                "who has the same contact details",
                ["client_id"],
            )
        if name and normalize_name(by_id.full_name) != normalize_name(name):
            raise MatchError(
                "client",
                f"Client {external_id} is '{by_id.full_name}', but the document names '{name}'",
                ["full_name"],
            )
        return Match(by_id, "CLIENT_ID")

    if not identity_matches:
        return None
    if len(identity_matches) > 1:
        raise MatchError(
            "client",
            "The client's contact details match more than one existing client",
            ["email", "contact_number"],
        )
    client = next(iter(identity_matches.values()))
    method = next(key for key, group in candidates.items() if client in group)
    if name and normalize_name(client.full_name) != normalize_name(name):
        raise MatchError(
            "client",
            f"The contact details belong to existing client '{client.full_name}', "
            f"not '{name}'",
            ["full_name"],
        )
    if external_id and client.external_client_id and client.external_client_id != external_id:
        raise MatchError(
            "client",
            f"Existing client '{client.full_name}' has ID {client.external_client_id}, "
            f"but the document states {external_id}",
            ["client_id"],
        )
    return Match(client, method)


def find_client_by_external_reference(db: Session, reference: str) -> Client | None:
    client = db.execute(
        select(Client).where(Client.external_client_id == reference)
    ).scalar_one_or_none()
    if client is None and _uuid(reference):
        client = db.get(Client, _uuid(reference))
    return client


# ---- transaction ---------------------------------------------------------------

def find_transaction_by_reference(db: Session, reference: str) -> PropertyTransaction | None:
    reference = reference.strip()
    transaction = db.execute(
        select(PropertyTransaction).where(
            PropertyTransaction.external_transaction_id == reference
        )
    ).scalar_one_or_none()
    if transaction is None and _uuid(reference):
        transaction = db.get(PropertyTransaction, _uuid(reference))
    return transaction


def active_transaction(db: Session, client_id: str, property_id: int,
                       transaction_type: str) -> PropertyTransaction | None:
    return db.execute(
        select(PropertyTransaction).where(
            PropertyTransaction.client_id == client_id,
            PropertyTransaction.property_id == property_id,
            PropertyTransaction.transaction_type == transaction_type,
            PropertyTransaction.status != "CANCELLED",
        )
    ).scalar_one_or_none()


def active_reservations(db: Session, property_id: int) -> list[PropertyTransaction]:
    return db.execute(
        select(PropertyTransaction).where(
            PropertyTransaction.property_id == property_id,
            PropertyTransaction.transaction_type == "RESERVED",
            PropertyTransaction.status == "RESERVED",
        )
    ).scalars().all()


def completed_sale(db: Session, property_id: int) -> PropertyTransaction | None:
    return db.execute(
        select(PropertyTransaction).where(
            PropertyTransaction.property_id == property_id,
            PropertyTransaction.transaction_type == "SOLD",
            PropertyTransaction.status != "CANCELLED",
        )
    ).scalars().first()


__all__ = [
    "Match", "MatchError", "match_property", "match_agent", "match_client",
    "find_property_by_reference", "find_client_by_external_reference",
    "find_transaction_by_reference", "active_transaction", "active_reservations",
    "completed_sale",
]
