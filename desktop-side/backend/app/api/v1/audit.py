"""Read-only system audit trail."""

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_management
from app.models.audit import AuditEvent
from app.models.user import User

router = APIRouter(prefix="/audit", tags=["Audit"])


@router.get("")
def get_audit_events(
    action: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    actor: str | None = None,
    result: str | None = None,
    search: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _user: User = Depends(require_management),
):
    filters = []
    if action:
        filters.append(AuditEvent.action == action.upper())
    if entity_type:
        filters.append(AuditEvent.entity_type == entity_type)
    if entity_id:
        filters.append(AuditEvent.entity_id == entity_id)
    if actor:
        filters.append(AuditEvent.actor_label.ilike(f"%{actor}%"))
    if result:
        filters.append(AuditEvent.result == result.upper())
    if since:
        filters.append(AuditEvent.created_at >= since)
    if until:
        filters.append(AuditEvent.created_at <= until)
    if search:
        pattern = f"%{search}%"
        filters.append(or_(AuditEvent.action.ilike(pattern), AuditEvent.entity_id.ilike(pattern),
                           AuditEvent.actor_label.ilike(pattern)))
    total = db.scalar(select(func.count(AuditEvent.id)).where(*filters)) or 0
    rows = db.execute(
        select(AuditEvent).where(*filters).order_by(AuditEvent.id.desc()).offset(offset).limit(limit)
    ).scalars().all()
    return {
        "total": int(total),
        "items": [
            {"id": e.id, "timestamp": e.created_at, "actor": e.actor_label, "actor_id": e.actor_id,
             "action": e.action, "entity_type": e.entity_type, "entity_id": e.entity_id,
             "result": e.result, "details": e.details}
            for e in rows
        ],
    }


@router.get("/actions")
def get_audit_actions(db: Session = Depends(get_db), _user: User = Depends(require_management)):
    return sorted(row[0] for row in db.execute(select(AuditEvent.action).distinct()))
