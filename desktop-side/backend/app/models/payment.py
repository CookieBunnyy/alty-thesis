from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TransactionPayment(Base):
    """Money received for a reservation after its reservation fee: the down
    payment and the monthly payments. Recorded by management; the payment
    schedule (services/payment_plan.py) applies them in order."""

    __tablename__ = "transaction_payments"
    __table_args__ = (CheckConstraint("amount > 0", name="ck_transaction_payments_amount_positive"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    transaction_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("transactions.transaction_id", ondelete="CASCADE"), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    paid_at: Mapped[date] = mapped_column(Date, nullable=False)
    note: Mapped[str | None] = mapped_column(String(300), nullable=True)
    recorded_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
