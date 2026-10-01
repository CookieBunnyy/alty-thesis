from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.supabase import supabase
from app.models.agent import Agent


NUMERIC_FIELDS = (
    "latitude",
    "longitude",
    "star_rating",
    "total_sales",
    "total_commission",
    "performance_score",
)
INTEGER_FIELDS = ("assignments_count", "transactions_count", "completed_sales")


def _datetime_value(value: Any, fallback: datetime) -> datetime:
    if value is None or value == "":
        return fallback
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(
            tzinfo=None
        )
    except ValueError as exc:
        raise ValueError("Invalid agent timestamp") from exc


def _decimal_value(value: Any, field: str) -> Decimal | None:
    if value is None or value == "":
        return None if field in {"latitude", "longitude", "star_rating"} else Decimal("0")
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"Invalid {field} value") from exc


def _agent_values(data: dict[str, Any], synced_at: datetime) -> dict[str, Any]:
    agent_id = str(data.get("agent_id") or "").strip()
    full_name = str(data.get("full_name") or "").strip()
    if not agent_id or len(agent_id) > 32:
        raise ValueError("Agent record has an invalid agent_id")
    if not full_name:
        raise ValueError(f"Agent {agent_id} has no full_name")

    values: dict[str, Any] = {
        "full_name": full_name,
        "phone_number": str(data["phone_number"]).strip() if data.get("phone_number") else None,
        "agent_location": str(data["agent_location"]).strip() if data.get("agent_location") else None,
        "status": str(data.get("status") or "ACTIVE").strip().upper(),
        "sync_status": "SYNCED",
        "last_synced_at": synced_at,
        "created_at": _datetime_value(data.get("created_at"), synced_at),
        "updated_at": _datetime_value(data.get("updated_at"), synced_at),
    }
    for field in NUMERIC_FIELDS:
        value = _decimal_value(data.get(field), field)
        if field == "latitude" and value is not None and not Decimal(-90) <= value <= Decimal(90):
            raise ValueError(f"Agent {agent_id} has an invalid latitude")
        if field == "longitude" and value is not None and not Decimal(-180) <= value <= Decimal(180):
            raise ValueError(f"Agent {agent_id} has an invalid longitude")
        if field == "star_rating" and value is not None and not Decimal(0) <= value <= Decimal(5):
            raise ValueError(f"Agent {agent_id} has an invalid star_rating")
        values[field] = value
    for field in INTEGER_FIELDS:
        raw_value = data.get(field) or 0
        try:
            count = int(raw_value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Agent {agent_id} has an invalid {field}") from exc
        if count < 0:
            raise ValueError(f"Agent {agent_id} has a negative {field}")
        values[field] = count
    return {"agent_id": agent_id, **values}


def sync_agents(db: Session) -> dict[str, Any]:
    if not settings.cloud_configured:
        raise HTTPException(status_code=503, detail="Supabase is not configured on the server")
    try:
        response = supabase.table("agents").select("*").execute()
    except Exception as exc:
        error_message = str(exc).casefold()
        if "42501" in error_message or "permission denied" in error_message:
            detail = (
                "Supabase denied access to public.agents. In the Supabase SQL Editor, "
                "run: GRANT USAGE ON SCHEMA public TO service_role; "
                "GRANT SELECT ON TABLE public.agents TO service_role;"
            )
        else:
            detail = (
                "Unable to read public.agents. Verify the backend Supabase URL/key "
                "and that the table exists."
            )
        raise HTTPException(status_code=502, detail=detail) from exc

    records = response.data or []
    deduplicated = {
        str(row.get("agent_id")): row
        for row in records
        if isinstance(row, dict) and row.get("agent_id")
    }
    synced_at = datetime.utcnow()
    inserted = 0
    updated = 0
    errors = len(records) - len(deduplicated)

    for data in deduplicated.values():
        try:
            values = _agent_values(data, synced_at)
            agent = db.execute(
                select(Agent).where(Agent.agent_id == values["agent_id"])
            ).scalar_one_or_none()
            if agent is None:
                db.add(Agent(**values))
                inserted += 1
            elif agent.sync_status == "PENDING":
                continue  # local document-derived change not yet pushed
            else:
                for key, value in values.items():
                    if key != "agent_id":
                        setattr(agent, key, value)
                updated += 1
        except (ValueError, TypeError):
            errors += 1

    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Unable to save synchronized agents locally") from exc
    return {
        "total": len(records),
        "inserted": inserted,
        "updated": updated,
        "errors": errors,
        "last_synced_at": synced_at,
    }