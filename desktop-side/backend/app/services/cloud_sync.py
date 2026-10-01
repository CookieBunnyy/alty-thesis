"""Push locally-created/updated records to Supabase (the central database).

Local PostgreSQL is authoritative for document-derived records: rows are
written locally with ``sync_status = PENDING`` and pushed here. A failed
push leaves the row PENDING with the reason reported, so nothing is lost
and a later sync retries it. Pull-syncs never overwrite PENDING rows.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.supabase import supabase
from app.models.agent import Agent
from app.models.client import Client
from app.models.document import Document
from app.models.property_listing import PropertyListing
from app.models.transaction import PropertyTransaction
from app.services.document_storage import try_sync_document_metadata

logger = logging.getLogger(__name__)

SCHEMA_HINT = (
    "Supabase is missing columns used by the document-first schema; run "
    "desktop-side/backend/supabase_document_first.sql in the Supabase SQL Editor."
)


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _row(record: Any, columns: list[str]) -> dict:
    return {column: _value(getattr(record, column)) for column in columns}


def _missing_column(exc: Exception) -> bool:
    text = str(exc)
    return "PGRST204" in text or "Could not find the" in text and "column" in text


def cloud_sync_enabled() -> bool:
    return settings.CLOUD_SYNC_ENABLED and settings.cloud_configured


AGENT_COLUMNS = [
    "agent_id", "full_name", "phone_number", "agent_location", "latitude", "longitude",
    "star_rating", "assignments_count", "transactions_count", "completed_sales",
    "total_sales", "total_commission", "performance_score", "status", "created_at", "updated_at",
]
LISTING_COLUMNS = [
    "listing_id", "external_listing_id", "title", "category", "price_total", "initial_dp",
    "monthly_rate", "num_bedrooms", "num_bathrooms", "layout_type", "village_name", "lat",
    "lng", "photos", "amenity_list", "nearby_places", "details", "nearby_establishments",
    "has_balcony", "has_kitchen", "has_backyard", "has_garage", "garage_spaces", "status",
]
CLIENT_BASE_COLUMNS = [
    "client_id", "external_client_id", "full_name", "location", "phone_number", "email",
    "agent_id", "property_id", "transaction_type", "transaction_date", "status",
    "created_at", "updated_at",
]
CLIENT_EXTENDED_COLUMNS = ["occupation", "civil_status", "preferred_contact", "purpose_of_purchase"]
TRANSACTION_BASE_COLUMNS = [
    "transaction_id", "external_transaction_id", "client_id", "property_id", "agent_id",
    "transaction_type", "transaction_date", "amount", "status", "notes", "created_at",
    "updated_at",
]
TRANSACTION_EXTENDED_COLUMNS = ["source", "source_document_id"]


def _upsert(table: str, rows: list[dict], conflict: str, base: list[str] | None = None) -> list[str]:
    """Upsert rows; if the cloud lacks extended columns, retry with ``base``."""
    warnings: list[str] = []
    try:
        supabase.table(table).upsert(rows, on_conflict=conflict).execute()
    except Exception as exc:
        if base is None or not _missing_column(exc):
            raise
        supabase.table(table).upsert(
            [{key: row[key] for key in base} for row in rows], on_conflict=conflict
        ).execute()
        warnings.append(f"{table}: {SCHEMA_HINT}")
    return warnings


def _push_listing(listing: PropertyListing) -> None:
    existing = (
        supabase.table("listings").select("listing_id,external_listing_id,title")
        .eq("listing_id", listing.listing_id).execute().data
    )
    row = _row(listing, LISTING_COLUMNS)
    if existing:
        cloud = existing[0]
        cloud_external = cloud.get("external_listing_id") or None
        if cloud_external or listing.external_listing_id:
            same_identity = cloud_external == listing.external_listing_id
        else:
            same_identity = (cloud.get("title") or "").strip().casefold() == (
                listing.title or ""
            ).strip().casefold()
        if not same_identity:
            raise RuntimeError(
                f"Supabase listing {listing.listing_id} is a different property "
                f"('{cloud.get('title')}'); not overwritten"
            )
        supabase.table("listings").update(
            {key: value for key, value in row.items() if key != "listing_id"}
        ).eq("listing_id", listing.listing_id).execute()
    else:
        supabase.table("listings").insert(row).execute()


def push_pending(db: Session) -> dict:
    """Push every PENDING record; returns per-table counts and errors."""
    report: dict[str, Any] = {"enabled": cloud_sync_enabled(), "tables": {}, "warnings": []}
    if not report["enabled"]:
        report["reason"] = (
            "Cloud sync disabled" if not settings.CLOUD_SYNC_ENABLED else "Supabase not configured"
        )
        return report

    def section(name: str) -> dict:
        return report["tables"].setdefault(name, {"pushed": 0, "failed": 0, "errors": []})

    # FK order: agents -> listings -> clients -> transactions.
    for agent in db.execute(select(Agent).where(Agent.sync_status == "PENDING")).scalars():
        stats = section("agents")
        try:
            _upsert("agents", [_row(agent, AGENT_COLUMNS)], "agent_id")
            agent.sync_status, agent.last_synced_at = "SYNCED", _now()
            stats["pushed"] += 1
        except Exception as exc:
            stats["failed"] += 1
            stats["errors"].append(f"agent {agent.agent_id}: {exc}")

    for listing in db.execute(
        select(PropertyListing).where(PropertyListing.sync_status == "PENDING")
    ).scalars():
        stats = section("listings")
        try:
            _push_listing(listing)
            listing.sync_status, listing.last_synced_at = "SYNCED", _now()
            stats["pushed"] += 1
        except Exception as exc:
            stats["failed"] += 1
            stats["errors"].append(f"listing {listing.listing_id}: {exc}")

    for client in db.execute(select(Client).where(Client.sync_status == "PENDING")).scalars():
        stats = section("clients")
        if client.property_id is not None and db.get(PropertyListing, client.property_id).sync_status != "SYNCED":
            stats["failed"] += 1
            stats["errors"].append(f"client {client.client_id}: its property is not yet synced")
            continue
        try:
            row = _row(client, CLIENT_BASE_COLUMNS + CLIENT_EXTENDED_COLUMNS)
            report["warnings"] += _upsert("clients", [row], "client_id", CLIENT_BASE_COLUMNS)
            client.sync_status, client.last_synced_at = "SYNCED", _now()
            stats["pushed"] += 1
        except Exception as exc:
            stats["failed"] += 1
            stats["errors"].append(f"client {client.client_id}: {exc}")

    for transaction in db.execute(
        select(PropertyTransaction).where(PropertyTransaction.sync_status == "PENDING")
    ).scalars():
        stats = section("transactions")
        if transaction.client.sync_status != "SYNCED":
            stats["failed"] += 1
            stats["errors"].append(f"transaction {transaction.transaction_id}: its client is not yet synced")
            continue
        try:
            row = _row(transaction, TRANSACTION_BASE_COLUMNS + TRANSACTION_EXTENDED_COLUMNS)
            report["warnings"] += _upsert("transactions", [row], "transaction_id", TRANSACTION_BASE_COLUMNS)
            transaction.sync_status, transaction.last_synced_at = "SYNCED", _now()
            stats["pushed"] += 1
        except Exception as exc:
            stats["failed"] += 1
            stats["errors"].append(f"transaction {transaction.transaction_id}: {exc}")

    for document in db.execute(select(Document).where(Document.sync_status == "PENDING")).scalars():
        stats = section("documents")
        error = try_sync_document_metadata(document)
        if error:
            stats["failed"] += 1
            stats["errors"].append(f"document {document.document_id} v{document.version}: {error}")
        else:
            stats["pushed"] += 1

    report["warnings"] = sorted(set(report["warnings"]))
    db.commit()
    return report


def try_push_pending(db: Session) -> dict:
    """Best-effort push used after document processing; never raises."""
    try:
        return push_pending(db)
    except Exception as exc:  # pragma: no cover - network/cloud failure
        db.rollback()
        logger.exception("Cloud push failed")
        return {"enabled": True, "error": f"{type(exc).__name__}: {exc}"}


def sync_state(db: Session) -> dict:
    """Counts of records per sync status for the settings/sync screens."""
    state = {}
    for name, model in (
        ("agents", Agent), ("listings", PropertyListing), ("clients", Client),
        ("transactions", PropertyTransaction), ("documents", Document),
    ):
        rows = db.execute(
            select(model.sync_status, func.count()).group_by(model.sync_status)
        ).all()
        state[name] = {str(status): int(count) for status, count in rows}
    return {"enabled": cloud_sync_enabled(), "counts": state}
