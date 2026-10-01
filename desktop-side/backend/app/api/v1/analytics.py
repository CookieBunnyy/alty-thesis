"""Analytics, forecasting, decision support and workforce indicators."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import MANAGEMENT_ROLES, get_current_user, require_roles
from app.models.user import User
from app.services import analytics

router = APIRouter(prefix="/analytics", tags=["Analytics"])
require_insight = require_roles(*MANAGEMENT_ROLES)


@router.get("/overview")
def get_overview(db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    return analytics.overview(db)


@router.get("/monthly")
def get_monthly(months: int | None = Query(default=None, ge=1, le=120),
                db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    return analytics.monthly_series(db, months)


@router.get("/forecast")
def get_forecast(metric: str = Query(default="revenue", pattern="^(revenue|transactions|sales)$"),
                 horizon: int = Query(default=3, ge=1, le=12),
                 db: Session = Depends(get_db), _user: User = Depends(require_insight)):
    return analytics.forecast(db, metric, horizon)


@router.get("/dss")
def get_decision_support(db: Session = Depends(get_db), _user: User = Depends(require_insight)):
    return analytics.dss_insights(db)


@router.get("/workforce")
def get_workforce(db: Session = Depends(get_db), _user: User = Depends(require_insight)):
    return analytics.workforce(db)
