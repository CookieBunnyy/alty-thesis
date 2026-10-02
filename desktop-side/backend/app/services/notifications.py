"""Header notifications for desktop staff, computed from stored records.

Nothing here is invented: each notification describes a real record or a
real condition (a failed document, a recorded transaction, a client review,
…). Notifications are not stored; each has a stable ``key`` that changes
when the underlying fact changes (e.g. a transaction moving from RESERVED to
COMPLETED), and only the per-user "read" marks are persisted
(``notification_reads``).

Each user only gets notifications for the pages their role can open;
synchronization and security alerts go to the Administrator.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, joinedload

from app.core.security import ADMINISTRATOR, canonical_role, permissions_for
from app.models.agent import Agent
from app.models.audit import AuditEvent
from app.models.client import Client
from app.models.document import Document
from app.models.notification import NotificationRead
from app.models.property_listing import PropertyListing
from app.models.review import AgentReview
from app.models.transaction import PropertyTransaction
from app.models.user import User
from app.services.cloud_sync import cloud_sync_enabled, sync_state

EVENT_WINDOW = timedelta(days=30)  # how far back record events are shown
SECURITY_WINDOW = timedelta(hours=24)
STUCK_PROCESSING = timedelta(minutes=30)
MAX_ITEMS = 60
READ_RETENTION = timedelta(days=120)

_TRANSACTION_TITLES = {
    "RESERVED": "Reservation recorded",
    "COMPLETED": "Sale completed",
    "CANCELLED": "Transaction cancelled",
}


def _iso(value: datetime | None) -> str | None:
    return f"{value.isoformat()}Z" if value else None  # stored as naive UTC


def _item(key: str, *, category: str, severity: str, title: str, message: str,
          at: datetime | None, page: str | None = None) -> dict[str, Any]:
    return {"key": key, "category": category, "severity": severity, "title": title,
            "message": message, "created_at": _iso(at), "page": page}


def _documents(db: Session, now: datetime) -> list[dict[str, Any]]:
    items = []
    failed = db.scalars(
        select(Document).where(Document.status == "FAILED")
        .order_by(Document.updated_at.desc()).limit(25)
    ).all()
    for document in failed:
        stage = (document.processing_stage or "processing").replace("_", " ").lower()
        error = (document.processing_error or "").strip().splitlines()[0:1]
        detail = f" — {error[0][:140]}" if error else ""
        items.append(_item(
            f"document-failed:{document.id}:{document.version}",
            category="documents", severity="danger", title="Document failed processing",
            message=f"{document.document_name} failed at the {stage} stage{detail}",
            at=document.processed_at or document.updated_at, page="documents",
        ))
    stuck = db.scalars(
        select(Document).where(Document.status == "PROCESSING",
                               Document.updated_at < now - STUCK_PROCESSING)
        .order_by(Document.updated_at).limit(10)
    ).all()
    for document in stuck:
        minutes = int((now - document.updated_at).total_seconds() // 60)
        items.append(_item(
            f"document-stuck:{document.id}:{document.version}",
            category="documents", severity="warning", title="Document still processing",
            message=f"{document.document_name} has been processing for {minutes} minutes",
            at=document.updated_at, page="documents",
        ))
    return items


def _transactions(db: Session, now: datetime) -> list[dict[str, Any]]:
    rows = db.scalars(
        select(PropertyTransaction)
        .options(joinedload(PropertyTransaction.client), joinedload(PropertyTransaction.property_listing),
                 joinedload(PropertyTransaction.agent))
        .where(PropertyTransaction.updated_at >= now - EVENT_WINDOW)
        .order_by(PropertyTransaction.updated_at.desc()).limit(20)
    ).all()
    items = []
    for transaction in rows:
        status = str(transaction.status or "").upper()
        client = transaction.client.full_name if transaction.client else "A client"
        listing = (transaction.property_listing.title if transaction.property_listing else None) \
            or f"listing #{transaction.property_id}"
        agent = transaction.agent.full_name if transaction.agent else transaction.agent_id
        amount = f" · ₱{float(transaction.amount):,.2f}" if transaction.amount else ""
        items.append(_item(
            f"transaction:{transaction.transaction_id}:{status}",
            category="transactions",
            severity="danger" if status == "CANCELLED" else "success" if status == "COMPLETED" else "info",
            title=_TRANSACTION_TITLES.get(status, "Transaction recorded"),
            message=f"{client} · {listing} · agent {agent}{amount}",
            at=transaction.updated_at, page="transactions",
        ))
    return items


def _reviews(db: Session, now: datetime) -> list[dict[str, Any]]:
    rows = db.scalars(
        select(AgentReview).options(joinedload(AgentReview.agent), joinedload(AgentReview.client))
        .where(AgentReview.updated_at >= now - EVENT_WINDOW)
        .order_by(AgentReview.updated_at.desc()).limit(15)
    ).all()
    items = []
    for review in rows:
        agent = review.agent.full_name if review.agent else review.agent_id
        client = review.client.full_name if review.client else "A client"
        text = f" — “{review.review.strip()[:120]}”" if review.review and review.review.strip() else ""
        edited = review.updated_at > review.created_at + timedelta(seconds=5)
        items.append(_item(
            f"review:{review.id}:{review.updated_at:%Y%m%d%H%M%S}",
            category="reviews", severity="warning" if review.rating <= 2 else "info",
            title=f"{'Updated' if edited else 'New'} {review.rating}★ review for {agent}",
            message=f"{client}{text}", at=review.updated_at, page="agents",
        ))
    return items


def _client_accounts(db: Session, now: datetime) -> list[dict[str, Any]]:
    rows = db.scalars(
        select(User).where(User.role == "Client", User.created_at >= now - EVENT_WINDOW)
        .order_by(User.created_at.desc()).limit(15)
    ).all()
    return [
        _item(f"client-account:{user.id}", category="clients", severity="info",
              title="New client account", message=f"{user.full_name} signed up on the website",
              at=user.created_at, page="clients")
        for user in rows
    ]


def _listings(db: Session) -> list[dict[str, Any]]:
    rows = db.execute(
        select(PropertyListing.listing_id, PropertyListing.updated_at)
        .where(func.upper(PropertyListing.status) == "AVAILABLE",
               (PropertyListing.lat.is_(None)) | (PropertyListing.lng.is_(None)))
        .order_by(PropertyListing.listing_id)
    ).all()
    if not rows:
        return []
    ids = [row.listing_id for row in rows]
    latest = max((row.updated_at for row in rows if row.updated_at), default=None)
    shown = ", ".join(f"#{i}" for i in ids[:6]) + ("…" if len(ids) > 6 else "")
    return [_item(
        "listings-no-location:" + ",".join(map(str, ids)),
        category="listings", severity="warning", title="Listings missing a map location",
        message=f"{len(ids)} available listing(s) have no coordinates and won't appear on the website map ({shown})",
        at=latest, page="properties",
    )]


def _sync(db: Session, now: datetime) -> list[dict[str, Any]]:
    if not cloud_sync_enabled():
        return []
    counts = sync_state(db)["counts"]
    items = []
    failed = {name: c.get("FAILED", 0) for name, c in counts.items() if c.get("FAILED", 0)}
    pending = {name: c.get("PENDING", 0) for name, c in counts.items() if c.get("PENDING", 0)}
    if failed:
        parts = ", ".join(f"{count} {name}" for name, count in failed.items())
        items.append(_item(
            "sync-failed:" + parts, category="sync", severity="danger",
            title="Records failed to sync", message=f"Not saved to the central database: {parts}",
            at=now, page="settings",
        ))
    if pending:
        parts = ", ".join(f"{count} {name}" for name, count in pending.items())
        items.append(_item(
            "sync-pending:" + parts, category="sync", severity="info",
            title="Records waiting to sync", message=f"Pending upload to the central database: {parts}",
            at=now, page="settings",
        ))
    return items


def _security(db: Session, now: datetime) -> list[dict[str, Any]]:
    rows = db.execute(
        select(AuditEvent.actor_label, func.count(), func.max(AuditEvent.created_at))
        .where(AuditEvent.action == "LOGIN_FAILED", AuditEvent.created_at >= now - SECURITY_WINDOW)
        .group_by(AuditEvent.actor_label)
    ).all()
    return [
        _item(f"login-failed:{actor}:{latest:%Y%m%d}:{count}", category="security",
              severity="danger" if count >= 5 else "warning",
              title="Failed sign-in attempts",
              message=f"{count} failed sign-in attempt(s) for “{actor}” in the last 24 hours",
              at=latest, page="audit")
        for actor, count, latest in rows
    ]


def notifications_for(db: Session, user: User) -> dict[str, Any]:
    now = datetime.utcnow()
    pages = set(permissions_for(user.role))
    admin = canonical_role(user.role) == ADMINISTRATOR
    items: list[dict[str, Any]] = []
    if "documents" in pages:
        items += _documents(db, now)
    if "transactions" in pages:
        items += _transactions(db, now)
    if "agents" in pages:
        items += _reviews(db, now)
    if "clients" in pages:
        items += _client_accounts(db, now)
    if "properties" in pages:
        items += _listings(db)
    if admin:
        items += _sync(db, now)
        items += _security(db, now)

    items.sort(key=lambda item: item["created_at"] or "", reverse=True)
    items = items[:MAX_ITEMS]
    read = set(db.scalars(
        select(NotificationRead.key).where(NotificationRead.user_id == user.id,
                                           NotificationRead.key.in_([item["key"] for item in items]))
    ).all()) if items else set()
    for item in items:
        item["read"] = item["key"] in read
    return {"items": items, "unread": sum(not item["read"] for item in items)}


def mark_read(db: Session, user: User, keys: list[str]) -> None:
    now = datetime.utcnow()
    keys = sorted({key[:200] for key in keys if key})
    if keys:
        existing = set(db.scalars(
            select(NotificationRead.key).where(NotificationRead.user_id == user.id,
                                               NotificationRead.key.in_(keys))
        ).all())
        db.add_all(NotificationRead(user_id=user.id, key=key, read_at=now) for key in keys if key not in existing)
    # Old marks belong to notifications that have long dropped out of the list.
    db.execute(delete(NotificationRead).where(NotificationRead.user_id == user.id,
                                              NotificationRead.read_at < now - READ_RETENTION))
    db.commit()
