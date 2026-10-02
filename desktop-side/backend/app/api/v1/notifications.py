"""Desktop header notifications (computed from records; see services.notifications)."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.services import notifications

router = APIRouter(prefix="/notifications", tags=["Notifications"])


class MarkRead(BaseModel):
    keys: list[str] = Field(default_factory=list, max_length=200)


@router.get("")
def list_notifications(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return notifications.notifications_for(db, user)


@router.post("/read")
def mark_notifications_read(payload: MarkRead, db: Session = Depends(get_db),
                            user: User = Depends(get_current_user)):
    notifications.mark_read(db, user, payload.keys)
    return notifications.notifications_for(db, user)


@router.post("/read-all")
def mark_all_notifications_read(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    current = notifications.notifications_for(db, user)
    notifications.mark_read(db, user, [item["key"] for item in current["items"] if not item["read"]])
    return notifications.notifications_for(db, user)
