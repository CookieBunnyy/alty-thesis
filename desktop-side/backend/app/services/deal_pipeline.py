"""Deals from inquiry to closing, kept in step with the reservation and sale
records (which come from documents or the "Proceed to sale" action)."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.deal import DEAL_CLOSED, DEAL_STAGES, Deal, DealEvent
from app.models.transaction import PropertyTransaction

ORDER = {stage: index for index, stage in enumerate(DEAL_STAGES)}


def log(db: Session, deal: Deal, actor: str | None, *, to_stage: str | None = None, changes: dict | None = None,
        note: str | None = None) -> None:
    db.add(DealEvent(deal_id=deal.id, from_stage=deal.stage if to_stage else None, to_stage=to_stage,
                     changes=changes or {}, note=note, actor=actor))
    if to_stage:
        deal.stage = to_stage


def _open_deal(db: Session, client_id: str, listing_id: int) -> Deal | None:
    return db.execute(select(Deal).where(Deal.client_id == client_id, Deal.listing_id == listing_id,
                                         Deal.stage.not_in(DEAL_CLOSED)).order_by(Deal.id.desc())).scalars().first()


def _day(value: datetime):
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc)
    return value.date()


def record_transaction(db: Session, transaction: PropertyTransaction, actor: str) -> Deal:
    """A reservation or sale was recorded: move (or start) the buyer's deal."""
    deal = _open_deal(db, transaction.client_id, transaction.property_id)
    if deal is None and transaction.transaction_type == "SOLD":
        deal = db.execute(select(Deal).where(Deal.reservation_transaction_id.is_not(None),
                                             Deal.client_id == transaction.client_id,
                                             Deal.listing_id == transaction.property_id,
                                             Deal.stage != "LOST").order_by(Deal.id.desc())).scalars().first()
    if deal is None:
        deal = Deal(client_id=transaction.client_id, listing_id=transaction.property_id,
                    agent_id=transaction.agent_id, stage="INQUIRY", created_by=actor)
        db.add(deal)
        db.flush()
        log(db, deal, actor, note="Started from a recorded transaction")
    deal.agent_id = deal.agent_id or transaction.agent_id
    if transaction.transaction_type == "RESERVED":
        deal.reservation_transaction_id = transaction.transaction_id
        deal.reservation_date = _day(transaction.transaction_date)
        deal.reservation_status = "RESERVED"
        if ORDER.get(deal.stage, 0) < ORDER["RESERVED"]:
            log(db, deal, actor, to_stage="RESERVED", note="Reservation recorded")
    else:
        deal.sale_transaction_id = transaction.transaction_id
        deal.closing_date = _day(transaction.transaction_date)
        if deal.reservation_status == "RESERVED":
            deal.reservation_status = "COMPLETED"
        log(db, deal, actor, to_stage="CLOSED", note="Sale recorded")
    db.flush()
    return deal


def record_cancellation(db: Session, reservation: PropertyTransaction, reason: str | None, actor: str) -> None:
    """A reservation was cancelled: the deal is lost unless already closed."""
    deal = db.execute(select(Deal).where(Deal.reservation_transaction_id == reservation.transaction_id)
                      ).scalars().first()
    if deal is None:
        return
    deal.reservation_status = "CANCELLED"
    if deal.stage not in DEAL_CLOSED:
        deal.lost_reason = reason
        log(db, deal, actor, to_stage="LOST", note=f"Reservation cancelled: {reason}" if reason else
            "Reservation cancelled")
