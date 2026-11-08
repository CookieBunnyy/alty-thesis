"""Staff password reset requests waiting for the Administrator (used while
email isn't set up; see services.password_requests)."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_management
from app.models.user import User
from app.services import password_requests

router = APIRouter(prefix="/password-requests", tags=["Password reset requests"])


@router.get("")
def list_password_requests(open_only: bool = True, db: Session = Depends(get_db),
                           _admin: User = Depends(require_management)):
    return password_requests.list_requests(db, open_only=open_only)


@router.post("/{request_id}/approve")
def approve_password_request(request_id: int, db: Session = Depends(get_db),
                             admin: User = Depends(require_management)):
    return password_requests.decide(db, request_id, admin, approve=True)


@router.post("/{request_id}/deny")
def deny_password_request(request_id: int, db: Session = Depends(get_db),
                          admin: User = Depends(require_management)):
    return password_requests.decide(db, request_id, admin, approve=False)
