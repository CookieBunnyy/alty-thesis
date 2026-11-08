from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PasswordResetToken(Base):
    """A staff password-reset link. Only the SHA-256 hash of the token is
    kept; the token itself exists only in the email."""

    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class AuthAttempt(Base):
    """One sign-in or recovery attempt, for rate limits shared by every API
    instance. ``key_hash`` is a keyed hash of the IP / account / email, so the
    table holds no addresses or usernames."""

    __tablename__ = "auth_attempts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    scope: Mapped[str] = mapped_column(String(40), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class PasswordResetRequest(Base):
    """"Forgot password" without email: the staff member asks, an
    Administrator approves or declines, and only the browser that asked
    (it holds the secret whose SHA-256 is ``token_hash``) can then choose the
    new password. Approval adds a PasswordResetToken with the same hash, so
    the usual one-time reset step finishes it."""

    __tablename__ = "password_reset_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    # PENDING -> APPROVED -> COMPLETED, or DENIED / CANCELLED.
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING", index=True)
    note: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)  # while pending
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    decided_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    decided_by_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
