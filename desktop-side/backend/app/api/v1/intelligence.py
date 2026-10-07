"""ALTY Intelligence: contextual decision support (see services/intelligence.py).

Management roles only, like the desktop's Analytics, Forecasting and
Decision Support pages. The desktop's /analytics/dss endpoint is unchanged.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import MANAGEMENT_ROLES, require_roles
from app.models.agent import Agent
from app.models.property_listing import PropertyListing
from app.models.user import User
from app.services import analytics, intelligence

router = APIRouter(prefix="/intelligence", tags=["Intelligence"])
require_insight = require_roles(*MANAGEMENT_ROLES)


@router.get("/insights")
def get_insights(db: Session = Depends(get_db), _user: User = Depends(require_insight)):
    """Every current insight, highest priority first (the Insights feed)."""
    return intelligence.all_insights(db)


@router.get("/analytics")
def get_analytics(months: int = Query(default=12, ge=3, le=60), db: Session = Depends(get_db),
                  _user: User = Depends(require_insight)):
    data = intelligence.breakdown(db)
    return {"overview": analytics.overview(db), "monthly": analytics.monthly_series(db, months),
            "breakdown": data, "insights": intelligence.market_insights(db, data)}


@router.get("/forecast")
def get_forecast(metric: str = Query(default="revenue", pattern="^(revenue|transactions|sales)$"),
                 horizon: int = Query(default=3, ge=1, le=12), db: Session = Depends(get_db),
                 _user: User = Depends(require_insight)):
    result = analytics.forecast(db, metric, horizon)
    return {"forecast": result, "insights": intelligence.forecast_insights(db, metric, result)}


@router.get("/properties/{listing_id}")
def get_property_insights(listing_id: int, db: Session = Depends(get_db), _user: User = Depends(require_insight)):
    listing = db.get(PropertyListing, listing_id)
    if listing is None:
        raise HTTPException(status_code=404, detail="Property listing not found")
    return {"insights": intelligence.property_insights(db, listing)}


@router.get("/agents/{agent_id}")
def get_agent_insights(agent_id: str, db: Session = Depends(get_db), _user: User = Depends(require_insight)):
    agent = db.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"insights": intelligence.agent_insights(db, agent)}


@router.get("/agent-forecasts")
def get_agent_forecasts(horizon: int = Query(default=3, ge=1, le=12), db: Session = Depends(get_db),
                        _user: User = Depends(require_insight)):
    """Each active agent's expected completed sales for the coming months,
    from the agent's own monthly history (or why it can't be estimated)."""
    return {"horizon": horizon, "agents": analytics.agent_forecasts(db, horizon)}


@router.get("/agents/{agent_id}/forecast")
def get_agent_forecast(agent_id: str, horizon: int = Query(default=3, ge=1, le=12),
                       db: Session = Depends(get_db), _user: User = Depends(require_insight)):
    if db.get(Agent, agent_id) is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return analytics.agent_forecasts(db, horizon, agent_id=agent_id)[0]
