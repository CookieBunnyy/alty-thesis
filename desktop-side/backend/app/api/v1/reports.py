"""Management reports: sales (Administrator, Broker, Filing Manager) and
recruitment (Administrator, Broker). Sellers never see these."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import MANAGEMENT_ROLES, canonical_role, get_company_user, require_management
from app.models.user import User
from app.services import reports

router = APIRouter(prefix="/reports", tags=["Reports"])


def _range(start: date | None, end: date | None) -> tuple[date, date]:
    end = end or date.today()
    start = start or date(end.year, 1, 1)
    if start > end:
        raise HTTPException(status_code=422, detail="The start date must be on or before the end date")
    return start, end


@router.get("/sales")
def sales(start: date | None = None, end: date | None = None,
          period: str = Query(default="month", pattern="^(day|month|year)$"), agent_id: str | None = None,
          team_id: int | None = None, project: str | None = None, listing_id: int | None = None,
          db: Session = Depends(get_db), _user: User = Depends(get_company_user)):
    start, end = _range(start, end)
    return reports.sales_report(db, start, end, period, agent_id, team_id, project, listing_id)


@router.get("/recruitment")
def recruitment(start: date | None = None, end: date | None = None,
                period: str = Query(default="month", pattern="^(day|month|year)$"), recruiter: str | None = None,
                team_id: int | None = None, db: Session = Depends(get_db), _user: User = Depends(require_management)):
    start, end = _range(start, end)
    return reports.recruitment_report(db, start, end, period, recruiter, team_id)


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), user: User = Depends(get_company_user)):
    return reports.dashboard(db, include_recruitment=canonical_role(user.role) in MANAGEMENT_ROLES)
