from datetime import datetime
from decimal import Decimal

from datetime import date

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


DESIGNATIONS = ("Trainee Agent", "Sales Agent", "Senior Sales Agent", "Team Leader", "Branch Manager", "Broker")


class Agent(Base):
    __tablename__ = "agents"

    agent_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    phone_number: Mapped[str | None] = mapped_column(String(40), nullable=True)
    agent_location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    star_rating: Mapped[Decimal | None] = mapped_column(Numeric(2, 1), nullable=True)
    assignments_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    transactions_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed_sales: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_sales: Mapped[Decimal] = mapped_column(
        Numeric(16, 2), default=Decimal("0"), nullable=False
    )
    total_commission: Mapped[Decimal] = mapped_column(
        Numeric(16, 2), default=Decimal("0"), nullable=False
    )
    performance_score: Mapped[Decimal] = mapped_column(
        Numeric(6, 2), default=Decimal("0"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(24), default="ACTIVE", nullable=False, index=True
    )
    sync_status: Mapped[str] = mapped_column(
        String(24), default="PENDING", nullable=False
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Assignment (ALTY only; not part of the Supabase agent record): where the
    # agent works, their position, and the area they cover.
    branch_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("branches.id", ondelete="SET NULL"), nullable=True, index=True)
    designation: Mapped[str | None] = mapped_column(String(60), nullable=True)
    work_area: Mapped[str | None] = mapped_column(String(255), nullable=True)
    hired_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    branch = relationship("Branch", lazy="selectin", viewonly=True)

    @property
    def branch_name(self) -> str | None:
        return self.branch.name if self.branch else None

    # Profile photo (ALTY only; not part of the Supabase agent record).
    photo_bucket: Mapped[str | None] = mapped_column(String(120), nullable=True)
    photo_path: Mapped[str | None] = mapped_column(String(300), nullable=True)
    photo_updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )