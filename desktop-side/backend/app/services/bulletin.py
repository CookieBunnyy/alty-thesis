"""Bulletin board figures: progress toward sales targets and incentives.

Only recorded transactions are counted, never estimates:

* "Sales" = the total contract price (TCP) of reservations and sales that
  aren't cancelled, each buyer-property deal counted once (a reservation that
  later becomes a sale is one deal), dated within the memo's period.
* Company-wide totals and other sellers' figures are shown to company staff
  only; a seller sees the target and their own figures.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.models.bulletin import BulletinPost
from app.models.property_listing import PropertyListing
from app.models.transaction import PropertyTransaction


def deals_in_period(db: Session, start: date | None, end: date | None, *, branch_id: int | None = None,
                    partner_id: int | None = None) -> list[dict[str, Any]]:
    """One row per buyer-property deal (largest TCP on record), not cancelled."""
    query = (select(PropertyTransaction.client_id, PropertyTransaction.property_id, PropertyTransaction.agent_id,
                    PropertyTransaction.amount, PropertyTransaction.transaction_date)
             .where(PropertyTransaction.status != "CANCELLED"))
    if start:
        query = query.where(PropertyTransaction.transaction_date >= datetime.combine(start, time.min))
    if end:
        query = query.where(PropertyTransaction.transaction_date <= datetime.combine(end, time.max))
    if branch_id is not None:
        query = query.join(Agent, Agent.agent_id == PropertyTransaction.agent_id).where(Agent.branch_id == branch_id)
    if partner_id is not None:
        query = (query.join(PropertyListing, PropertyListing.listing_id == PropertyTransaction.property_id)
                 .where(PropertyListing.partner_id == partner_id))
    deals: dict[tuple, dict] = {}
    for client_id, property_id, agent_id, amount, when in db.execute(query).all():
        key = (str(client_id), property_id)
        amount = Decimal(amount or 0)
        if key not in deals or amount > deals[key]["amount"]:
            deals[key] = {"agent_id": agent_id, "amount": amount, "date": when}
    return list(deals.values())


def _period(post: BulletinPost) -> tuple[date | None, date | None]:
    return post.valid_from, post.valid_until


def progress(db: Session, post: BulletinPost, *, viewer_agent_id: str | None, company: bool) -> dict | None:
    """What the memo means in recorded sales, for this viewer."""
    if post.board != "MEMO" or post.category not in ("TARGET", "INCENTIVE"):
        return None
    start, end = _period(post)
    deals = deals_in_period(db, start, end, branch_id=post.branch_id, partner_id=post.partner_id)
    per_agent: dict[str, Decimal] = defaultdict(Decimal)
    count_per_agent: dict[str, int] = defaultdict(int)
    for deal in deals:
        per_agent[deal["agent_id"]] += deal["amount"]
        count_per_agent[deal["agent_id"]] += 1
    mine = per_agent.get(viewer_agent_id, Decimal(0)) if viewer_agent_id else None
    result: dict[str, Any] = {"period": {"from": start.isoformat() if start else None,
                                         "until": end.isoformat() if end else None}}
    if mine is not None:
        result["mine"] = {"sales": float(mine), "deals": count_per_agent.get(viewer_agent_id, 0)}
    if post.category == "TARGET" and post.target_amount:
        target = Decimal(post.target_amount)
        if company:
            achieved = sum(per_agent.values(), Decimal(0))
            result["company"] = {"sales": float(achieved), "deals": len(deals),
                                 "percent": round(float(achieved / target * 100), 1) if target else None}
        return result
    tiers = sorted(post.tiers or [], key=lambda tier: float(tier.get("minimum_sales") or 0))
    if tiers and mine is not None:
        reached = [tier for tier in tiers if mine >= Decimal(str(tier.get("minimum_sales") or 0))]
        upcoming = next((tier for tier in tiers if mine < Decimal(str(tier.get("minimum_sales") or 0))), None)
        result["mine"]["reached"] = reached[-1]["label"] if reached else None
        result["mine"]["next"] = ({"label": upcoming["label"],
                                   "missing": float(Decimal(str(upcoming["minimum_sales"])) - mine)}
                                  if upcoming else None)
    if post.reward_amount and mine is not None:
        result["mine"]["reward_total"] = float(Decimal(post.reward_amount) * count_per_agent.get(viewer_agent_id, 0))
    if company:
        names = dict(db.execute(select(Agent.agent_id, Agent.full_name).where(
            Agent.agent_id.in_(list(per_agent) or ["-"]))).all())
        board = []
        for agent_id, sales in sorted(per_agent.items(), key=lambda item: item[1], reverse=True)[:10]:
            reached = [tier["label"] for tier in tiers if sales >= Decimal(str(tier.get("minimum_sales") or 0))]
            row = {"agent_id": agent_id, "name": names.get(agent_id, agent_id), "sales": float(sales),
                   "deals": count_per_agent[agent_id], "reached": reached[-1] if reached else None}
            if post.reward_amount:
                row["reward_total"] = float(Decimal(post.reward_amount) * count_per_agent[agent_id])
            board.append(row)
        result["leaders"] = board
    return result
