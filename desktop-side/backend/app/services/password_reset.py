"""Staff password recovery by registered email.

* The response never depends on whether the address belongs to an account
  (callers always answer the same way; emails go out in the background).
* Tokens: 32 random bytes (``secrets``), stored only as SHA-256 hashes,
  valid PASSWORD_RESET_TTL_MINUTES (15-30), single use. Claiming a token is
  one atomic UPDATE, so two simultaneous uses cannot both succeed.
* A new link replaces any earlier unused one; using a link ends every
  session of the account (session_version) and sends a notice.
* Links are built from STAFF_APP_URL, never from the request's Host header.
"""

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import ADMINISTRATOR, CLIENT, canonical_role, get_password_hash
from app.models.auth_security import PasswordResetToken
from app.models.client import Client
from app.models.user import User
from app.services import auth_throttle as throttle
from app.services.audit import record_audit, record_audit_now
from app.services.email_service import send_email

INVALID_LINK = "This reset link is invalid or has expired. Request a new one."
HOUR = timedelta(hours=1)


@dataclass
class ResetEmail:
    to: str
    full_name: str
    link: str
    is_client: bool


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def mask_email(email: str) -> str:
    local, _, domain = email.partition("@")
    return f"{local[:1]}***@{domain}" if domain else "***"


def _eligible(db: Session, email: str) -> User | None:
    client_ids = select(Client.client_id).where(func.lower(Client.email) == email)
    user = db.scalars(
        select(User).where(
            func.lower(User.email) == email,
            func.lower(User.role) != CLIENT.casefold(),
        )
    ).first()
    if user is None:
        user = db.execute(
            select(User).where(
                func.lower(User.role) == CLIENT.casefold(),
                (func.lower(User.username) == email) | User.client_id.in_(client_ids),
            )
        ).scalars().first()
    if user is None or not user.is_active:
        return None
    if canonical_role(user.role) == CLIENT and (user.client_id is None or db.get(Client, user.client_id) is None):
        return None
    return user


def account_email(db: Session, user: User) -> str | None:
    if canonical_role(user.role) == CLIENT:
        client = db.get(Client, user.client_id) if user.client_id else None
        return (client.email if client else None) or user.username
    return user.email


def active_admin_emails(db: Session) -> list[str]:
    rows = db.execute(
        select(User.email, User.role)
        .where(
            User.is_active.is_(True),
            User.email.is_not(None),
            func.trim(User.email) != "",
        )
        .distinct()
    ).all()
    return sorted({email for email, role in rows if email and canonical_role(role) == ADMINISTRATOR})


def request_reset(db: Session, email: str, ip: str) -> ResetEmail | None:
    """Create a reset link when ``email`` belongs to an eligible account
    and the sending limits allow it. Returns what to send, or None."""
    if throttle.count(db, throttle.RESET_IP, ip, HOUR) >= settings.PASSWORD_RESET_PER_IP_PER_HOUR:
        raise HTTPException(status_code=429, detail="Too many requests. Please wait a while and try again.")
    email = throttle.normalize_identifier(email)
    throttle.record(db, throttle.RESET_IP, ip)
    over_email_limit = throttle.count(db, throttle.RESET_EMAIL, email, HOUR) >= settings.PASSWORD_RESET_PER_EMAIL_PER_HOUR
    throttle.record(db, throttle.RESET_EMAIL, email)
    user = None if over_email_limit else _eligible(db, email)
    if user is None:
        record_audit(db, "PASSWORD_RESET_REQUEST_IGNORED", actor="UNKNOWN", entity_type="users", result="IGNORED",
                     details={"email": mask_email(email), "reason": "limit" if over_email_limit else "no eligible account"})
        db.commit()
        return None

    account = f"user:{user.id}"
    interval = timedelta(seconds=settings.PASSWORD_RESET_MIN_EMAIL_INTERVAL_SECONDS)
    if (throttle.count(db, throttle.RESET_SENT, account, interval)
            or throttle.count(db, throttle.RESET_SENT, account, HOUR) >= settings.PASSWORD_RESET_PER_EMAIL_PER_HOUR):
        record_audit(db, "PASSWORD_RESET_REQUEST_IGNORED", actor=user, entity_type="users", entity_id=user.id,
                     result="IGNORED", details={"reason": "email sent recently"})
        db.commit()
        return None

    now = datetime.utcnow()
    # Only the newest link works.
    db.execute(update(PasswordResetToken)
               .where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None))
               .values(used_at=now))
    token = secrets.token_urlsafe(32)
    db.add(PasswordResetToken(user_id=user.id, token_hash=hash_token(token), created_at=now,
                              expires_at=now + timedelta(minutes=settings.password_reset_ttl_minutes)))
    throttle.record(db, throttle.RESET_SENT, account)
    record_audit(db, "PASSWORD_RESET_REQUESTED", actor=user, entity_type="users", entity_id=user.id)
    db.commit()
    recipient = account_email(db, user) or email
    is_client = canonical_role(user.role) == CLIENT
    base_url = (settings.CLIENT_APP_URL if is_client and settings.CLIENT_APP_URL.strip()
                else settings.STAFF_APP_URL).strip().rstrip("/")
    path = "/reset-password" if is_client else "/manage/reset-password"
    link = f"{base_url}{path}#token={token}"
    return ResetEmail(to=recipient, full_name=user.full_name, link=link, is_client=is_client)


def confirm_reset(db: Session, token: str, new_password: str, ip: str) -> User:
    """Set a new password with a valid link. Raises 400 (one message for
    unknown, expired and used links) or 429."""
    if throttle.count(db, throttle.RESET_CONFIRM_IP, ip, HOUR, failures_only=True) >= 20:
        raise HTTPException(status_code=429, detail="Too many attempts. Please wait a while and try again.")
    now = datetime.utcnow()
    claimed = None
    if 20 <= len(token) <= 200:
        # Atomic claim: marks the token used only if it is unused and current.
        claimed = db.execute(
            update(PasswordResetToken)
            .where(PasswordResetToken.token_hash == hash_token(token),
                   PasswordResetToken.used_at.is_(None), PasswordResetToken.expires_at > now)
            .values(used_at=now)
            .returning(PasswordResetToken.user_id)
        ).scalar_one_or_none()
    user = db.get(User, claimed) if claimed is not None else None
    if user is None or not user.is_active:
        db.rollback()
        throttle.record(db, throttle.RESET_CONFIRM_IP, ip)
        record_audit_now(db, "PASSWORD_RESET_FAILED", actor="UNKNOWN", entity_type="users", result="FAILED",
                         details={"reason": "invalid, expired or used link"})
        raise HTTPException(status_code=400, detail=INVALID_LINK)

    set_password(user, new_password)
    # An Administrator-approved request finishes here too (same token hash).
    from app.services.password_requests import mark_completed
    mark_completed(db, hash_token(token), user.id)
    db.execute(update(PasswordResetToken)
               .where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None))
               .values(used_at=now))
    throttle.record(db, throttle.RESET_CONFIRM_IP, ip, success=True)
    record_audit(db, "PASSWORD_RESET_COMPLETED", actor=user, entity_type="users", entity_id=user.id)
    db.commit()
    return user


def set_password(user: User, new_password: str) -> None:
    """New password; every existing session of the account ends."""
    user.password_hash = get_password_hash(new_password)
    user.session_version = (user.session_version or 0) + 1
    user.password_changed_at = datetime.utcnow()


# ---- emails (sent in the background, after the response) --------------------

def send_reset_email(message: ResetEmail) -> None:
    minutes = settings.password_reset_ttl_minutes
    product = "Abellar Realty" if message.is_client else "Alty MSA (Abellar Realty Management System)"
    account_label = "buyer" if message.is_client else "staff"
    text = (
        f"Hello {message.full_name},\n\n"
        f"Someone asked to reset the password of your {product} {account_label} account.\n"
        f"Open this link within {minutes} minutes to choose a new password:\n\n{message.link}\n\n"
        "The link works once. If you didn't ask for this, ignore this email: your password stays the same.\n"
    )
    html = (
        f"<p>Hello {_escape(message.full_name)},</p>"
        f"<p>Someone asked to reset the password of your <b>{_escape(product)}</b> {account_label} account.</p>"
        f"<p><a href=\"{_escape(message.link)}\">Choose a new password</a> (valid for {minutes} minutes, works once).</p>"
        "<p>If you didn't ask for this, ignore this email: your password stays the same.</p>"
    )
    subject = "Reset your Abellar Realty password" if message.is_client else "Reset your Alty MSA password"
    send_email(message.to, subject, text, html)


def send_buyer_reset_admin_notice(to: str, buyer_name: str, buyer_email: str) -> None:
    text = (
        "A buyer requested a password reset for their Abellar Realty account.\n\n"
        f"Buyer: {buyer_name}\n"
        f"Email: {buyer_email}\n\n"
        "A one-time reset link was sent to the buyer. No action is required unless they need assistance.\n"
    )
    html = (
        "<p>A buyer requested a password reset for their Abellar Realty account.</p>"
        f"<p>Buyer: {_escape(buyer_name)}<br>Email: {_escape(buyer_email)}</p>"
        "<p>A one-time reset link was sent to the buyer. No action is required unless they need assistance.</p>"
    )
    send_email(to, "Buyer password reset requested", text, html)


def send_password_changed_notice(to: str | None, full_name: str, is_client: bool = False) -> None:
    if not to:
        return
    product = "Abellar Realty" if is_client else "Alty MSA (Abellar Realty Management System)"
    text = (
        f"Hello {full_name},\n\n"
        f"The password of your {product} account was just changed, "
        "and every device signed in to it was signed out.\n\n"
        "If this wasn't you, contact your Administrator right away.\n"
    )
    subject = "Your Abellar Realty password was changed" if is_client else "Your Alty MSA password was changed"
    send_email(to, subject, text)


def _escape(value: str) -> str:
    return (value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;"))
