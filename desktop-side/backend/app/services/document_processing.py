"""Document-first processing: EXTRACTION -> CLASSIFICATION -> VALIDATION ->
ENTITY_MATCHING -> DUPLICATE_CHECK -> DATABASE_WRITE -> COMPLETE.

All database writes for one document happen inside a SAVEPOINT; any failure
rolls them back and the document is marked FAILED with the stage and the
exact reason. Re-processing the same content is idempotent: existing records
are matched and reported, never duplicated.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.models.client import Client
from app.models.document import Document
from app.models.property_listing import PropertyListing
from app.models.transaction import PropertyTransaction
from app.services import entity_matching as matching
from app.services.document_classification import (
    AUTO,
    DOCUMENT_TYPES,
    FINANCIAL_TYPES,
    canonical_type,
    classify,
)
from app.services.document_extraction import (
    ExtractionError,
    extract_labeled_fields,
    extract_text,
    format_ph_datetime,
    jsonable_fields,
    normalize_fields,
    normalize_name,
    ph_day,
)
from app.services.document_validation import validate
from app.services.entity_matching import Match, MatchError

logger = logging.getLogger(__name__)

EXTRACTION = "EXTRACTION"
CLASSIFICATION = "CLASSIFICATION"
VALIDATION = "VALIDATION"
ENTITY_MATCHING = "ENTITY_MATCHING"
DUPLICATE_CHECK = "DUPLICATE_CHECK"
DATABASE_WRITE = "DATABASE_WRITE"
COMPLETE = "COMPLETE"

# Fields where two different stated values make the document ambiguous.
_CRITICAL_FIELDS = {
    "listing_id", "client_id", "agent_id", "transaction_id", "reservation_id",
    "amount", "transaction_date", "transaction_type", "full_name",
}
# Generic declared types that defer to a more specific detected type.
_GENERIC_TYPES = {"CONTRACT", "TRANSACTION_DOCUMENT", "OTHER"}
_SALE_TYPES = {"SALE_AGREEMENT", "DEED"}

PROPERTY_FIELD_MAP = {
    "property_title": "title", "category": "category", "price_total": "price_total",
    "initial_dp": "initial_dp", "monthly_rate": "monthly_rate",
    "num_bedrooms": "num_bedrooms", "num_bathrooms": "num_bathrooms",
    "layout_type": "layout_type", "village_name": "village_name",
    "latitude": "lat", "longitude": "lng", "amenities": "amenity_list",
    "nearby_places": "nearby_places", "nearby_establishments": "nearby_establishments",
    "has_balcony": "has_balcony", "has_kitchen": "has_kitchen",
    "has_backyard": "has_backyard", "has_garage": "has_garage",
    "garage_spaces": "garage_spaces", "details": "details",
}
CLIENT_FIELD_MAP = {
    "address": "location", "contact_number": "phone_number", "email": "email",
    "occupation": "occupation", "civil_status": "civil_status",
    "preferred_contact": "preferred_contact", "purpose_of_purchase": "purpose_of_purchase",
}
AGENT_FIELD_MAP = {
    "phone_number": "phone_number", "contact_number": "phone_number",
    "agent_location": "agent_location", "latitude": "latitude", "longitude": "longitude",
    "star_rating": "star_rating", "assignments_count": "assignments_count",
    "transactions_count": "transactions_count", "completed_sales": "completed_sales",
    "total_sales": "total_sales", "total_commission": "total_commission",
    "performance_score": "performance_score",
}
MANUAL_PROPERTY_STATUSES = {"AVAILABLE", "ON_HOLD", "UNAVAILABLE"}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class ProcessingError(ValueError):
    def __init__(self, stage: str, message: str, fields: list[str] | None = None):
        super().__init__(message)
        self.stage = stage
        self.fields = fields or []


@dataclass
class Context:
    """Shared by document processing and website submissions so both follow
    the same client/transaction/property-lifecycle rules."""

    db: Session
    document: Document | None
    document_type: str
    fields: dict[str, Any]
    result: dict
    links: dict[str, Any] = field(default_factory=dict)
    events: list[dict] = field(default_factory=list)
    source: str = "DOCUMENT"

    @property
    def source_document_id(self) -> str | None:
        return self.document.document_id if self.document is not None else None

    def created(self, table: str, record_id: Any, action: str, details: dict | None = None) -> None:
        self.result["created_records"].append(f"{table}:{record_id}")
        self.events.append({"action": action, "entity_type": table, "entity_id": str(record_id),
                            "details": details or {}})

    def updated(self, table: str, record_id: Any, action: str, changes: dict) -> None:
        self.result["updated_records"].append(f"{table}:{record_id}")
        if changes:
            self.result["changes"][f"{table}:{record_id}"] = changes
        self.events.append({"action": action, "entity_type": table, "entity_id": str(record_id),
                            "details": {"changes": changes}})

    def matched(self, entity: str, match: Match, key: str) -> None:
        self.result["matched_entities"][entity] = match.describe(key)

    def warn(self, message: str) -> None:
        self.result["warnings"].append(message)


def _jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _same(old: Any, new: Any) -> bool:
    if isinstance(old, (int, float, Decimal)) and isinstance(new, (int, float, Decimal)):
        return Decimal(str(old)) == Decimal(str(new))
    if isinstance(old, str) and isinstance(new, str):
        return " ".join(old.split()).casefold() == " ".join(new.split()).casefold()
    return old == new


def new_result(document: Document | None, filename: str | None, declared_type: str | None) -> dict:
    return {
        "document_id": document.document_id if document is not None else None,
        "filename": filename,
        "declared_type": declared_type,
        "document_type": None,
        "classification": None,
        "status": "FAILED",
        "stage": EXTRACTION,
        "error_reason": None,
        "extraction": None,
        "extracted_fields": {},
        "field_conflicts": {},
        "validation_result": {"valid": False, "errors": []},
        "matched_entities": {},
        "created_records": [],
        "updated_records": [],
        "changes": {},
        "warnings": [],
        "idempotent": False,
        "processed_at": None,
    }


# ---------------------------------------------------------------------------
# Entity writers
# ---------------------------------------------------------------------------

def _apply_property(ctx: Context) -> PropertyListing:
    db, fields = ctx.db, ctx.fields
    reference = str(fields["listing_id"]).strip()
    listing = matching.find_property_by_reference(db, reference)
    stated_status = fields.get("status")

    if listing is None:
        if reference.isdecimal():
            raise ProcessingError(
                ENTITY_MATCHING,
                f"Property {reference} not found. Numeric IDs refer to existing listings; "
                "use a listing code (for example PROP-0001) for a new property.",
                ["listing_id"],
            )
        if stated_status and stated_status not in MANUAL_PROPERTY_STATUSES:
            raise ProcessingError(
                VALIDATION,
                f"A new property cannot start as {stated_status}; RESERVED and SOLD are set "
                "by reservation and sale documents.",
                ["status"],
            )
        values = {
            column: fields[key] for key, column in PROPERTY_FIELD_MAP.items() if key in fields
        }
        listing = PropertyListing(
            external_listing_id=reference,
            status=stated_status or "AVAILABLE",
            photos=fields.get("photos"),
            sync_status="PENDING",
            status_changed_at=_utcnow(),
            **values,
        )
        db.add(listing)
        db.flush()
        ctx.result["matched_entities"]["property"] = {"id": str(listing.listing_id), "matched_by": "CREATED"}
        ctx.created("property_listings", listing.listing_id, "PROPERTY_CREATED",
                    {"external_listing_id": reference, "status": listing.status})
        return listing

    ctx.matched("property", Match(listing, "LISTING_ID"), "listing_id")
    if fields.get("property_title") and listing.title and not _same(listing.title, fields["property_title"]):
        raise ProcessingError(
            ENTITY_MATCHING,
            f"Property {reference} is '{listing.title}', but the document names "
            f"'{fields['property_title']}'",
            ["property_title"],
        )
    changes: dict[str, dict] = {}
    for key, column in PROPERTY_FIELD_MAP.items():
        if key not in fields:
            continue
        old, new = getattr(listing, column), fields[key]
        if old is None or not _same(old, new):
            changes[column] = {"old": _jsonable(old), "new": _jsonable(new)}
            setattr(listing, column, new)
    if fields.get("photos"):
        merged = list(listing.photos or [])
        added = [url for url in fields["photos"] if url not in merged]
        if added:
            changes["photos"] = {"added": added}
            listing.photos = merged + added
    if stated_status and stated_status != listing.status:
        has_activity = matching.active_reservations(db, listing.listing_id) or matching.completed_sale(
            db, listing.listing_id
        )
        if stated_status in MANUAL_PROPERTY_STATUSES and listing.status in MANUAL_PROPERTY_STATUSES \
                and not has_activity:
            changes["status"] = {"old": listing.status, "new": stated_status}
            listing.status = stated_status
            listing.status_changed_at = _utcnow()
        else:
            ctx.warn(
                f"Stated status {stated_status} was not applied: the property is "
                f"{listing.status} and RESERVED/SOLD status is controlled by transactions."
            )
    if changes:
        listing.sync_status = "PENDING"
        ctx.updated("property_listings", listing.listing_id, "PROPERTY_UPDATED", changes)
    else:
        ctx.result["idempotent"] = True
    return listing


def _apply_client(ctx: Context, match: Match | None, listing: PropertyListing | None,
                  agent: Agent | None) -> Client:
    fields = ctx.fields
    if match is None:
        client = Client(
            external_client_id=fields.get("client_id"),
            full_name=fields["full_name"],
            property_id=listing.listing_id if listing else None,
            agent_id=agent.agent_id if agent else None,
            status="PROSPECT",
            source=ctx.source,
            sync_status="PENDING",
            **{column: fields[key] for key, column in CLIENT_FIELD_MAP.items() if key in fields},
        )
        ctx.db.add(client)
        ctx.db.flush()
        ctx.result["matched_entities"]["client"] = {"id": client.client_id, "matched_by": "CREATED"}
        ctx.created("clients", client.client_id, "CLIENT_CREATED",
                    {"full_name": client.full_name, "external_client_id": client.external_client_id})
        return client

    client = match.record
    ctx.matched("client", match, "client_id")
    changes: dict[str, dict] = {}
    candidates = dict(CLIENT_FIELD_MAP, client_id="external_client_id")
    for key, column in candidates.items():
        if key not in fields:
            continue
        old, new = getattr(client, column), fields[key]
        if old in (None, ""):
            changes[column] = {"old": None, "new": new}
            setattr(client, column, new)
        elif not _same(old, new):
            ctx.warn(f"Client {column} kept as '{old}' (document states '{new}')")
    if listing is not None and client.property_id is None:
        changes["property_id"] = {"old": None, "new": listing.listing_id}
        client.property_id = listing.listing_id
    if agent is not None and client.agent_id is None:
        changes["agent_id"] = {"old": None, "new": agent.agent_id}
        client.agent_id = agent.agent_id
    elif agent is not None and client.agent_id != agent.agent_id:
        ctx.warn(f"Client remains assigned to agent {client.agent_id}; this document names {agent.agent_id}")
    if changes:
        client.sync_status = "PENDING"
        ctx.updated("clients", client.client_id, "CLIENT_UPDATED", changes)
    return client


def apply_transaction(ctx: Context, transaction_type: str) -> None:
    db, fields = ctx.db, ctx.fields
    # Match property and agent independently so one message names everything
    # that is missing (e.g. both an unknown project and an unknown consultant).
    found: dict[str, Any] = {}
    problems: list[MatchError] = []
    for entity, find in (("property", matching.match_property), ("agent", matching.match_agent)):
        try:
            found[entity] = find(db, fields)
        except MatchError as exc:
            problems.append(exc)
    if problems:
        raise ProcessingError(ENTITY_MATCHING, "; ".join(str(p) for p in problems),
                              [name for p in problems for name in p.fields])
    try:
        client_match = matching.match_client(db, fields)
    except MatchError as exc:
        raise ProcessingError(ENTITY_MATCHING, str(exc), exc.fields) from exc
    listing, agent = found["property"].record, found["agent"].record
    ctx.result["matched_entities"]["property"] = {"id": str(listing.listing_id),
                                                  "matched_by": found["property"].method}
    ctx.result["matched_entities"]["agent"] = {"id": agent.agent_id, "matched_by":
                                               "AGENT_ID" if fields.get("agent_id") else "AGENT_NAME"}
    if str(agent.status or "").upper() not in {"ACTIVE", ""}:
        ctx.warn(f"Agent {agent.agent_id} status is {agent.status}")

    date: datetime = fields["transaction_date"]
    amount: Decimal = fields["amount"]
    reference = fields.get("transaction_id")
    if transaction_type == "RESERVED" and not reference:
        reference = fields.get("reservation_id")

    # -- DUPLICATE_CHECK: an explicit reference that already exists ---------
    if reference:
        existing = matching.find_transaction_by_reference(db, reference)
        if existing is not None:
            client = existing.client
            if client_match is not None and client_match.record.client_id != client.client_id:
                raise ProcessingError(
                    DUPLICATE_CHECK,
                    f"Transaction {reference} already belongs to client '{client.full_name}'",
                    ["transaction_id"],
                )
            if existing.property_id != listing.listing_id or existing.transaction_type != transaction_type:
                raise ProcessingError(
                    DUPLICATE_CHECK,
                    f"Transaction {reference} already exists for property {existing.property_id} "
                    f"as {existing.transaction_type}",
                    ["transaction_id"],
                )
            if existing.amount != amount or ph_day(existing.transaction_date) != ph_day(date):
                raise ProcessingError(
                    DUPLICATE_CHECK,
                    f"Transaction {reference} already exists with amount {existing.amount} on "
                    f"{format_ph_datetime(existing.transaction_date)}; the document states {amount} on "
                    f"{format_ph_datetime(date)}",
                    ["amount", "transaction_date"],
                )
            ctx.result["matched_entities"]["client"] = {"id": client.client_id, "matched_by": "TRANSACTION"}
            ctx.result["matched_entities"]["transaction"] = {"id": existing.transaction_id,
                                                             "matched_by": "TRANSACTION_ID"}
            ctx.result["idempotent"] = True
            _link(ctx, listing=listing, client=client, transaction=existing)
            return

    client = _apply_client(ctx, client_match, listing, agent)

    # -- DUPLICATE_CHECK: same live transaction already recorded -----------
    existing = matching.active_transaction(db, client.client_id, listing.listing_id, transaction_type)
    if existing is not None:
        if reference and existing.external_transaction_id and existing.external_transaction_id != reference:
            raise ProcessingError(
                DUPLICATE_CHECK,
                f"Client '{client.full_name}' already has {transaction_type} transaction "
                f"{existing.external_transaction_id} for this property",
                ["transaction_id"],
            )
        if existing.amount != amount:
            raise ProcessingError(
                DUPLICATE_CHECK,
                f"Client '{client.full_name}' already has a {transaction_type} transaction for this "
                f"property with amount {existing.amount}; the document states {amount}",
                ["amount"],
            )
        if reference and not existing.external_transaction_id:
            existing.external_transaction_id = reference
            existing.sync_status = "PENDING"
            ctx.updated("transactions", existing.transaction_id, "TRANSACTION_UPDATED",
                        {"external_transaction_id": {"old": None, "new": reference}})
        else:
            ctx.result["idempotent"] = not ctx.result["created_records"] and not ctx.result["updated_records"]
        ctx.result["matched_entities"]["transaction"] = {"id": existing.transaction_id,
                                                         "matched_by": "CLIENT_PROPERTY_TYPE"}
        _link(ctx, listing=listing, client=client, transaction=existing)
        return

    # -- property lifecycle rules -------------------------------------------
    status = listing.status
    reservations = matching.active_reservations(db, listing.listing_id)
    if transaction_type == "RESERVED":
        if status != "AVAILABLE":
            holder = f" by client {reservations[0].client.full_name}" if reservations else ""
            raise ProcessingError(
                ENTITY_MATCHING,
                f"Property {listing.external_listing_id or listing.listing_id} is {status}{holder}; "
                "a reservation requires an AVAILABLE property",
                ["listing_id"],
            )
    else:
        if status not in {"AVAILABLE", "RESERVED"}:
            raise ProcessingError(
                ENTITY_MATCHING,
                f"Property {listing.external_listing_id or listing.listing_id} is {status}; "
                "a sale requires an AVAILABLE or RESERVED property",
                ["listing_id"],
            )
        others = [item for item in reservations if item.client_id != client.client_id]
        if others:
            raise ProcessingError(
                ENTITY_MATCHING,
                f"Property is reserved by another client ('{others[0].client.full_name}')",
                ["listing_id"],
            )
        if status == "RESERVED" and not reservations:
            ctx.warn("Property was RESERVED without a recorded reservation transaction")
        reservation_reference = fields.get("reservation_id")
        if reservation_reference:
            reservation = matching.find_transaction_by_reference(db, reservation_reference)
            if reservation is None or reservation.client_id != client.client_id \
                    or reservation.property_id != listing.listing_id:
                raise ProcessingError(
                    ENTITY_MATCHING,
                    f"Reservation {reservation_reference} not found for this client and property",
                    ["reservation_id"],
                )

    transaction = PropertyTransaction(
        external_transaction_id=reference,
        client_id=client.client_id,
        property_id=listing.listing_id,
        agent_id=agent.agent_id,
        transaction_type=transaction_type,
        transaction_date=date,
        amount=amount,
        status="RESERVED" if transaction_type == "RESERVED" else "COMPLETED",
        source=ctx.source,
        source_document_id=ctx.source_document_id,
        sync_status="PENDING",
    )
    db.add(transaction)
    db.flush()
    ctx.result["matched_entities"]["transaction"] = {"id": transaction.transaction_id, "matched_by": "CREATED"}
    ctx.created("transactions", transaction.transaction_id, "TRANSACTION_CREATED",
                {"type": transaction_type, "amount": str(amount), "property_id": listing.listing_id,
                 "client_id": client.client_id, "external_transaction_id": reference})

    if transaction_type == "SOLD":
        for reservation in reservations:  # preserved; the reservation is fulfilled
            if reservation.client_id == client.client_id:
                reservation.status = "COMPLETED"
                reservation.sync_status = "PENDING"
                ctx.updated("transactions", reservation.transaction_id, "TRANSACTION_UPDATED",
                            {"status": {"old": "RESERVED", "new": "COMPLETED"}})

    old_status = listing.status
    listing.status = transaction_type
    listing.status_changed_at = _utcnow()
    listing.sync_status = "PENDING"
    ctx.updated("property_listings", listing.listing_id, "PROPERTY_STATUS_CHANGED",
                {"status": {"old": old_status, "new": transaction_type}})

    client.transaction_type = transaction_type
    client.status = transaction_type
    client.transaction_date = date
    client.property_id = listing.listing_id
    if client.agent_id is None:
        client.agent_id = agent.agent_id
    client.sync_status = "PENDING"
    _link(ctx, listing=listing, client=client, transaction=transaction)


def _apply_agent(ctx: Context) -> None:
    fields = ctx.fields
    agent_id = str(fields["agent_id"]).strip()
    name = fields.get("full_name") or fields.get("agent_name")
    agent = ctx.db.get(Agent, agent_id)
    status = fields.get("agent_status") or fields.get("status")
    if agent is None:
        agent = Agent(agent_id=agent_id, full_name=name, status=status or "ACTIVE", sync_status="PENDING")
        for key, column in AGENT_FIELD_MAP.items():
            if key in fields and getattr(agent, column, None) is None:
                setattr(agent, column, fields[key])
        ctx.db.add(agent)
        ctx.db.flush()
        ctx.result["matched_entities"]["agent"] = {"id": agent_id, "matched_by": "CREATED"}
        ctx.created("agents", agent_id, "AGENT_CREATED", {"full_name": name})
    else:
        ctx.matched("agent", Match(agent, "AGENT_ID"), "agent_id")
        if normalize_name(agent.full_name) != normalize_name(name):
            raise ProcessingError(
                ENTITY_MATCHING,
                f"Agent {agent_id} is '{agent.full_name}', but the document names '{name}'",
                ["full_name"],
            )
        changes: dict[str, dict] = {}
        updates = {column: fields[key] for key, column in AGENT_FIELD_MAP.items() if key in fields}
        if status:
            updates["status"] = status
        for column, new in updates.items():
            old = getattr(agent, column)
            if old is None or not _same(old, new):
                changes[column] = {"old": _jsonable(old), "new": _jsonable(new)}
                setattr(agent, column, new)
        if changes:
            agent.sync_status = "PENDING"
            ctx.updated("agents", agent_id, "AGENT_UPDATED", changes)
        else:
            ctx.result["idempotent"] = True
    ctx.links.update(related_party_name=agent.full_name, related_party_external_id=agent.agent_id)


def _apply_buyer(ctx: Context) -> None:
    if ctx.fields.get("transaction_type") in {"RESERVED", "SOLD"}:
        apply_transaction(ctx, ctx.fields["transaction_type"])
        return
    db, fields = ctx.db, ctx.fields
    try:
        listing_match = matching.match_property(db, fields, required=False)
        agent_match = matching.match_agent(db, fields, required=False)
        client_match = matching.match_client(db, fields)
    except MatchError as exc:
        raise ProcessingError(ENTITY_MATCHING, str(exc), exc.fields) from exc
    listing = listing_match.record if listing_match else None
    agent = agent_match.record if agent_match else None
    if listing_match:
        ctx.matched("property", listing_match, "listing_id")
    if agent_match:
        ctx.matched("agent", agent_match, "agent_id")
    client = _apply_client(ctx, client_match, listing, agent)
    ctx.result["idempotent"] = not ctx.result["created_records"] and not ctx.result["updated_records"]
    _link(ctx, listing=listing, client=client)


def _apply_links_only(ctx: Context, *, property_required: bool) -> None:
    """Seller, financial and generic documents: resolve and link references."""
    db, fields = ctx.db, ctx.fields
    try:
        listing_match = matching.match_property(db, fields, required=property_required)
    except MatchError as exc:
        raise ProcessingError(ENTITY_MATCHING, str(exc), exc.fields) from exc
    listing = listing_match.record if listing_match else None
    if listing_match:
        ctx.matched("property", listing_match, "listing_id")
    transaction = None
    reference = fields.get("transaction_id") or fields.get("reservation_id")
    if reference:
        transaction = matching.find_transaction_by_reference(db, reference)
        if transaction is None:
            raise ProcessingError(ENTITY_MATCHING, f"Transaction {reference} not found", ["transaction_id"])
        if listing is not None and transaction.property_id != listing.listing_id:
            raise ProcessingError(
                ENTITY_MATCHING,
                f"Transaction {reference} belongs to property {transaction.property_id}, "
                f"not {listing.listing_id}",
                ["listing_id"],
            )
        ctx.result["matched_entities"]["transaction"] = {"id": transaction.transaction_id,
                                                         "matched_by": "TRANSACTION_ID"}
        listing = listing or transaction.property_listing
    client = None
    if fields.get("client_id"):
        client = matching.find_client_by_external_reference(db, fields["client_id"])
        if client is None:
            raise ProcessingError(ENTITY_MATCHING, f"Client {fields['client_id']} not found", ["client_id"])
        ctx.result["matched_entities"]["client"] = {"id": client.client_id, "matched_by": "CLIENT_ID"}
    elif transaction is not None:
        client = transaction.client
    party = fields.get("seller_name") or fields.get("payer") or fields.get("full_name")
    _link(ctx, listing=listing, client=client, transaction=transaction, party=party)
    ctx.result["idempotent"] = True  # linking documents never changes business records


def _link(ctx: Context, *, listing: PropertyListing | None = None, client: Client | None = None,
          transaction: PropertyTransaction | None = None, party: str | None = None) -> None:
    if listing is not None:
        ctx.links.update(
            property_listing_id=listing.listing_id,
            property_listing_external_id=listing.external_listing_id or str(listing.listing_id),
            property_listing_title=listing.title,
        )
    if client is not None:
        ctx.links.update(
            related_party_name=client.full_name,
            related_party_external_id=client.external_client_id or client.client_id,
        )
    elif party:
        ctx.links["related_party_name"] = party
    if transaction is not None:
        ctx.links["transaction_reference"] = (
            transaction.external_transaction_id or transaction.transaction_id
        )


def _dispatch(ctx: Context) -> None:
    document_type = ctx.document_type
    if document_type == "PROPERTY_INFORMATION":
        listing = _apply_property(ctx)
        _link(ctx, listing=listing)
    elif document_type == "BUYER_DOCUMENT":
        _apply_buyer(ctx)
    elif document_type == "RESERVATION_AGREEMENT":
        apply_transaction(ctx, "RESERVED")
    elif document_type in _SALE_TYPES:
        apply_transaction(ctx, "SOLD")
    elif document_type == "TRANSACTION_DOCUMENT":
        apply_transaction(ctx, ctx.fields["transaction_type"])
    elif document_type == "CONTRACT" and ctx.fields.get("transaction_type"):
        apply_transaction(ctx, ctx.fields["transaction_type"])
    elif document_type == "AGENT_INFORMATION":
        _apply_agent(ctx)
    elif document_type == "SELLER_DOCUMENT":
        _apply_links_only(ctx, property_required=True)
    elif document_type in FINANCIAL_TYPES or document_type == "CONTRACT":
        _apply_links_only(ctx, property_required=False)
    elif document_type == "OTHER":
        ctx.warn("OTHER documents are stored without business-record processing")
        ctx.result["idempotent"] = True
    else:  # pragma: no cover - registry and dispatcher must stay aligned
        raise ProcessingError(CLASSIFICATION, f"No processor is defined for {document_type}")


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def _resolve_type(declared: str | None, detected: str | None, confidence: str) -> str:
    if declared in (None, AUTO):
        if detected is None:
            raise ProcessingError(
                CLASSIFICATION,
                "The document type could not be determined from its content. "
                "Upload it again choosing the document type explicitly.",
            )
        return detected
    if detected is None or detected == declared:
        return declared
    if declared in _GENERIC_TYPES:
        return detected
    if {declared, detected} <= _SALE_TYPES:
        return declared
    if confidence == "HIGH":
        raise ProcessingError(
            CLASSIFICATION,
            f"The document was uploaded as {declared}, but its content is a {detected} "
            f"({DOCUMENT_TYPES[detected][0]}).",
        )
    return declared


def process_document_content(
    db: Session,
    document: Document,
    filename: str,
    content: bytes,
    *,
    source_format: str,
    declared_type: str | None = None,
) -> dict:
    """Process stored document bytes. Never raises for document problems."""
    result = new_result(document, filename, declared_type)
    events: list[dict] = []
    stage = EXTRACTION
    try:
        extraction = extract_text(source_format, content)
        result["extraction"] = extraction.summary()
        document.extraction_method = extraction.method
        document.source_format = extraction.source_format

        labeled = extract_labeled_fields(extraction.text)
        normalized = normalize_fields(labeled.values)
        fields = normalized.values
        result["extracted_fields"] = jsonable_fields(fields)
        result["field_conflicts"] = labeled.conflicts

        stage = CLASSIFICATION
        classification = classify(extraction.text, fields)
        result["classification"] = {
            "detected_type": classification.document_type,
            "confidence": classification.confidence,
            "reason": classification.reason,
        }
        document_type = _resolve_type(
            canonical_type(declared_type), classification.document_type, classification.confidence
        )
        result["document_type"] = document_type
        document.document_type = document_type

        stage = VALIDATION
        validation = validate(document_type, fields, normalized.invalid)
        for name, values in labeled.conflicts.items():
            if name in _CRITICAL_FIELDS:
                validation.add(name, "the document states different values: " + ", ".join(values))
        result["validation_result"] = validation.as_dict()
        if not validation.valid:
            raise ProcessingError(VALIDATION, validation.summary(), validation.fields)

        stage = ENTITY_MATCHING
        context = Context(db, document, document_type, fields, result)
        savepoint = db.begin_nested()
        try:
            _dispatch(context)
            db.flush()
        except Exception:
            savepoint.rollback()
            raise
        savepoint.commit()
        for key, value in context.links.items():
            setattr(document, key, value)
        events = context.events
        result.update(status="SUCCESS", stage=COMPLETE)
    except ExtractionError as exc:
        result.update(stage=EXTRACTION, error_reason=str(exc))
    except ProcessingError as exc:
        result.update(stage=exc.stage, error_reason=str(exc))
        if exc.fields and exc.stage != VALIDATION:
            result["validation_result"].setdefault("missing_or_invalid_fields", exc.fields)
    except MatchError as exc:
        result.update(stage=ENTITY_MATCHING, error_reason=str(exc))
    except IntegrityError as exc:
        reason = str(exc.orig).splitlines()[0] if exc.orig else str(exc)
        result.update(stage=DATABASE_WRITE, error_reason=f"Database constraint rejected the write: {reason}")
    except Exception as exc:  # unexpected defect: keep the exact exception
        logger.exception("Unexpected processing failure for document %s", document.document_id)
        result.update(stage=stage if stage != ENTITY_MATCHING else DATABASE_WRITE,
                      error_reason=f"Unexpected {type(exc).__name__}: {exc}")

    if result["status"] != "SUCCESS":
        result["matched_entities"] = result["matched_entities"] if result["stage"] == ENTITY_MATCHING else {}
        result["created_records"], result["updated_records"], result["changes"] = [], [], {}
        result["idempotent"] = False
        events = []

    now = _utcnow()
    result["processed_at"] = now.isoformat()
    document.status = result["status"]
    document.processing_stage = result["stage"]
    document.processing_error = result["error_reason"]
    document.processed_at = now
    result["entity_events"] = events
    return result
