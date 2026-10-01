"""System audit trail helper.

Callers add the event to the current session; it is committed with the
business change it describes, so a rolled-back change leaves no audit row.
Use :func:`record_audit_now` for events that must persist on their own
(for example failed logins).
"""

from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.models.audit import AuditEvent
from app.models.user import User

logger = logging.getLogger(__name__)

SYSTEM = "SYSTEM"
WEBSITE = "WEBSITE"


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(item) for item in value]
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def record_audit(
    db: Session,
    action: str,
    *,
    actor: User | str | None = None,
    entity_type: str | None = None,
    entity_id: Any = None,
    result: str = "SUCCESS",
    details: dict | None = None,
) -> AuditEvent:
    if isinstance(actor, User):
        actor_id, actor_label = actor.id, actor.username
    else:
        actor_id, actor_label = None, actor or SYSTEM
    event = AuditEvent(
        actor_id=actor_id,
        actor_label=actor_label,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        result=result,
        details=_jsonable(details or {}),
    )
    db.add(event)
    return event


def record_audit_now(db: Session, action: str, **kwargs: Any) -> None:
    """Persist an audit event in its own commit (never raises)."""
    try:
        record_audit(db, action, **kwargs)
        db.commit()
    except Exception:  # pragma: no cover - audit must never break the request
        db.rollback()
        logger.exception("Could not persist audit event %s", action)
