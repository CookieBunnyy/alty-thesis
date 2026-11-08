"""Forgot password without email: the Administrator approves the request and
only the browser that asked can choose the new password."""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import update

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.auth_security import PasswordResetRequest
from tests.conftest import _make_user, login

ASK = "/api/v1/auth/password-reset/ask"
STATUS = "/api/v1/auth/password-reset/status"
CONFIRM = "/api/v1/auth/password-reset/confirm"


@pytest.fixture(autouse=True)
def no_email(monkeypatch):
    monkeypatch.setattr(settings, "STAFF_APP_URL", "")  # = email recovery off -> Administrator approval


def _ask(api, identifier, **extra):
    reply = api.post(ASK, json={"identifier": identifier, **extra})
    assert reply.status_code == 202, reply.text
    return reply.json()


def _status(api, token):
    return api.post(STATUS, json={"token": token}).json()["status"]


def _open(api, admin):
    return api.get("/api/v1/password-requests", headers=admin).json()


def test_mode_is_admin_without_email(api, monkeypatch):
    assert api.get("/api/v1/auth/security-config").json()["password_reset_mode"] == "admin"
    # Email configured but not chosen: still the Administrator.
    monkeypatch.setattr(settings, "STAFF_APP_URL", "https://alty-msa.example.app")
    monkeypatch.setattr(settings, "EMAIL_PROVIDER", "brevo")
    assert api.get("/api/v1/auth/security-config").json()["password_reset_mode"] == "admin"


def test_request_approve_and_set_password(api, admin):
    _make_user("seller1", "Filing Manager")
    old_session = login(api, "seller1")
    asked = _ask(api, "SELLER1", note="Lost my notes")
    assert len(asked["code"]) == 7 and _status(api, asked["request_token"]) == "PENDING"
    # Not usable before approval.
    early = api.post(CONFIRM, json={"token": asked["request_token"], "new_password": "Brand-New-2026"})
    assert early.status_code == 400

    # The Administrator sees it (list + notification) with the same check code.
    [item] = _open(api, admin)
    assert item["user"]["username"] == "seller1" and item["code"] == asked["code"] and item["note"] == "Lost my notes"
    bell = api.get("/api/v1/notifications", headers=admin).json()["items"]
    assert any(n["key"] == f"password-request:{item['id']}" and asked["code"] in n["message"] for n in bell)

    approved = api.post(f"/api/v1/password-requests/{item['id']}/approve", headers=admin)
    assert approved.status_code == 200 and approved.json()["status"] == "APPROVED"
    assert _status(api, asked["request_token"]) == "APPROVED"
    assert api.post(f"/api/v1/password-requests/{item['id']}/approve", headers=admin).status_code == 409

    done = api.post(CONFIRM, json={"token": asked["request_token"], "new_password": "Brand-New-2026"})
    assert done.status_code == 200, done.text
    assert _status(api, asked["request_token"]) == "COMPLETED"
    assert api.get("/api/v1/auth/me", headers=old_session).status_code == 401  # other sessions end
    assert login(api, "seller1", "Brand-New-2026")
    # Works once.
    assert api.post(CONFIRM, json={"token": asked["request_token"], "new_password": "Again-2026x"}).status_code == 400
    assert _open(api, admin) == []


def test_denied_request_cannot_reset(api, admin):
    _make_user("filer", "Filing Manager")
    asked = _ask(api, "filer")
    [item] = _open(api, admin)
    assert api.post(f"/api/v1/password-requests/{item['id']}/deny", headers=admin).json()["status"] == "DENIED"
    assert _status(api, asked["request_token"]) == "DENIED"
    assert api.post(CONFIRM, json={"token": asked["request_token"], "new_password": "Brand-New-2026"}).status_code == 400
    assert login(api, "filer")  # password unchanged


def test_unknown_accounts_look_the_same_and_clients_are_ignored(api, admin):
    _make_user("buyer", "Client")
    unknown = _ask(api, "nobody-here")
    client = _ask(api, "buyer")
    assert set(unknown) == set(client) and _status(api, unknown["request_token"]) == "PENDING"
    assert _open(api, admin) == []


def test_only_the_administrator_decides(api, admin, employee):
    _make_user("filer", "Filing Manager")
    _ask(api, "filer")
    [item] = _open(api, admin)
    assert api.get("/api/v1/password-requests", headers=employee).status_code == 403
    assert api.post(f"/api/v1/password-requests/{item['id']}/approve", headers=employee).status_code == 403
    assert api.post("/api/v1/password-requests/999999/approve", headers=admin).status_code == 404


def test_expired_requests_and_approvals(api, admin):
    _make_user("filer", "Filing Manager")
    asked = _ask(api, "filer")
    [item] = _open(api, admin)
    with SessionLocal() as session:
        session.execute(update(PasswordResetRequest).values(expires_at=datetime.utcnow() - timedelta(minutes=1)))
        session.commit()
    assert _status(api, asked["request_token"]) == "EXPIRED"
    assert api.post(f"/api/v1/password-requests/{item['id']}/approve", headers=admin).status_code == 409
    assert _open(api, admin) == []


def test_open_requests_per_account_are_limited(api, admin, monkeypatch):
    monkeypatch.setattr(settings, "PASSWORD_RESET_PER_EMAIL_PER_HOUR", 50)
    _make_user("filer", "Filing Manager")
    for _ in range(5):
        _ask(api, "filer")
    assert len(_open(api, admin)) == 3


def test_ask_is_off_when_email_recovery_is_configured(api, monkeypatch):
    monkeypatch.setattr(settings, "STAFF_APP_URL", "https://alty-msa.example.app")
    monkeypatch.setattr(settings, "EMAIL_PROVIDER", "brevo")
    monkeypatch.setattr(settings, "PASSWORD_RESET_VIA", "email")
    assert api.get("/api/v1/auth/security-config").json()["password_reset_mode"] == "email"
    assert api.post(ASK, json={"identifier": "anyone"}).status_code == 409
