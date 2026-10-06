"""Integration-test harness.

Runs against a dedicated PostgreSQL database (``<name>_test``) created fresh
for the session and migrated with Alembic, local file storage in a temp
directory, and cloud sync disabled — tests never touch Supabase or the live
database.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
from dotenv import dotenv_values
from sqlalchemy.engine import make_url

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

_configured = os.environ.get("TEST_DATABASE_URL") or dotenv_values(BACKEND / ".env").get("DATABASE_URL")
if not _configured:
    raise RuntimeError("Set TEST_DATABASE_URL or DATABASE_URL in .env to run the integration tests")
_url = make_url(_configured)
if not str(_url.database).endswith("_test"):
    _url = _url.set(database=f"{_url.database}_test")
TEST_DATABASE_URL = _url.render_as_string(hide_password=False)
_STORAGE = tempfile.mkdtemp(prefix="alty-test-storage-")

os.environ.update(
    DATABASE_URL=TEST_DATABASE_URL,
    SUPABASE_URL="",
    SUPABASE_SERVICE_ROLE_KEY="",
    CLOUD_SYNC_ENABLED="false",
    DOCUMENT_STORAGE_BACKEND="local",
    DOCUMENT_STORAGE_DIR=_STORAGE,
    INITIAL_ADMIN_PASSWORD="",
    SECRET_KEY="test-secret-key-for-integration-tests",
    FORECAST_MIN_MONTHS="6",
    # Never call live routing/traffic providers from tests, whatever .env says.
    ROUTING_PROVIDER="osrm",
    TRAFFIC_PROVIDER="none",
    TOMTOM_API_KEY="",
)


def _create_database() -> None:
    from sqlalchemy import create_engine, text

    assert _url.database.endswith("_test"), "refusing to recreate a non-test database"
    admin = create_engine(_url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(text(f'DROP DATABASE IF EXISTS "{_url.database}" WITH (FORCE)'))
        connection.execute(text(f'CREATE DATABASE "{_url.database}"'))
    admin.dispose()
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND, env=os.environ.copy(), capture_output=True, text=True, timeout=300,
    )
    if result.returncode != 0:
        raise RuntimeError("alembic upgrade head failed:\n" + result.stderr[-4000:])


_create_database()

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.core.database import SessionLocal, engine  # noqa: E402
from app.core.security import get_password_hash  # noqa: E402
from app.models.agent import Agent  # noqa: E402
from app.models.user import User  # noqa: E402
from main import app  # noqa: E402

BUSINESS_TABLES = (
    "notification_reads", "agent_reviews", "audit_events", "document_audit_events", "property_media", "transactions", "clients",
    "documents", "document_folders", "property_listings", "partners", "agents", "users",
)

# Synthetic agents used by the ingestion test documents (test DB only).
TEST_AGENTS = [
    ("AGT-0003", "Angela Cruz", "Quezon City"),
    ("AGT-0005", "Sofia Mendoza", "Parañaque City"),
    ("AGT-0006", "Daniel Flores", "Imus, Cavite"),
    ("AGT-0007", "Patricia Ramos", "Bacoor, Cavite"),
]


@pytest.fixture(autouse=True)
def clean_database():
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE " + ", ".join(BUSINESS_TABLES) + " RESTART IDENTITY CASCADE"))
    from app.api.v1 import client_portal, maps

    maps.map_limiter._hits.clear()
    client_portal.auth_limiter._hits.clear()
    from app.api.v1 import auth as staff_auth

    staff_auth.login_limiter._hits.clear()
    yield


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _make_user(username: str, role: str, password: str = "password123") -> None:
    with SessionLocal() as session:
        session.add(User(username=username, full_name=username.title(), role=role,
                         password_hash=get_password_hash(password), is_active=True))
        session.commit()


@pytest.fixture
def api():
    with TestClient(app) as client:
        yield client


def login(api: TestClient, username: str, password: str = "password123") -> dict:
    response = api.post("/api/v1/auth/login", data={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def admin(api):
    _make_user("admin", "Administrator")
    return login(api, "admin")


@pytest.fixture
def employee(api):
    _make_user("employee", "Employee")
    return login(api, "employee")


@pytest.fixture
def agents():
    with SessionLocal() as session:
        for agent_id, name, location in TEST_AGENTS:
            session.add(Agent(agent_id=agent_id, full_name=name, agent_location=location,
                              status="ACTIVE", sync_status="SYNCED"))
        session.commit()
    return [agent_id for agent_id, _, _ in TEST_AGENTS]
