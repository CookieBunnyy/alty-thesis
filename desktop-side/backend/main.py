import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select

from app.api.v1.agents import router as agents_router
from app.api.v1.analytics import router as analytics_router
from app.api.v1.audit import router as audit_router
from app.api.v1.auth import router as auth_router
from app.api.v1.client_portal import router as client_portal_router
from app.api.v1.clients import router as clients_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.documents import router as documents_router
from app.api.v1.maps import router as maps_router
from app.api.v1.media import router as media_router
from app.api.v1.property_listings import router as property_listings_router
from app.api.v1.public import router as public_router
from app.api.v1.search import router as search_router
from app.api.v1.system import router as system_router
from app.api.v1.transactions import router as transactions_router
from app.api.v1.users import router as users_router
from app.core.config import DEFAULT_SECRET_KEY, settings
from app.core.database import SessionLocal
from app.core.security import ADMINISTRATOR, get_password_hash
from app.models.user import User

logger = logging.getLogger("alty")


def _bootstrap_admin() -> None:
    """Create the first administrator only when the users table is empty and
    INITIAL_ADMIN_PASSWORD is configured. No default password is ever used."""
    db = SessionLocal()
    try:
        if db.scalar(select(func.count(User.id))):
            return
        if not settings.INITIAL_ADMIN_PASSWORD:
            logger.warning(
                "No users exist. Set INITIAL_ADMIN_PASSWORD in .env and restart "
                "to create the first administrator."
            )
            return
        db.add(User(
            username=settings.INITIAL_ADMIN_USERNAME,
            full_name="System Administrator",
            role=ADMINISTRATOR,
            password_hash=get_password_hash(settings.INITIAL_ADMIN_PASSWORD),
            is_active=True,
        ))
        db.commit()
        logger.warning("Created initial administrator '%s'", settings.INITIAL_ADMIN_USERNAME)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.SECRET_KEY == DEFAULT_SECRET_KEY:
        logger.warning("SECRET_KEY is the default value; set a random SECRET_KEY in .env")
    _bootstrap_admin()
    yield


app = FastAPI(title=settings.APP_NAME, version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=settings.CORS_ORIGIN_REGEX.strip() or None,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)

for router in (
    auth_router,
    users_router,
    property_listings_router,
    documents_router,
    media_router,
    agents_router,
    clients_router,
    transactions_router,
    dashboard_router,
    analytics_router,
    audit_router,
    system_router,
    public_router,
    maps_router,
    client_portal_router,
    search_router,
):
    app.include_router(router, prefix="/api/v1")


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "app": settings.APP_NAME}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
