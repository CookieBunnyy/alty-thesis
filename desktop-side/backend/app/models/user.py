from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str] = mapped_column(String(50), default="Employee", nullable=False)
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id"), nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Website client accounts (role "Client") point at their client record;
    # internal staff accounts leave this empty.
    client_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("clients.client_id", ondelete="SET NULL"),
        nullable=True, unique=True,
    )
    # Staff accounts of agents: the agent record they are (for "My Work").
    agent_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("agents.agent_id", ondelete="SET NULL"), nullable=True, unique=True,
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )