"""Pull clients from Supabase and reconcile property status changes."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.supabase import supabase
from app.models.agent import Agent
from app.models.client import Client
from app.models.property_listing import PropertyListing
from app.models.transaction import PropertyTransaction
from app.services.agent_sync import sync_agents

CLIENT_STATUSES = {"PROSPECT", "RESERVED", "SOLD", "CANCELLED"}
OPTIONAL_TEXT = ("location", "phone_number", "occupation", "civil_status",
                 "preferred_contact", "purpose_of_purchase", "external_client_id")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _normalized_status(value: Any) -> str:
    return str(value or "").strip().upper().replace(" ", "_")


def _datetime_value(value: Any, fallback: datetime | None = None) -> datetime | None:
    if value is None or value == "":
        return fallback
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Invalid client timestamp") from exc


def cancel_reservation(reservation: PropertyTransaction, reason: str, cancelled_by: str) -> None:
    """Cancel one open reservation and record why, by whom and when.

    The reserving client's summary status follows (when it points at this
    property). The caller decides what happens to the property itself."""
    reservation.status = "CANCELLED"
    reservation.cancellation_reason = reason
    reservation.cancelled_at = _utcnow()
    reservation.cancelled_by = cancelled_by
    reservation.sync_status = "PENDING"
    client = reservation.client
    if client.property_id == reservation.property_id and client.status == "RESERVED":
        client.status = "CANCELLED"
        client.sync_status = "PENDING"


def reconcile_property_status(db: Session, listing: PropertyListing, old_status: str | None,
                              reason: str | None = None, cancelled_by: str | None = None) -> list[str]:
    """Apply the consequences of a property status change that did not come
    from a transaction (manual management edit or cloud pull).

    RESERVED -> AVAILABLE/ON_HOLD/UNAVAILABLE cancels the live reservation(s)
    and the reserving clients' summary status. Sales are never undone here.
    The reason is recorded on each cancelled reservation; without one, the
    status change itself is recorded as the reason.
    Returns human-readable notes describing what changed.
    """
    new_status = _normalized_status(listing.status)
    notes: list[str] = []
    if old_status == new_status:
        return notes
    listing.status_changed_at = _utcnow()
    if new_status in {"AVAILABLE", "ON_HOLD", "UNAVAILABLE"}:
        reservations = db.execute(
            select(PropertyTransaction).where(
                PropertyTransaction.property_id == listing.listing_id,
                PropertyTransaction.transaction_type == "RESERVED",
                PropertyTransaction.status == "RESERVED",
            )
        ).scalars().all()
        label = new_status.replace("_", " ").lower()
        why = (reason or "").strip() or f"The property was changed from reserved to {label}."
        for reservation in reservations:
            cancel_reservation(reservation, why, cancelled_by or "System")
            notes.append(f"reservation {reservation.transaction_id} cancelled: {why}")
    return notes


def _client_values(data: dict[str, Any], synced_at: datetime) -> dict[str, Any]:
    raw_client_id = str(data.get("client_id") or "").strip()
    try:
        client_id = str(UUID(raw_client_id))
    except ValueError as exc:
        raise ValueError("Client record has an invalid client_id") from exc
    full_name = str(data.get("full_name") or "").strip()
    if not full_name or len(full_name) > 200:
        raise ValueError("Client record has an invalid full_name")
    property_id = data.get("property_id")
    property_id = int(property_id) if property_id not in (None, "") else None
    agent_id = str(data.get("agent_id") or "").strip() or None
    transaction_type = _normalized_status(data.get("transaction_type")) or None
    if transaction_type not in {None, "RESERVED", "SOLD"}:
        raise ValueError("Client record has an invalid transaction_type")
    status = _normalized_status(data.get("status")) or "PROSPECT"
    if status not in CLIENT_STATUSES:
        raise ValueError("Client record has an invalid status")
    created_at = _datetime_value(data.get("created_at"), synced_at)
    if created_at is not None and created_at.tzinfo is not None:
        created_at = created_at.astimezone(timezone.utc).replace(tzinfo=None)
    values = {
        "client_id": client_id,
        "full_name": full_name,
        "email": str(data["email"]).strip().lower() if data.get("email") else None,
        "agent_id": agent_id,
        "property_id": property_id,
        "transaction_type": transaction_type,
        "transaction_date": _datetime_value(data.get("transaction_date")),
        "status": status,
        "created_at": created_at,
        "updated_at": synced_at,
        "sync_status": "SYNCED",
        "last_synced_at": synced_at,
    }
    for name in OPTIONAL_TEXT:
        if name in data:
            values[name] = str(data[name]).strip() if data.get(name) else None
    return values


def sync_clients(db: Session) -> dict[str, Any]:
    if not settings.cloud_configured:
        raise HTTPException(status_code=503, detail="Supabase is not configured on the server.")
    try:
        from app.services.property_listing_sync import sync_property_listings

        agent_sync = sync_agents(db)
        if agent_sync["errors"]:
            raise HTTPException(status_code=502, detail="Unable to refresh agent records before client sync.")
        property_sync = sync_property_listings(db)
        if property_sync["errors"]:
            raise HTTPException(status_code=502, detail="Unable to refresh property listings before client sync.")
        response = supabase.table("clients").select("*").execute()
    except HTTPException:
        raise
    except Exception as exc:
        message = str(exc).casefold()
        detail = (
            "Supabase denied access to public.clients. Grant the service_role access "
            "using the provided Supabase SQL script."
            if "42501" in message or "permission denied" in message
            else f"Unable to read public.clients from Supabase: {exc}"
        )
        raise HTTPException(status_code=502, detail=detail) from exc

    records = response.data or []
    synced_at = _utcnow()
    inserted = updated = skipped = errors = 0
    messages: list[str] = []
    for data in records:
        try:
            values = _client_values(data, synced_at)
        except (TypeError, ValueError) as exc:
            errors += 1
            messages.append(str(exc))
            continue
        if values["property_id"] is not None and db.get(PropertyListing, values["property_id"]) is None:
            errors += 1
            messages.append(f"client {values['client_id']}: property {values['property_id']} is not local")
            continue
        if values["agent_id"] is not None and db.get(Agent, values["agent_id"]) is None:
            errors += 1
            messages.append(f"client {values['client_id']}: agent {values['agent_id']} is not local")
            continue
        existing = db.get(Client, values["client_id"])
        if existing is None:
            db.add(Client(source="SYNC", **values))
            inserted += 1
        elif existing.sync_status == "PENDING":
            skipped += 1  # local change not yet pushed: never overwrite it
        else:
            for field, value in values.items():
                if field != "client_id":
                    setattr(existing, field, value)
            updated += 1
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Unable to save synchronized clients locally: {exc}") from exc
    return {
        "total": len(records), "inserted": inserted, "updated": updated,
        "skipped_pending": skipped, "cancelled": 0, "errors": errors,
        "error_messages": messages[:20], "last_synced_at": synced_at,
    }
