"""Rate limits and cooldowns for staff sign-in and password recovery.

Attempts are stored in the database (``auth_attempts``), so every API
instance shares them and a restart does not reset them. Keys (IP, account,
email) are stored only as keyed hashes. Cooldowns are temporary and
progressive (LOGIN_COOLDOWN_STEPS); nothing locks an account permanently.
"""

import hashlib
import hmac
import random
from datetime import datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.auth_security import AuthAttempt

LOGIN_IP = "login_ip"
LOGIN_ACCOUNT = "login_account"
RESET_IP = "reset_ip"
RESET_EMAIL = "reset_email"
RESET_SENT = "reset_sent"        # emails actually sent, per account
RESET_CONFIRM_IP = "reset_confirm_ip"

KEEP_FOR = timedelta(days=2)


def normalize_identifier(value: str) -> str:
    return (value or "").strip().casefold()


def key_hash(value: str) -> str:
    return hmac.new(settings.SECRET_KEY.encode(), normalize_identifier(value).encode(), hashlib.sha256).hexdigest()


def record(db: Session, scope: str, key: str, success: bool = False) -> None:
    db.add(AuthAttempt(scope=scope, key_hash=key_hash(key), success=success, created_at=datetime.utcnow()))
    if random.random() < 0.02:  # occasional clean-up of old rows
        db.execute(delete(AuthAttempt).where(AuthAttempt.created_at < datetime.utcnow() - KEEP_FOR))


def count(db: Session, scope: str, key: str, within: timedelta, *, failures_only: bool = False) -> int:
    query = select(func.count(AuthAttempt.id)).where(
        AuthAttempt.scope == scope, AuthAttempt.key_hash == key_hash(key),
        AuthAttempt.created_at >= datetime.utcnow() - within,
    )
    if failures_only:
        query = query.where(AuthAttempt.success.is_(False))
    return db.scalar(query) or 0


def _since_last_success(db: Session, scope: str, key: str, within: timedelta) -> tuple[int, datetime | None]:
    """Failures for ``key`` since its last success inside ``within``, and the latest failure time."""
    hashed = key_hash(key)
    start = datetime.utcnow() - within
    last_success = db.scalar(select(func.max(AuthAttempt.created_at)).where(
        AuthAttempt.scope == scope, AuthAttempt.key_hash == hashed, AuthAttempt.success.is_(True),
        AuthAttempt.created_at >= start))
    since = max(start, last_success) if last_success else start
    row = db.execute(select(func.count(AuthAttempt.id), func.max(AuthAttempt.created_at)).where(
        AuthAttempt.scope == scope, AuthAttempt.key_hash == hashed, AuthAttempt.success.is_(False),
        AuthAttempt.created_at > since)).one()
    return row[0] or 0, row[1]


def login_failures(db: Session, account: str) -> tuple[int, datetime | None]:
    return _since_last_success(db, LOGIN_ACCOUNT, account,
                               timedelta(minutes=settings.LOGIN_FAILURE_WINDOW_MINUTES))


def login_cooldown_seconds(db: Session, account: str) -> int:
    """Seconds left before ``account`` may try again (0 = may try now)."""
    failures, last = login_failures(db, account)
    wait = 0
    for threshold, seconds in settings.login_cooldown_steps:
        if failures >= threshold:
            wait = seconds
    if not wait or last is None:
        return 0
    remaining = (last + timedelta(seconds=wait) - datetime.utcnow()).total_seconds()
    return max(0, int(remaining + 0.999))


def ip_failures(db: Session, ip: str) -> int:
    return count(db, LOGIN_IP, ip, timedelta(minutes=settings.LOGIN_FAILURE_WINDOW_MINUTES), failures_only=True)


def login_needs_captcha(db: Session, account: str, ip: str) -> bool:
    if not settings.captcha_enabled:
        return False
    after = max(1, settings.LOGIN_CAPTCHA_AFTER_FAILURES)
    return login_failures(db, account)[0] >= after or ip_failures(db, ip) >= after * 2
