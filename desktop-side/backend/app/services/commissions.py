"""Commission records: suggestions from configurable structures and the
recorded amounts the reports use. No rate is assumed anywhere: a commission
counts only once it is recorded (and is never counted when rejected or
cancelled)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.models.commission import CommissionRecord, CommissionStructure
from app.models.transaction import PropertyTransaction

CENT = Decimal("0.01")


def suggest(structure: CommissionStructure | None, basis_amount: Decimal | None,
            monthly_rent: Decimal | None = None) -> Decimal | None:
    """The amount a structure gives, or None when it can't (AS_AGREED, missing inputs)."""
    if structure is None:
        return None
    if structure.basis == "PERCENT_OF_PRICE" and structure.rate_percent is not None and basis_amount:
        return (Decimal(basis_amount) * Decimal(structure.rate_percent) / 100).quantize(CENT, ROUND_HALF_UP)
    if structure.basis == "FIXED_AMOUNT" and structure.fixed_amount is not None:
        return Decimal(structure.fixed_amount).quantize(CENT)
    if structure.basis == "MONTHS_OF_RENT" and structure.months_of_rent is not None and monthly_rent:
        return (Decimal(monthly_rent) * Decimal(structure.months_of_rent)).quantize(CENT, ROUND_HALF_UP)
    return None


def _day(value) -> date:
    if isinstance(value, datetime):
        return (value.astimezone(timezone.utc) if value.tzinfo else value).date()
    return value


def counted(db: Session, agent_id: str | None = None, branch_id: int | None = None) -> list[dict]:
    """Recorded commissions that count: the sale's date for sales, else the record date.
    ``branch_id`` 0 = sellers without a team."""
    statement = (select(CommissionRecord, PropertyTransaction.transaction_date, Agent.branch_id)
                 .outerjoin(PropertyTransaction, PropertyTransaction.transaction_id == CommissionRecord.transaction_id)
                 .outerjoin(Agent, Agent.agent_id == CommissionRecord.agent_id)
                 .where(CommissionRecord.status != "CANCELLED", CommissionRecord.approval_status != "REJECTED"))
    if agent_id is not None:
        statement = statement.where(CommissionRecord.agent_id == agent_id)
    rows = []
    for record, sold_at, branch in db.execute(statement).all():
        if branch_id is not None and (branch or 0) != branch_id:
            continue
        day = _day(sold_at) if sold_at is not None else record.record_date
        rows.append({"record": record, "day": day, "month": f"{day.year:04d}-{day.month:02d}",
                     "amount": float(record.amount or 0)})
    return rows


def monthly(db: Session, agent_id: str | None = None, branch_id: int | None = None) -> dict[str, float]:
    totals: dict[str, float] = {}
    for row in counted(db, agent_id, branch_id):
        totals[row["month"]] = totals.get(row["month"], 0.0) + row["amount"]
    return {month: round(total, 2) for month, total in totals.items()}
