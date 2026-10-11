"""Staff sign-in protection and password recovery (security requirements).

Email is captured in memory (never sent) and Cloudflare is never called:
the Turnstile check is replaced per test.
"""

import threading
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update

from app.api.v1 import auth as auth_api
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import get_password_hash
from app.models.auth_security import PasswordResetToken
from app.models.user import User
from app.services import email_service
from main import app
from tests.conftest import _make_user, login

STAFF_URL = "https://alty-msa.example.app"
GENERIC = auth_api.RESET_SENT_MESSAGE


@pytest.fixture
def mail(monkeypatch):
    outbox: list[dict] = []
    monkeypatch.setattr(email_service, "outbox", outbox)
    monkeypatch.setattr(settings, "STAFF_APP_URL", STAFF_URL)
    monkeypatch.setattr(settings, "EMAIL_PROVIDER", "brevo")
    monkeypatch.setattr(settings, "EMAIL_FROM", "no-reply@example.app")
    return outbox


def _staff(username: str, email: str | None, role: str = "Employee", active: bool = True,
           password: str = "password123") -> int:
    with SessionLocal() as session:
        user = User(username=username, full_name=username.title(), role=role, email=email, is_active=active,
                    password_hash=get_password_hash(password))
        session.add(user)
        session.commit()
        return user.id


def _request(api, email: str, **extra):
    return api.post("/api/v1/auth/password-reset/request", json={"email": email, **extra})


def _token_from(message: dict) -> str:
    link = message["text"].split(STAFF_URL, 1)[1].split()[0]
    assert link.startswith("/manage/reset-password#token=")
    return link.split("#token=", 1)[1]


# ---- sign-in -------------------------------------------------------------------

def test_unknown_account_and_wrong_password_look_the_same(api):
    _staff("realperson", "real@example.com")
    unknown = api.post("/api/v1/auth/login", data={"username": "nobody-here", "password": "whatever1"})
    wrong = api.post("/api/v1/auth/login", data={"username": "realperson", "password": "whatever1"})
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json() == wrong.json() == {"detail": "Incorrect username or password"}


def test_cooldowns_are_progressive_and_apply_to_any_name(api, monkeypatch):
    monkeypatch.setattr(settings, "LOGIN_COOLDOWN_STEPS", "3:60,6:600")
    for name in ("ghost-user", "realperson"):  # an existing and a non-existing name behave alike
        if name == "realperson":
            _staff(name, None)
        for _ in range(3):
            assert api.post("/api/v1/auth/login", data={"username": name, "password": "bad-pass"}).status_code == 401
        blocked = api.post("/api/v1/auth/login", data={"username": name, "password": "password123"})
        assert blocked.status_code == 429 and 0 < int(blocked.headers["Retry-After"]) <= 60
    # The cooldown is temporary: once it has passed, the right password works again.
    with SessionLocal() as session:
        session.execute(update(auth_api.throttle.AuthAttempt).values(
            created_at=datetime.utcnow() - timedelta(minutes=2)))
        session.commit()
    assert api.post("/api/v1/auth/login", data={"username": "realperson", "password": "password123"}).status_code == 200


def test_success_resets_the_failure_count(api, monkeypatch):
    monkeypatch.setattr(settings, "LOGIN_COOLDOWN_STEPS", "3:60")
    _staff("steady", None)
    for _ in range(2):
        api.post("/api/v1/auth/login", data={"username": "steady", "password": "bad-pass"})
    assert login(api, "steady")
    for _ in range(2):
        assert api.post("/api/v1/auth/login", data={"username": "steady", "password": "bad-pass"}).status_code == 401


def test_per_ip_limit(api, monkeypatch):
    monkeypatch.setattr(settings, "LOGIN_MAX_ATTEMPTS_PER_IP", 4)
    for index in range(4):
        api.post("/api/v1/auth/login", data={"username": f"spray{index}", "password": "bad-pass"})
    assert api.post("/api/v1/auth/login", data={"username": "fresh", "password": "x"}).status_code == 429


def test_captcha_required_after_failures_and_verified_on_the_server(api, monkeypatch):
    monkeypatch.setattr(settings, "TURNSTILE_SITE_KEY", "site-key")
    monkeypatch.setattr(settings, "TURNSTILE_SECRET_KEY", "secret-key")
    monkeypatch.setattr(settings, "LOGIN_CAPTCHA_AFTER_FAILURES", 2)
    accepted = {"good-token"}
    monkeypatch.setattr(auth_api, "verify_turnstile", lambda token, ip=None: token in accepted)
    _staff("checked", None)
    assert api.get("/api/v1/auth/security-config").json()["captcha_site_key"] == "site-key"
    api.post("/api/v1/auth/login", data={"username": "checked", "password": "bad-pass"})
    second = api.post("/api/v1/auth/login", data={"username": "checked", "password": "bad-pass"})
    assert second.headers.get("X-Captcha-Required") == "true"
    # Without a token, or with a rejected one, even the right password is refused.
    for token in (None, "forged-token"):
        data = {"username": "checked", "password": "password123", **({"captcha_token": token} if token else {})}
        refused = api.post("/api/v1/auth/login", data=data)
        assert refused.status_code == 401 and refused.headers.get("X-Captcha-Required") == "true"
    ok = api.post("/api/v1/auth/login",
                  data={"username": "checked", "password": "password123", "captcha_token": "good-token"})
    assert ok.status_code == 200


def test_spoofed_forwarded_for_does_not_change_the_ip(api, monkeypatch):
    monkeypatch.setattr(settings, "LOGIN_MAX_ATTEMPTS_PER_IP", 3)
    monkeypatch.setattr(settings, "TRUSTED_PROXY_HOPS", 1)
    for index in range(3):
        # The visitor puts a new fake address first; the proxy's entry (last) stays the same.
        api.post("/api/v1/auth/login", data={"username": f"u{index}", "password": "bad"},
                 headers={"X-Forwarded-For": f"10.0.0.{index}, 203.0.113.9"})
    blocked = api.post("/api/v1/auth/login", data={"username": "u9", "password": "bad"},
                       headers={"X-Forwarded-For": "10.9.9.9, 203.0.113.9"})
    assert blocked.status_code == 429


def test_cloudflare_header_is_used_when_configured(api, admin, monkeypatch):
    monkeypatch.setattr(settings, "CLIENT_IP_HEADER", "cf-connecting-ip")
    check = api.get("/api/v1/system/security-check", headers={**admin, "CF-Connecting-IP": "198.51.100.7",
                                                                "X-Forwarded-For": "1.2.3.4"})
    assert check.status_code == 200 and check.json()["detected_client_ip"] == "198.51.100.7"
    assert "SECRET" not in str(check.json()).upper().replace("SECRET_KEY_IS_DEFAULT", "")


def test_security_check_is_admin_only(api, employee):
    assert api.get("/api/v1/system/security-check", headers=employee).status_code == 403
    assert api.get("/api/v1/system/security-check").status_code == 401


# ---- access control --------------------------------------------------------------

def test_client_accounts_cannot_use_staff_endpoints(api):
    signup = api.post("/api/v1/client/register", json={
        "full_name": "Ana Reyes", "email": "ana@example.com", "phone_number": "0917 111 2222",
        "password": "s3cret-pass"})
    client = {"Authorization": f"Bearer {signup.json()['access_token']}"}
    for path in ("/api/v1/auth/me", "/api/v1/users", "/api/v1/transactions", "/api/v1/dashboard/summary"):
        assert api.get(path, headers=client).status_code == 403, path
    assert api.post("/api/v1/auth/login", data={"username": "ana@example.com", "password": "s3cret-pass"}).status_code == 403


def test_no_role_escalation(api, admin, employee):
    _make_user("gm", "General Manager")
    manager = login(api, "gm")
    me = api.get("/api/v1/auth/me", headers=employee).json()
    new_admin = {"username": "sneaky", "full_name": "S", "password": "password123", "role": "Administrator"}
    assert api.post("/api/v1/users", headers=employee, json=new_admin).status_code == 403
    assert api.post("/api/v1/users", headers=manager, json=new_admin).status_code == 403
    assert api.put(f"/api/v1/users/{me['id']}", headers=employee, json={"role": "Administrator"}).status_code == 403
    assert api.put(f"/api/v1/users/{me['id']}", headers=manager, json={"role": "Administrator"}).status_code == 403
    # Unknown fields (e.g. smuggling a role into self-service calls) are rejected.
    assert api.post("/api/v1/auth/register", json={"username": "x", "password": "password123", "full_name": "X",
                                                   "role": "Administrator"}).status_code == 403


def test_admin_sets_unique_staff_email(api, admin):
    created = api.post("/api/v1/users", headers=admin, json={
        "username": "mailed", "full_name": "Mailed", "password": "password123", "role": "Employee",
        "email": "  Mailed.Person@Example.com "})
    assert created.status_code == 201 and created.json()["email"] == "mailed.person@example.com"
    clash = api.post("/api/v1/users", headers=admin, json={
        "username": "other", "full_name": "Other", "password": "password123", "role": "Employee",
        "email": "MAILED.person@example.com"})
    assert clash.status_code == 409
    assert api.post("/api/v1/users", headers=admin, json={
        "username": "bad", "full_name": "Bad", "password": "password123", "role": "Employee",
        "email": "not-an-email"}).status_code == 422
    user_id = created.json()["id"]
    assert api.put(f"/api/v1/users/{user_id}", headers=admin, json={"email": "new@example.com"}).json()["email"] == "new@example.com"
    assert api.get("/api/v1/auth/me", headers=login(api, "mailed")).json()["email"] == "new@example.com"


# ---- password recovery -------------------------------------------------------------

def test_unknown_and_registered_email_get_the_same_answer(api, mail):
    _staff("known", "known@example.com")
    _staff("sleeping", "sleeping@example.com", active=False)
    answers = [_request(api, email) for email in
               ("known@example.com", "nobody@example.com", "sleeping@example.com", "KNOWN@example.com ")]
    assert {response.status_code for response in answers} == {202}
    assert {response.text for response in answers} == {answers[0].text}
    assert answers[0].json() == {"message": GENERIC}
    # Only the eligible, active staff account got an email (the repeat is inside the resend interval).
    assert [message["to"] for message in mail] == ["known@example.com"]


def test_client_accounts_cannot_recover_through_staff_flow(api, mail):
    api.post("/api/v1/client/register", json={
        "full_name": "Ana Reyes", "email": "ana@example.com", "phone_number": "0917 111 2222",
        "password": "s3cret-pass"})
    with SessionLocal() as session:  # even if a client row somehow carried an email
        session.execute(update(User).where(User.username == "ana@example.com").values(email="ana@example.com"))
        session.commit()
    assert _request(api, "ana@example.com").status_code == 202
    assert mail == []


def test_repeated_requests_do_not_send_unlimited_emails(api, mail, monkeypatch):
    monkeypatch.setattr(settings, "PASSWORD_RESET_MIN_EMAIL_INTERVAL_SECONDS", 0)
    monkeypatch.setattr(settings, "PASSWORD_RESET_PER_EMAIL_PER_HOUR", 3)
    monkeypatch.setattr(settings, "PASSWORD_RESET_PER_IP_PER_HOUR", 100)
    _staff("spammed", "spammed@example.com")
    for _ in range(8):
        assert _request(api, "spammed@example.com").status_code == 202
    assert len(mail) == 3


def test_resend_interval(api, mail):
    _staff("waiting", "waiting@example.com")
    _request(api, "waiting@example.com")
    _request(api, "waiting@example.com")
    assert len(mail) == 1


def test_reset_requests_are_limited_per_ip(api, mail, monkeypatch):
    monkeypatch.setattr(settings, "PASSWORD_RESET_PER_IP_PER_HOUR", 2)
    assert _request(api, "a@example.com").status_code == 202
    assert _request(api, "b@example.com").status_code == 202
    assert _request(api, "c@example.com").status_code == 429


def test_reset_captcha_after_suspicious_volume(api, mail, monkeypatch):
    monkeypatch.setattr(settings, "TURNSTILE_SITE_KEY", "site-key")
    monkeypatch.setattr(settings, "TURNSTILE_SECRET_KEY", "secret-key")
    monkeypatch.setattr(auth_api, "verify_turnstile", lambda token, ip=None: token == "good-token")
    for index in range(3):
        assert _request(api, f"x{index}@example.com").status_code == 202
    refused = _request(api, "x9@example.com", captcha_token="bad")
    assert refused.status_code == 400 and refused.headers.get("X-Captcha-Required") == "true"
    assert _request(api, "x9@example.com", captcha_token="good-token").status_code == 202


def test_reset_disabled_without_configuration(api, monkeypatch):
    monkeypatch.setattr(settings, "STAFF_APP_URL", "")
    assert api.get("/api/v1/auth/security-config").json()["password_reset_enabled"] is False
    assert _request(api, "someone@example.com").status_code == 503


def test_full_reset_ends_sessions_and_link_works_once(api, mail):
    user_id = _staff("forgetful", "forgetful@example.com")
    old_session = login(api, "forgetful")
    # A forged Host header must not change where the link points.
    assert api.post("/api/v1/auth/password-reset/request", json={"email": "forgetful@example.com"},
                    headers={"Host": "evil.example.net"}).status_code == 202
    token = _token_from(mail[0])
    assert "evil" not in mail[0]["text"] and "password123" not in mail[0]["text"]
    with SessionLocal() as session:  # only the hash is stored
        stored = session.query(PasswordResetToken).filter_by(user_id=user_id).one()
        assert stored.token_hash != token and len(stored.token_hash) == 64
        assert timedelta(minutes=15) <= stored.expires_at - stored.created_at <= timedelta(minutes=30)

    done = api.post("/api/v1/auth/password-reset/confirm", json={"token": token, "new_password": "Fresh-Pass-2026"})
    assert done.status_code == 200
    assert api.get("/api/v1/auth/me", headers=old_session).status_code == 401  # signed out everywhere
    assert login(api, "forgetful", "Fresh-Pass-2026")
    assert api.post("/api/v1/auth/login", data={"username": "forgetful", "password": "password123"}).status_code == 401
    assert mail[-1]["subject"] == "Your Alty MSA password was changed"
    reused = api.post("/api/v1/auth/password-reset/confirm", json={"token": token, "new_password": "Another-Pass-1"})
    assert reused.status_code == 400 and reused.json()["detail"] == auth_api.reset_service.INVALID_LINK


def test_invalid_expired_and_replaced_links(api, mail, monkeypatch):
    monkeypatch.setattr(settings, "PASSWORD_RESET_MIN_EMAIL_INTERVAL_SECONDS", 0)
    _staff("late", "late@example.com")
    bogus = api.post("/api/v1/auth/password-reset/confirm",
                     json={"token": "x" * 43, "new_password": "Fresh-Pass-2026"})
    assert bogus.status_code == 400
    _request(api, "late@example.com")
    first = _token_from(mail[0])
    _request(api, "late@example.com")
    second = _token_from(mail[1])
    # A newer link replaces the older one.
    assert api.post("/api/v1/auth/password-reset/confirm",
                    json={"token": first, "new_password": "Fresh-Pass-2026"}).status_code == 400
    with SessionLocal() as session:
        session.execute(update(PasswordResetToken).values(expires_at=datetime.utcnow() - timedelta(seconds=1)))
        session.commit()
    expired = api.post("/api/v1/auth/password-reset/confirm", json={"token": second, "new_password": "Fresh-Pass-2026"})
    assert expired.status_code == 400 and expired.json() == bogus.json()
    assert api.post("/api/v1/auth/password-reset/confirm",
                    json={"token": second, "new_password": "short"}).status_code == 422


def test_concurrent_use_of_one_link_succeeds_once(api, mail):
    _staff("racer", "racer@example.com")
    _request(api, "racer@example.com")
    token = _token_from(mail[0])
    results: list[int] = []
    barrier = threading.Barrier(6)

    def attempt(index: int) -> None:
        with TestClient(app) as client:
            barrier.wait()
            response = client.post("/api/v1/auth/password-reset/confirm",
                                   json={"token": token, "new_password": f"Race-Pass-{index}-x"})
            results.append(response.status_code)

    threads = [threading.Thread(target=attempt, args=(index,)) for index in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(results) == [200] + [400] * 5


def test_admin_reset_ends_sessions(api, admin, mail):
    user_id = _staff("managed", "managed@example.com")
    session = login(api, "managed")
    assert api.post(f"/api/v1/users/{user_id}/reset-password", headers=admin,
                    json={"password": "Admin-Set-Pass-1"}).status_code == 204
    assert api.get("/api/v1/auth/me", headers=session).status_code == 401
    assert [message["to"] for message in mail] == ["managed@example.com"]


def test_no_secrets_in_audit_log(api, admin, mail):
    _staff("audited", "audited@example.com")
    _request(api, "audited@example.com")
    token = _token_from(mail[0])
    api.post("/api/v1/auth/password-reset/confirm", json={"token": token, "new_password": "Fresh-Pass-2026"})
    api.post("/api/v1/auth/login", data={"username": "audited", "password": "Wrong-Guess-99"})
    log = api.get("/api/v1/audit", headers=admin, params={"limit": 200}).text
    for secret in (token, "Fresh-Pass-2026", "Wrong-Guess-99"):
        assert secret not in log
    assert "PASSWORD_RESET_REQUESTED" in log and "PASSWORD_RESET_COMPLETED" in log


def test_desktop_style_login_still_works(api):
    """The desktop app posts the OAuth2 form and reads access_token / detail strings."""
    _staff("desk", None)
    ok = api.post("/api/v1/auth/login", data={"username": "desk", "password": "password123"})
    assert ok.status_code == 200 and ok.json()["token_type"] == "bearer"
    bad = api.post("/api/v1/auth/login", data={"username": "desk", "password": "nope-nope"})
    assert isinstance(bad.json()["detail"], str)
