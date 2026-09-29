from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

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

CLIENT_STATUSES = {"RESERVED", "SOLD"}


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


def reconcile_client_for_property(
    db: Session, listing: PropertyListing
) -> None:
    client = db.execute(
        select(Client).where(Client.property_id == listing.listing_id)
    ).scalar_one_or_none()
    if client is None:
        return

    property_status = _normalized_status(listing.status)
    if property_status not in CLIENT_STATUSES:
        client.status = "CANCELLED"
        for transaction in client.transactions:
            if transaction.status == "RESERVED":
                transaction.status = "CANCELLED"
    else:
        client.transaction_type = property_status
        client.status = property_status
        if property_status == "SOLD":
            for transaction in client.transactions:
                if transaction.status == "RESERVED":
                    transaction.status = "COMPLETED"
    client.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)


def _client_values(
    data: dict[str, Any], listing: PropertyListing, synced_at: datetime
) -> dict[str, Any]:
    raw_client_id = str(data.get("client_id") or "").strip()
    try:
        client_id = str(UUID(raw_client_id)) if raw_client_id else str(uuid4())
    except ValueError as exc:
        raise ValueError("Client record has an invalid client_id") from exc

    try:
        property_id = int(data.get("property_id"))
    except (TypeError, ValueError) as exc:
        raise ValueError("Client record has an invalid property_id") from exc

    full_name = str(data.get("full_name") or "").strip()
    if not full_name or len(full_name) > 200:
        raise ValueError("Client record has an invalid full_name")
    if property_id != listing.listing_id:
        raise ValueError("Client property_id does not match its listing")

    agent_id = str(data.get("agent_id") or "").strip()
    if not agent_id or len(agent_id) > 32:
        raise ValueError("Client record has an invalid agent_id")

    property_status = _normalized_status(listing.status)
    transaction_type = _normalized_status(data.get("transaction_type"))
    if property_status in CLIENT_STATUSES:
        transaction_type = property_status
        status = property_status
    else:
        if transaction_type not in CLIENT_STATUSES:
            raise ValueError("Client record has an invalid transaction_type")
        status = _normalized_status(data.get("status"))
        if status not in {"RESERVED", "SOLD", "CANCELLED"}:
            status = "CANCELLED"

    created_at = _datetime_value(data.get("created_at"), synced_at)
    if created_at is not None and created_at.tzinfo is not None:
        created_at = created_at.astimezone(timezone.utc).replace(tzinfo=None)

    values = {
        "client_id": client_id,
        "full_name": full_name,
        "location": str(data["location"]).strip() if data.get("location") else None,
        "phone_number": (
            str(data["phone_number"]).strip()
            if data.get("phone_number")
            else None
        ),
        "email": str(data["email"]).strip().lower() if data.get("email") else None,
        "agent_id": agent_id,
        "property_id": property_id,
        "transaction_type": transaction_type,
        "transaction_date": _datetime_value(data.get("transaction_date")),
        "status": status,
        "created_at": created_at,
        "updated_at": synced_at,
    }
    if data.get("external_client_id"):
        values["external_client_id"] = data["external_client_id"]
    return values


def sync_clients(db: Session) -> dict[str, Any]:
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
        raise HTTPException(
            status_code=503,
            detail="Supabase is not configured on the server.",
        )

    try:
        from app.services.property_listing_sync import sync_property_listings

        agent_sync = sync_agents(db)
        if agent_sync["errors"]:
            raise HTTPException(
                status_code=502,
                detail="Unable to refresh agent records before client sync.",
            )
        property_sync = sync_property_listings(db)
        if property_sync["errors"]:
            raise HTTPException(
                status_code=502,
                detail="Unable to refresh property statuses before client sync.",
            )
        response = supabase.table("clients").select("*").execute()
    except HTTPException:
        raise
    except Exception as exc:
        error_message = str(exc).casefold()
        if "42501" in error_message or "permission denied" in error_message:
            detail = (
                "Supabase denied access to public.clients. Grant the service_role "
                "access using the provided Supabase SQL script."
            )
        else:
            detail = (
                "Unable to read public.clients. Verify the backend Supabase "
                "credentials and that the clients table exists."
            )
        raise HTTPException(status_code=502, detail=detail) from exc

    records = response.data or []
    synced_at = datetime.now(timezone.utc).replace(tzinfo=None)
    processed_property_ids: set[int] = set()
    inserted = 0
    updated = 0
    errors = 0

    for data in records:
        if not isinstance(data, dict):
            errors += 1
            continue
        try:
            property_id = int(data.get("property_id"))
        except (TypeError, ValueError):
            errors += 1
            continue

        listing = db.get(PropertyListing, property_id)
        if listing is None:
            continue

        if property_id in processed_property_ids:
            errors += 1
            continue

        try:
            values = _client_values(data, listing, synced_at)
            if db.get(Agent, values["agent_id"]) is None:
                errors += 1
                continue
            existing = db.execute(
                select(Client).where(Client.property_id == property_id)
            ).scalar_one_or_none()
            if existing is None:
                db.add(Client(**values))
                inserted += 1
            else:
                for field, value in values.items():
                    if field != "client_id":
                        setattr(existing, field, value)
                updated += 1
            processed_property_ids.add(property_id)
        except (ValueError, TypeError):
            errors += 1

    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Unable to save synchronized client records locally.",
        ) from exc

    return {
        "total": len(records),
        "inserted": inserted,
        "updated": updated,
        "cancelled": 0,
        "errors": errors,
        "last_synced_at": synced_at,
    }
