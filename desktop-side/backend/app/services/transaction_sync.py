from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
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
from app.services.client_sync import sync_clients


def sync_transactions(db: Session) -> dict[str, Any]:
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
        raise HTTPException(
            status_code=503,
            detail="Supabase is not configured on the server.",
        )

    client_sync = sync_clients(db)
    if client_sync["errors"]:
        raise HTTPException(
            status_code=502,
            detail="Unable to sync clients before transaction records.",
        )
    try:
        response = supabase.table("transactions").select("*").execute()
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail="Unable to retrieve public.transactions from Supabase.",
        ) from exc

    records = response.data or []
    synced_at = datetime.now(timezone.utc).replace(tzinfo=None)
    inserted = 0
    updated = 0
    errors = 0
    for data in records:
        try:
            transaction_id = str(UUID(str(data.get("transaction_id"))))
            client_id = str(UUID(str(data.get("client_id"))))
            property_id = int(data.get("property_id"))
            agent_id = str(data.get("agent_id") or "").strip()
            amount = Decimal(str(data.get("amount")))
            if amount < 0:
                raise ValueError("Transaction amount cannot be negative")
            transaction_date = datetime.fromisoformat(
                str(data.get("transaction_date")).replace("Z", "+00:00")
            )
            if transaction_date.tzinfo is None:
                transaction_date = transaction_date.replace(tzinfo=timezone.utc)
        except (InvalidOperation, TypeError, ValueError):
            errors += 1
            continue

        client = db.get(Client, client_id)
        listing = db.get(PropertyListing, property_id)
        agent = db.get(Agent, agent_id)
        if (
            client is None
            or listing is None
            or agent is None
            or client.property_id != property_id
            or client.agent_id != agent_id
        ):
            errors += 1
            continue

        values = {
            "client_id": client_id,
            "property_id": property_id,
            "agent_id": agent_id,
            "transaction_type": str(data.get("transaction_type") or "").upper(),
            "transaction_date": transaction_date,
            "amount": amount,
            "status": str(data.get("status") or "").upper(),
            "notes": data.get("notes"),
            "updated_at": synced_at,
        }
        if data.get("external_transaction_id"):
            values["external_transaction_id"] = data["external_transaction_id"]
        existing = db.get(PropertyTransaction, transaction_id)
        if existing is None and values.get("external_transaction_id"):
            existing = db.execute(
                select(PropertyTransaction).where(
                    PropertyTransaction.external_transaction_id
                    == values["external_transaction_id"]
                )
            ).scalar_one_or_none()
        if existing is None:
            db.add(
                PropertyTransaction(
                    transaction_id=transaction_id,
                    created_at=synced_at,
                    **values,
                )
            )
            inserted += 1
        else:
            for field, value in values.items():
                setattr(existing, field, value)
            updated += 1

    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Unable to save synchronized transactions locally.",
        ) from exc

    return {
        "total": len(records),
        "inserted": inserted,
        "updated": updated,
        "errors": errors,
        "last_synced_at": synced_at,
    }