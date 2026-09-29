from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.api.v1.auth import router as auth_router
from app.api.v1.agents import router as agents_router
from app.api.v1.clients import router as clients_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.transactions import router as transactions_router
from app.api.v1.documents import router as documents_router
from app.api.v1.property_listings import router as property_listings_router
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import get_password_hash
from app.models.user import User


@asynccontextmanager
async def lifespan(app: FastAPI):
    db: Session = SessionLocal()
    try:
        existing = db.query(User).filter(User.username == "admin").first()
        if existing is None:
            db.add(
                User(
                    username="admin",
                    full_name="System Administrator",
                    role="Administrator",
                    password_hash=get_password_hash("admin123"),
                    is_active=True,
                )
            )
            db.commit()
    finally:
        db.close()

    yield


app = FastAPI(title=settings.APP_NAME, version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/v1")

app.include_router(
    property_listings_router,
    prefix="/api/v1",
)
app.include_router(
    documents_router,
    prefix="/api/v1",
)
app.include_router(
    agents_router,
    prefix="/api/v1",
)
app.include_router(
    clients_router,
    prefix="/api/v1",
)
app.include_router(
    transactions_router,
    prefix="/api/v1",
)
app.include_router(
    dashboard_router,
    prefix="/api/v1",
)


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "app": settings.APP_NAME}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
