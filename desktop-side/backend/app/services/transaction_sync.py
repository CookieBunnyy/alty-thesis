"""Pull transactions from Supabase into local PostgreSQL."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.supabase import supabase
from app.models.agent import Agent
from app.models.client import Client
from app.models.property_listing import PropertyListing
from app.models.transaction import PropertyTransaction
from app.services.client_sync import sync_clients


def sync_transactions(db: Session) -> dict[str, Any]:
    if not settings.cloud_configured:
        raise HTTPException(status_code=503, detail="Supabase is not configured on the server.")

    client_sync = sync_clients(db)
    try:
        response = supabase.table("transactions").select("*").execute()
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"Unable to retrieve public.transactions from Supabase: {exc}"
        ) from exc

    records = response.data or []
    synced_at = datetime.now(timezone.utc).replace(tzinfo=None)
    inserted = updated = skipped = errors = 0
    messages: list[str] = []
    for data in records:
        try:
            transaction_id = str(UUID(str(data.get("transaction_id"))))
            client_id = str(UUID(str(data.get("client_id"))))
            property_id = int(data.get("property_id"))
            agent_id = str(data.get("agent_id") or "").strip()
            amount = Decimal(str(data.get("amount")))
            if amount < 0:
                raise ValueError("amount cannot be negative")
            transaction_date = datetime.fromisoformat(
                str(data.get("transaction_date")).replace("Z", "+00:00")
            )
            if transaction_date.tzinfo is None:
                transaction_date = transaction_date.replace(tzinfo=timezone.utc)
            transaction_type = str(data.get("transaction_type") or "").upper()
            status = str(data.get("status") or "").upper()
            if transaction_type not in {"RESERVED", "SOLD"} or status not in {
                "RESERVED", "COMPLETED", "CANCELLED"
            }:
                raise ValueError("invalid type/status")
        except (InvalidOperation, TypeError, ValueError) as exc:
            errors += 1
            messages.append(f"transaction {data.get('transaction_id')}: {exc}")
            continue

        if db.get(Client, client_id) is None or db.get(PropertyListing, property_id) is None \
                or db.get(Agent, agent_id) is None:
            errors += 1
            messages.append(f"transaction {transaction_id}: client, property or agent is not local")
            continue

        values = {
            "client_id": client_id, "property_id": property_id, "agent_id": agent_id,
            "transaction_type": transaction_type, "transaction_date": transaction_date,
            "amount": amount, "status": status, "notes": data.get("notes"),
            "updated_at": synced_at, "sync_status": "SYNCED", "last_synced_at": synced_at,
        }
        if data.get("external_transaction_id"):
            values["external_transaction_id"] = data["external_transaction_id"]
        existing = db.get(PropertyTransaction, transaction_id)
        if existing is None and values.get("external_transaction_id"):
            existing = db.execute(select(PropertyTransaction).where(
                PropertyTransaction.external_transaction_id == values["external_transaction_id"]
            )).scalar_one_or_none()
        if existing is None:
            # Same business event stored under a different id (e.g. local rows
            # created by an earlier migration): match on client + property +
            # type instead of inserting a duplicate reservation/sale.
            existing = db.execute(
                select(PropertyTransaction).where(
                    PropertyTransaction.client_id == client_id,
                    PropertyTransaction.property_id == property_id,
                    PropertyTransaction.transaction_type == transaction_type,
                ).order_by((PropertyTransaction.status == "CANCELLED").asc())
            ).scalars().first()
        savepoint = db.begin_nested()
        try:
            if existing is None:
                existing = PropertyTransaction(transaction_id=transaction_id, created_at=synced_at,
                                               source="SYNC", **values)
                db.add(existing)
                inserted += 1
            elif existing.sync_status == "PENDING":
                skipped += 1  # local change not yet pushed: never overwrite it
            else:
                for field, value in values.items():
                    setattr(existing, field, value)
                updated += 1
            if existing.status == "CANCELLED" and not existing.cancellation_reason \
                    and existing.sync_status != "PENDING":
                # The central database only carries the status, not why.
                existing.cancellation_reason = "Cancelled in the central database (no reason recorded there)."
                existing.cancelled_at = existing.cancelled_at or synced_at
                existing.cancelled_by = existing.cancelled_by or "Central database sync"
            db.flush()  # later rows in this batch see this one
            savepoint.commit()
        except IntegrityError as exc:
            savepoint.rollback()
            errors += 1
            messages.append(f"transaction {transaction_id}: {str(exc.orig).splitlines()[0]}")

    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Unable to save synchronized transactions locally: {exc}") from exc
    return {
        "total": len(records), "inserted": inserted, "updated": updated,
        "skipped_pending": skipped, "errors": errors,
        "error_messages": (client_sync.get("error_messages", []) + messages)[:20],
        "last_synced_at": synced_at,
    }
