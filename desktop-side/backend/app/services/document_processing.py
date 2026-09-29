from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import re
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.models.client import Client
from app.models.document import Document
from app.models.property_listing import PropertyListing
from app.models.transaction import PropertyTransaction
from app.services.document_extraction import classify_and_extract


class ProcessingError(ValueError):
    def __init__(self, message: str, missing_fields: list[str] | None = None):
        super().__init__(message)
        self.missing_fields = missing_fields or []


def _required(fields: dict, names: list[str]) -> None:
    missing = [name for name in names if fields.get(name) in (None, "")]
    if missing:
        raise ProcessingError(
            "Required fields are missing or invalid: " + ", ".join(missing), missing
        )


def _document_id(value: str) -> str | None:
    try:
        return str(UUID(value))
    except (ValueError, TypeError, AttributeError):
        return None


def _normalized_name(value: str | None) -> str:
    return " ".join((value or "").casefold().split())


def _property(db: Session, fields: dict) -> tuple[PropertyListing, bool]:
    external_id = str(fields.get("listing_id") or "").strip()
    _required(fields, ["listing_id", "property_title", "category"])
    status = str(fields.get("status") or "AVAILABLE").upper().replace(" ", "_")
    if status not in {"AVAILABLE", "RESERVED", "SOLD", "ON_HOLD", "UNAVAILABLE"}:
        raise ProcessingError("status is invalid", ["status"])
    for field_name in ("price_total", "initial_dp", "monthly_rate"):
        if fields.get(field_name) is not None and fields[field_name] < 0:
            raise ProcessingError(f"{field_name} must not be negative", [field_name])
    if fields.get("latitude") is not None and not -90 <= fields["latitude"] <= 90:
        raise ProcessingError("latitude is outside the valid range", ["latitude"])
    if fields.get("longitude") is not None and not -180 <= fields["longitude"] <= 180:
        raise ProcessingError("longitude is outside the valid range", ["longitude"])

    listing = db.execute(
        select(PropertyListing).where(PropertyListing.external_listing_id == external_id)
    ).scalar_one_or_none()
    if listing is None and external_id.isdecimal():
        listing = db.get(PropertyListing, int(external_id))
    if listing is not None:
        return listing, False

    values = {
        "title": fields["property_title"],
        "category": fields["category"],
        "price_total": fields.get("price_total"),
        "initial_dp": fields.get("initial_dp"),
        "monthly_rate": fields.get("monthly_rate"),
        "num_bedrooms": fields.get("num_bedrooms"),
        "num_bathrooms": fields.get("num_bathrooms"),
        "layout_type": fields.get("layout_type"),
        "village_name": fields.get("village_name"),
        "lat": fields.get("latitude"),
        "lng": fields.get("longitude"),
        "amenity_list": fields.get("amenities"),
        "nearby_places": fields.get("nearby_places"),
        "nearby_establishments": fields.get("nearby_establishments"),
        "has_balcony": fields.get("has_balcony"),
        "has_kitchen": fields.get("has_kitchen"),
        "has_backyard": fields.get("has_backyard"),
        "has_garage": fields.get("has_garage"),
        "garage_spaces": fields.get("garage_spaces"),
        "details": fields.get("details"),
        "status": status,
        "external_listing_id": external_id,
        "sync_status": "PENDING",
    }
    listing = PropertyListing(**values)
    db.add(listing)
    db.flush()
    return listing, True


def _client(db: Session, fields: dict, listing_id: int, agent_id: str) -> tuple[Client, bool]:
    external_id = str(fields.get("client_id") or "").strip() or None
    if external_id:
        client = db.execute(
            select(Client).where(Client.external_client_id == external_id)
        ).scalar_one_or_none()
        if client is None:
            primary_id = _document_id(external_id)
            if primary_id:
                client = db.get(Client, primary_id)
        if client is not None:
            if client.property_id != listing_id:
                raise ProcessingError("Matched client is already linked to a different property")
            if client.agent_id != agent_id:
                raise ProcessingError("Matched client has a different assigned agent")
            return client, False

    name = str(fields.get("full_name") or "").strip()
    email = str(fields.get("email") or "").strip().casefold() or None
    phone = str(fields.get("contact_number") or "").strip() or None
    address = str(fields.get("address") or "").strip() or None
    _required(fields, ["full_name"])
    identity_filters = []
    if email:
        identity_filters.append(func.lower(Client.email) == email)
    if phone:
        digits = re.sub(r"\D", "", phone)
        if digits:
            identity_filters.append(
                func.regexp_replace(Client.phone_number, "[^0-9]", "", "g") == digits
            )
    if address:
        identity_filters.append(
            (func.lower(Client.full_name) == _normalized_name(name))
            & (func.lower(Client.location) == _normalized_name(address))
        )
    matches = []
    if identity_filters:
        matches = db.execute(select(Client).where(or_(*identity_filters))).scalars().all()
    if len(matches) > 1:
        raise ProcessingError("Client identity matched multiple existing records")
    if matches:
        client = matches[0]
        if client.property_id != listing_id:
            raise ProcessingError("Matched client is already linked to a different property")
        if client.agent_id != agent_id:
            raise ProcessingError("Matched client has a different assigned agent")
        if external_id and not client.external_client_id:
            client.external_client_id = external_id
        if client.email is None:
            client.email = email
        if client.phone_number is None:
            client.phone_number = phone
        if client.location is None:
            client.location = address
        return client, False

    if not (email or phone or address):
        raise ProcessingError(
            "Cannot safely create or match a client without an email, contact number, or address"
        )
    values = {
        "external_client_id": external_id,
        "full_name": name,
        "location": address,
        "phone_number": phone,
        "email": email,
        "agent_id": agent_id,
        "property_id": listing_id,
        "transaction_type": "RESERVED",
        "status": "RESERVED",
        "transaction_date": None,
    }
    primary_id = _document_id(external_id) if external_id else None
    if primary_id:
        values["client_id"] = primary_id
    client = Client(**values)
    db.add(client)
    db.flush()
    return client, True


def _transaction_date(value: str) -> datetime:
    candidate = value.strip()
    try:
        parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
    except ValueError:
        parsed = None
        for pattern in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"):
            try:
                parsed = datetime.strptime(candidate, pattern)
                break
            except ValueError:
                continue
        if parsed is None:
            raise ProcessingError("transaction_date is invalid", ["transaction_date"])
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed


def _process_transaction(
    db: Session, fields: dict, document_type: str, listing: PropertyListing
) -> tuple[Client, PropertyTransaction, bool, bool]:
    _required(fields, ["agent_id", "transaction_date", "amount"])
    agent_id = str(fields["agent_id"]).strip()
    agent = db.get(Agent, agent_id)
    if agent is None:
        raise ProcessingError(f"No agent exists with agent_id {agent_id}", ["agent_id"])
    try:
        amount = Decimal(str(fields["amount"]))
    except InvalidOperation as exc:
        raise ProcessingError("amount is invalid", ["amount"]) from exc
    if amount < 0:
        raise ProcessingError("amount must not be negative", ["amount"])

    transaction_type = "RESERVED" if document_type == "RESERVATION_AGREEMENT" else "SOLD"
    declared_type = str(fields.get("transaction_type") or "").upper().replace(" ", "_")
    if declared_type and declared_type not in {
        transaction_type,
        "RESERVATION" if transaction_type == "RESERVED" else "SALE",
    }:
        raise ProcessingError("transaction_type conflicts with document classification", ["transaction_type"])
    declared_status = str(fields.get("transaction_status") or "").upper().replace(" ", "_")
    allowed_statuses = {"RESERVED"} if transaction_type == "RESERVED" else {"SOLD", "COMPLETED"}
    if declared_status and declared_status not in allowed_statuses:
        raise ProcessingError("transaction_status conflicts with document classification", ["transaction_status"])
    if fields.get("agent_name") and _normalized_name(agent.full_name) != _normalized_name(str(fields["agent_name"])):
        raise ProcessingError("agent_name does not match the agent_id record", ["agent_name"])
    if fields.get("property_title") and listing.title and _normalized_name(listing.title) != _normalized_name(str(fields["property_title"])):
        raise ProcessingError("property_title does not match the listing_id record", ["property_title"])

    date = _transaction_date(str(fields["transaction_date"]))
    client, client_created = _client(db, fields, listing.listing_id, agent_id)
    external_id = str(fields.get("transaction_id") or "").strip() or None
    transaction = None
    if external_id:
        transaction = db.execute(select(PropertyTransaction).where(
            PropertyTransaction.external_transaction_id == external_id
        )).scalar_one_or_none()
        if transaction is None:
            primary_id = _document_id(external_id)
            if primary_id:
                transaction = db.get(PropertyTransaction, primary_id)
    if transaction is not None:
        if transaction.property_id != listing.listing_id or transaction.client_id != client.client_id:
            raise ProcessingError("transaction_id is already used for different entities")
        if (
            transaction.agent_id != agent_id
            or transaction.transaction_type != transaction_type
            or transaction.transaction_date != date
            or transaction.amount != amount
        ):
            raise ProcessingError("transaction_id is already used for different transaction details")
        return client, transaction, client_created, False

    transaction = db.execute(select(PropertyTransaction).where(
        PropertyTransaction.client_id == client.client_id,
        PropertyTransaction.property_id == listing.listing_id,
        PropertyTransaction.transaction_type == transaction_type,
        PropertyTransaction.transaction_date == date,
        PropertyTransaction.amount == amount,
    )).scalar_one_or_none()
    if transaction is not None:
        return client, transaction, client_created, False

    client.transaction_type = transaction_type
    client.status = transaction_type
    client.transaction_date = date
    transaction_status = "RESERVED" if transaction_type == "RESERVED" else "COMPLETED"
    transaction_values = {
        "external_transaction_id": external_id,
        "client_id": client.client_id,
        "property_id": listing.listing_id,
        "agent_id": agent_id,
        "transaction_type": transaction_type,
        "transaction_date": date,
        "amount": amount,
        "status": transaction_status,
    }
    primary_id = _document_id(external_id) if external_id else None
    if primary_id:
        transaction_values["transaction_id"] = primary_id
    transaction = PropertyTransaction(**transaction_values)
    db.add(transaction)
    listing.status = transaction_type
    listing.sync_status = "PENDING"
    listing.last_synced_at = None
    db.flush()
    return client, transaction, client_created, True


def process_document_content(
    db: Session, document: Document, filename: str, content: bytes
) -> dict:
    processed_at = datetime.now(timezone.utc).isoformat()
    result = {
        "document_id": document.document_id,
        "filename": filename,
        "document_type": None,
        "status": "FAILED",
        "extracted_fields": {},
        "validation_result": {"valid": False},
        "matched_entities": {},
        "created_records": [],
        "updated_records": [],
        "error_reason": None,
        "processed_at": processed_at,
    }
    try:
        document_type, fields = classify_and_extract(filename, content)
    except Exception as exc:
        result["error_reason"] = f"Text extraction failed: {exc}"
        return result
    result["document_type"] = document_type or None
    result["extracted_fields"] = {
        name: str(value) if isinstance(value, Decimal) else value
        for name, value in fields.items()
    }
    if not document_type:
        result["error_reason"] = "Document content could not be classified"
        return result
    document.document_type = document_type
    if fields.get("listing_id"):
        document.property_listing_external_id = str(fields["listing_id"])
    if fields.get("property_title"):
        document.property_listing_title = str(fields["property_title"])
    if fields.get("full_name"):
        document.related_party_name = str(fields["full_name"])
    if fields.get("client_id"):
        document.related_party_external_id = str(fields["client_id"])
    if fields.get("transaction_id"):
        document.transaction_reference = str(fields["transaction_id"])
    elif fields.get("transaction_type"):
        document.transaction_reference = str(fields["transaction_type"])

    matched_document_fields: dict[str, object] = {}
    savepoint = db.begin_nested()
    try:
        if document_type == "PROPERTY_INFORMATION":
            listing, created = _property(db, fields)
            result["matched_entities"]["property"] = listing.listing_id
            matched_document_fields.update({
                "property_listing_id": listing.listing_id,
                "property_listing_external_id": str(
                    fields.get("listing_id") or listing.external_listing_id or listing.listing_id
                ),
                "property_listing_title": listing.title,
            })
            (result["created_records"] if created else result["updated_records"]).append(
                f"property_listings:{listing.listing_id}"
            )
            if not created:
                for key, field_name in {
                    "property_title": "title", "category": "category", "price_total": "price_total",
                    "initial_dp": "initial_dp", "monthly_rate": "monthly_rate",
                    "num_bedrooms": "num_bedrooms", "num_bathrooms": "num_bathrooms",
                    "layout_type": "layout_type", "village_name": "village_name",
                    "latitude": "lat", "longitude": "lng", "amenities": "amenity_list",
                    "nearby_places": "nearby_places", "nearby_establishments": "nearby_establishments",
                    "has_balcony": "has_balcony", "has_kitchen": "has_kitchen",
                    "has_backyard": "has_backyard", "has_garage": "has_garage",
                    "garage_spaces": "garage_spaces", "details": "details", "status": "status",
                }.items():
                    if key in fields:
                        setattr(listing, field_name, fields[key])
        elif document_type == "AGENT_INFORMATION":
            if "full_name" not in fields and fields.get("agent_name"):
                fields["full_name"] = fields["agent_name"]
            _required(fields, ["agent_id", "full_name"])
            agent_id = str(fields["agent_id"]).strip()
            agent = db.get(Agent, agent_id)
            created = agent is None
            if created:
                agent = Agent(agent_id=agent_id, full_name=str(fields["full_name"]).strip())
                db.add(agent)
            values = {
                "full_name": "full_name", "phone_number": "phone_number",
                "contact_number": "phone_number", "agent_location": "agent_location",
                "latitude": "latitude", "longitude": "longitude", "star_rating": "star_rating",
                "assignments_count": "assignments_count", "transactions_count": "transactions_count",
                "completed_sales": "completed_sales", "total_sales": "total_sales",
                "total_commission": "total_commission", "performance_score": "performance_score",
                "status": "status",
            }
            for key, field_name in values.items():
                if key in fields:
                    setattr(agent, field_name, fields[key])
            db.flush()
            result["matched_entities"]["agent"] = agent.agent_id
            matched_document_fields.update({
                "related_party_name": agent.full_name,
                "related_party_external_id": agent.agent_id,
            })
            (result["created_records"] if created else result["updated_records"]).append(
                f"agents:{agent.agent_id}"
            )
        else:
            _required(fields, ["listing_id"])
            external_id = str(fields["listing_id"]).strip()
            listing = db.execute(select(PropertyListing).where(
                PropertyListing.external_listing_id == external_id
            )).scalar_one_or_none()
            if listing is None and external_id.isdecimal():
                listing = db.get(PropertyListing, int(external_id))
            if listing is None:
                raise ProcessingError(
                    f"No property exists with listing_id {external_id}. "
                    "Process a PROPERTY_INFORMATION document for this listing before its agreement.",
                    ["property_match"],
                )
            result["matched_entities"]["property"] = listing.listing_id
            client, transaction, client_created, transaction_created = _process_transaction(
                db, fields, document_type, listing
            )
            result["matched_entities"].update({
                "client": client.client_id,
                "agent": client.agent_id,
                "transaction": transaction.transaction_id,
            })
            matched_document_fields.update({
                "property_listing_id": listing.listing_id,
                "property_listing_external_id": external_id,
                "property_listing_title": listing.title,
                "transaction_reference": str(
                    fields.get("transaction_id") or transaction.transaction_id
                ),
                "related_party_name": client.full_name,
                "related_party_external_id": str(
                    fields.get("client_id") or client.external_client_id or client.client_id
                ),
            })
            if client_created:
                result["created_records"].append(f"clients:{client.client_id}")
            else:
                result["updated_records"].append(f"clients:{client.client_id}")
            if transaction_created:
                result["created_records"].append(f"transactions:{transaction.transaction_id}")
                result["updated_records"].append(f"property_listings:{listing.listing_id}:status")

        db.flush()
        savepoint.commit()
        for field, value in matched_document_fields.items():
            setattr(document, field, value)
        result["status"] = "SUCCESS"
        result["validation_result"] = {"valid": True}
    except Exception as exc:
        savepoint.rollback()
        result["error_reason"] = str(exc)
        result["matched_entities"] = {}
        result["created_records"] = []
        result["updated_records"] = []
        result["validation_result"] = {
            "valid": False,
            "missing_or_invalid_fields": getattr(exc, "missing_fields", []),
        }
    return result