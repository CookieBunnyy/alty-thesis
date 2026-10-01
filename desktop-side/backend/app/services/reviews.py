"""Client reviews of agents: the single source for every rating shown.

Desktop Agent Management, the website agent profile, Agents Near Property
and the home page all read client ratings through these helpers, so they
always show the same numbers. ``agents.star_rating`` (synced from Supabase)
is kept untouched and reported separately as the system/legacy rating.
"""

from __future__ import annotations

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models.review import AgentReview

MAX_REVIEW_LENGTH = 1000


def review_stats(db: Session, agent_ids: list[str] | None = None) -> dict[str, dict]:
    """{agent_id: {"client_rating": avg | None, "review_count": n}} from agent_reviews."""
    statement = select(AgentReview.agent_id, func.avg(AgentReview.rating), func.count(AgentReview.id)) \
        .group_by(AgentReview.agent_id)
    if agent_ids is not None:
        if not agent_ids:
            return {}
        statement = statement.where(AgentReview.agent_id.in_(agent_ids))
    return {
        agent_id: {"client_rating": round(float(avg), 2), "review_count": int(count)}
        for agent_id, avg, count in db.execute(statement)
    }


def stats_for(stats: dict[str, dict], agent_id: str) -> dict:
    return stats.get(agent_id, {"client_rating": None, "review_count": 0})


def overall_stats(db: Session) -> dict:
    avg, count = db.execute(select(func.avg(AgentReview.rating), func.count(AgentReview.id))).one()
    return {"average": round(float(avg), 2) if avg is not None else None, "count": int(count)}


def reviewer_name(full_name: str | None) -> str:
    """Privacy-safe reviewer label: first name and last initial ("Maria S.")."""
    parts = [part for part in (full_name or "").split() if part]
    if not parts:
        return "Verified client"
    if len(parts) == 1:
        return parts[0]
    return f"{parts[0]} {parts[-1][0].upper()}."


def public_review(review: AgentReview, include_agent: bool = False) -> dict:
    """What anyone may see: no client ID, email, phone, address or property."""
    data = {
        "id": review.id,
        "rating": review.rating,
        "review": review.review,
        "reviewer": reviewer_name(review.client.full_name if review.client else None),
        "verified": True,  # every review is tied to a completed transaction
        "transaction_type": review.transaction.transaction_type if review.transaction else None,
        "created_at": review.created_at,
        "updated_at": review.updated_at,
    }
    if include_agent:
        data["agent"] = {"agent_id": review.agent_id,
                         "full_name": review.agent.full_name if review.agent else None}
    return data


def recent_reviews(db: Session, agent_id: str | None = None, limit: int = 10, offset: int = 0,
                   with_text_first: bool = False) -> list[AgentReview]:
    statement = select(AgentReview)
    if agent_id is not None:
        statement = statement.where(AgentReview.agent_id == agent_id)
    order = [AgentReview.created_at.desc(), AgentReview.id.desc()]
    if with_text_first:
        has_text = func.length(func.coalesce(AgentReview.review, "")) > 0
        order.insert(0, case((has_text, 0), else_=1))
    return list(db.execute(statement.order_by(*order).offset(offset).limit(limit)).scalars())
