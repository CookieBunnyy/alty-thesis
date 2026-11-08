"""Staff "forgot password" without email: the Administrator approves it.

1. On the sign-in page the staff member enters their username (or registered
   email). The browser receives a random secret (kept only in that browser;
   the server stores its SHA-256) and a 6-digit check code derived from it.
2. Administrators see the request in their notifications and on the Users
   page. Before approving they confirm with the person (in person or by
   phone) that the check code on the person's screen matches.
3. Approval creates a normal one-time reset token with the same hash, valid
   PASSWORD_RESET_APPROVED_HOURS. The asking browser, which polls the status,
   then shows the "choose a new password" form and finishes through the
   usual /auth/password-reset/confirm step (atomic, single use, ends every
   session of the account).

The public answers never say whether an account exists: an unknown name
gets a secret and a code too, and its status simply stays pending.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import CLIENT, canonical_role
from app.models.auth_security import PasswordResetRequest, PasswordResetToken
from app.models.user import User
from app.services import auth_throttle as throttle
from app.services.audit import record_audit

HOUR = timedelta(hours=1)
OPEN = ("PENDING", "APPROVED")
MAX_OPEN_PER_ACCOUNT = 3


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def check_code(token_hash: str) -> str:
    """Six digits both screens show, so the Administrator can confirm they are
    approving the request of the person they are talking to."""
    number = int(token_hash[:12], 16) % 1_000_000
    return f"{number:06d}"[:3] + " " + f"{number:06d}"[3:]


def _iso(value: datetime | None) -> str | None:
    return f"{value.isoformat()}Z" if value else None


def _pending_window() -> timedelta:
    return timedelta(hours=max(1, settings.PASSWORD_RESET_REQUEST_HOURS))


def _approved_window() -> timedelta:
    return timedelta(hours=max(1, settings.PASSWORD_RESET_APPROVED_HOURS))


def _eligible(db: Session, identifier: str) -> User | None:
    user = db.execute(
        select(User).where(or_(func.lower(User.username) == identifier, func.lower(User.email) == identifier))
    ).scalars().first()
    if user is None or not user.is_active or canonical_role(user.role) == CLIENT:
        return None
    return user


def ask(db: Session, identifier: str, note: str | None, ip: str) -> dict[str, Any]:
    """Record a request for the account named ``identifier`` (username or
    email). Same answer whether or not the account exists."""
    if throttle.count(db, throttle.RESET_IP, ip, HOUR) >= settings.PASSWORD_RESET_PER_IP_PER_HOUR:
        raise HTTPException(status_code=429, detail="Too many requests. Please wait a while and try again.")
    identifier = throttle.normalize_identifier(identifier)
    throttle.record(db, throttle.RESET_IP, ip)
    over_limit = throttle.count(db, throttle.RESET_EMAIL, identifier, HOUR) >= settings.PASSWORD_RESET_PER_EMAIL_PER_HOUR
    throttle.record(db, throttle.RESET_EMAIL, identifier)

    now = datetime.utcnow()
    token = secrets.token_urlsafe(32)
    token_hash = hash_token(token)
    expires_at = now + _pending_window()
    user = None if over_limit else _eligible(db, identifier)
    if user is not None:
        open_count = db.scalar(select(func.count()).select_from(PasswordResetRequest).where(
            PasswordResetRequest.user_id == user.id, PasswordResetRequest.status == "PENDING",
            PasswordResetRequest.expires_at > now))
        if open_count >= MAX_OPEN_PER_ACCOUNT:
            user = None
    if user is None:
        record_audit(db, "PASSWORD_RESET_REQUEST_IGNORED", actor="UNKNOWN", entity_type="users", result="IGNORED",
                     details={"reason": "limit" if over_limit else "no eligible account or too many open requests"})
    else:
        db.add(PasswordResetRequest(user_id=user.id, token_hash=token_hash, status="PENDING",
                                    note=(note or "").strip()[:300] or None, created_at=now, expires_at=expires_at))
        record_audit(db, "PASSWORD_RESET_REQUESTED", actor=user, entity_type="users", entity_id=user.id,
                     details={"approval": "administrator"})
    db.commit()
    return {"request_token": token, "code": check_code(token_hash), "expires_at": _iso(expires_at),
            "approved_hours": int(_approved_window().total_seconds() // 3600)}


def _state(db: Session, request: PasswordResetRequest, now: datetime) -> tuple[str, datetime | None]:
    """The request's current status and until when it lasts."""
    if request.status == "PENDING":
        return ("EXPIRED", None) if request.expires_at <= now else ("PENDING", request.expires_at)
    if request.status == "APPROVED":
        link = db.execute(select(PasswordResetToken).where(PasswordResetToken.token_hash == request.token_hash)).scalar_one_or_none()
        if link is None or link.used_at is not None or link.expires_at <= now:
            return "EXPIRED", None
        return "APPROVED", link.expires_at
    return request.status, None


def status(db: Session, token: str) -> dict[str, Any]:
    now = datetime.utcnow()
    request = None
    if 20 <= len(token) <= 200:
        request = db.execute(select(PasswordResetRequest).where(
            PasswordResetRequest.token_hash == hash_token(token))).scalar_one_or_none()
    if request is None:
        # Unknown secrets look like a request still waiting (no account hints).
        return {"status": "PENDING", "until": None}
    state, until = _state(db, request, now)
    return {"status": state, "until": _iso(until)}


def mark_completed(db: Session, token_hash: str, user_id: int) -> None:
    """Called when the reset step succeeds: this request is done, the
    account's other open requests are closed."""
    now = datetime.utcnow()
    db.execute(update(PasswordResetRequest).where(PasswordResetRequest.token_hash == token_hash)
               .values(status="COMPLETED", completed_at=now))
    db.execute(update(PasswordResetRequest)
               .where(PasswordResetRequest.user_id == user_id, PasswordResetRequest.status.in_(OPEN),
                      PasswordResetRequest.token_hash != token_hash)
               .values(status="CANCELLED", decided_at=now))


# ---- Administrator side ------------------------------------------------------

def _row(db: Session, request: PasswordResetRequest, user: User | None, now: datetime) -> dict[str, Any]:
    state, until = _state(db, request, now)
    return {
        "id": request.id, "status": state, "code": check_code(request.token_hash), "note": request.note,
        "created_at": _iso(request.created_at), "until": _iso(until),
        "decided_at": _iso(request.decided_at), "decided_by": request.decided_by_name,
        "completed_at": _iso(request.completed_at),
        "user": {"id": user.id, "username": user.username, "full_name": user.full_name,
                 "role": canonical_role(user.role)} if user else None,
    }


def list_requests(db: Session, *, open_only: bool) -> list[dict[str, Any]]:
    now = datetime.utcnow()
    query = select(PasswordResetRequest, User).join(User, User.id == PasswordResetRequest.user_id)
    if open_only:
        query = query.where(PasswordResetRequest.status.in_(OPEN))
    else:
        query = query.where(PasswordResetRequest.created_at >= now - timedelta(days=30))
    rows = db.execute(query.order_by(PasswordResetRequest.created_at.desc()).limit(100)).all()
    items = [_row(db, request, user, now) for request, user in rows]
    return [item for item in items if item["status"] in OPEN] if open_only else items


def pending_for_notifications(db: Session) -> list[tuple[PasswordResetRequest, User]]:
    now = datetime.utcnow()
    return list(db.execute(
        select(PasswordResetRequest, User).join(User, User.id == PasswordResetRequest.user_id)
        .where(PasswordResetRequest.status == "PENDING", PasswordResetRequest.expires_at > now)
        .order_by(PasswordResetRequest.created_at.desc()).limit(20)
    ).all())


def decide(db: Session, request_id: int, admin: User, approve: bool) -> dict[str, Any]:
    now = datetime.utcnow()
    request = db.get(PasswordResetRequest, request_id)
    if request is None:
        raise HTTPException(status_code=404, detail="Password reset request not found")
    user = db.get(User, request.user_id)
    if request.user_id == admin.id:
        raise HTTPException(status_code=403, detail="Another Administrator has to decide your own request")
    state, _ = _state(db, request, now)
    if state != "PENDING":
        raise HTTPException(status_code=409, detail=f"This request is already {state.lower()}")
    if approve and (user is None or not user.is_active):
        raise HTTPException(status_code=409, detail="The account is deactivated. Reactivate it first.")
    request.status = "APPROVED" if approve else "DENIED"
    request.decided_at = now
    request.decided_by_user_id = admin.id
    request.decided_by_name = admin.full_name
    if approve:
        db.add(PasswordResetToken(user_id=request.user_id, token_hash=request.token_hash, created_at=now,
                                  expires_at=now + _approved_window()))
    record_audit(db, "PASSWORD_RESET_APPROVED" if approve else "PASSWORD_RESET_DENIED", actor=admin,
                 entity_type="users", entity_id=request.user_id, details={"request_id": request.id})
    db.commit()
    return _row(db, request, user, now)
