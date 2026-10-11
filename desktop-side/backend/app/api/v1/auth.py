from datetime import datetime, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.client_ip import client_ip
from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    canonical_role,
    create_session_token,
    get_current_user,
    is_client,
    permissions_for,
    verify_password,
    verify_password_or_dummy,
)
from app.models.user import User
from app.schemas.auth import CurrentUser, PasswordChange, PasswordResetConfirm, PasswordResetRequest, Token
from app.services import auth_throttle as throttle
from app.services import password_reset as reset_service
from app.services.audit import record_audit, record_audit_now
from app.services.captcha import verify_turnstile
from app.services.profile_photos import photo_version

router = APIRouter(prefix="/auth", tags=["auth"])


def current_user_payload(user: User) -> dict:
    role = canonical_role(user.role)
    return {
        "id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "role": role,
        "permissions": permissions_for(role),
        "branch_id": user.branch_id,
        "is_active": user.is_active,
        "last_login_at": user.last_login_at,
        "agent_id": user.agent_id,
        "photo_version": photo_version(user),
        "email": user.email,
    }


# Staff sign-in is reachable from the public website, so it is throttled in
# the database (shared by every API instance, kept across restarts):
#   * per IP: at most LOGIN_MAX_ATTEMPTS_PER_IP attempts in 15 minutes;
#   * per account name (any name, existing or not): progressive temporary
#     cooldowns after repeated failures (LOGIN_COOLDOWN_STEPS);
#   * the security check (Turnstile, when configured) after
#     LOGIN_CAPTCHA_AFTER_FAILURES failures for the name, or twice that per IP.
# Errors never say whether an account exists.
IP_WINDOW = timedelta(minutes=15)
BAD_CREDENTIALS = "Incorrect username or password"
CAPTCHA_HEADER = "X-Captcha-Required"
CHECK_REQUIRED = "Complete the security check, then sign in again."


def _too_many(detail: str, seconds: int) -> HTTPException:
    return HTTPException(status_code=429, detail=detail, headers={"Retry-After": str(max(1, seconds))})


def _wait_text(seconds: int) -> str:
    minutes = max(1, -(-seconds // 60))
    return f"{minutes} minute{'s' if minutes != 1 else ''}"


@router.post("/login", response_model=Token)
def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends(),
          captcha_token: str | None = Form(default=None), db: Session = Depends(get_db)):
    ip = client_ip(request)
    account = throttle.normalize_identifier(form_data.username)[:120]
    if throttle.count(db, throttle.LOGIN_IP, ip, IP_WINDOW) >= settings.LOGIN_MAX_ATTEMPTS_PER_IP:
        raise _too_many("Too many sign-in attempts from this network. Please wait a few minutes and try again.", 900)
    wait = throttle.login_cooldown_seconds(db, account)
    if wait:
        raise _too_many(f"Too many failed sign-in attempts. Try again in {_wait_text(wait)}.", wait)
    if throttle.login_needs_captcha(db, account, ip) and not verify_turnstile(captcha_token, ip):
        throttle.record(db, throttle.LOGIN_IP, ip)
        record_audit_now(db, "LOGIN_CAPTCHA_FAILED", actor=account or "UNKNOWN", entity_type="users",
                         result="FAILED", details={"reason": "security check missing or rejected"})
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=CHECK_REQUIRED,
                            headers={"WWW-Authenticate": "Bearer", CAPTCHA_HEADER: "true"})

    user = db.query(User).filter(User.username == form_data.username).first()
    if not verify_password_or_dummy(form_data.password, user):
        throttle.record(db, throttle.LOGIN_ACCOUNT, account)
        throttle.record(db, throttle.LOGIN_IP, ip)
        record_audit_now(db, "LOGIN_FAILED", actor=form_data.username[:120] or "UNKNOWN",
                         entity_type="users", result="FAILED",
                         details={"reason": "invalid credentials"})
        headers = {"WWW-Authenticate": "Bearer"}
        if throttle.login_needs_captcha(db, account, ip):
            headers[CAPTCHA_HEADER] = "true"
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=BAD_CREDENTIALS, headers=headers)
    # The password was right: from here on the caller owns the account.
    throttle.record(db, throttle.LOGIN_IP, ip, success=True)
    if not user.is_active:
        record_audit_now(db, "LOGIN_FAILED", actor=user, entity_type="users", entity_id=user.id,
                         result="FAILED", details={"reason": "account inactive"})
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account is inactive")
    if is_client(user):
        # Website client accounts sign in through /client/login only.
        record_audit_now(db, "LOGIN_FAILED", actor=user, entity_type="users", entity_id=user.id,
                         result="FAILED", details={"reason": "client account on staff login"})
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Client accounts can only sign in on the Abellar Realty website.")

    throttle.record(db, throttle.LOGIN_ACCOUNT, account, success=True)
    user.last_login_at = datetime.utcnow()
    record_audit(db, "LOGIN", actor=user, entity_type="users", entity_id=user.id)
    db.commit()
    return {"access_token": create_session_token(user), "token_type": "bearer"}


@router.get("/security-config")
def security_config():
    """Public settings the sign-in pages need (the Turnstile site key is public by design)."""
    return {
        "captcha_site_key": settings.TURNSTILE_SITE_KEY.strip() if settings.captcha_enabled else None,
        "password_reset_enabled": settings.password_reset_enabled,
        "password_reset_minutes": settings.password_reset_ttl_minutes,
    }


RESET_SENT_MESSAGE = ("If that email belongs to a staff account, we've sent it a link to reset the password. "
                      "Check the inbox and the spam folder.")


@router.post("/password-reset/request", status_code=202)
def request_password_reset(payload: PasswordResetRequest, request: Request, background: BackgroundTasks,
                           db: Session = Depends(get_db)):
    """Always the same answer, whether or not the address belongs to an
    account; the email itself is sent after the response."""
    if not settings.password_reset_enabled:
        raise HTTPException(status_code=503,
                            detail="Password recovery isn't available. Ask the Administrator to reset it.")
    ip = client_ip(request)
    if (settings.captcha_enabled
            and throttle.count(db, throttle.RESET_IP, ip, timedelta(hours=1)) >= 3
            and not verify_turnstile(payload.captcha_token, ip)):
        raise HTTPException(status_code=400, detail="Complete the security check, then try again.",
                            headers={CAPTCHA_HEADER: "true"})
    message = reset_service.request_reset(db, payload.email, ip)
    if message is not None:
        background.add_task(reset_service.send_reset_email, message)
    return {"message": RESET_SENT_MESSAGE}


@router.post("/password-reset/confirm")
def confirm_password_reset(payload: PasswordResetConfirm, request: Request, background: BackgroundTasks,
                           db: Session = Depends(get_db)):
    user = reset_service.confirm_reset(db, payload.token, payload.new_password, client_ip(request))
    background.add_task(reset_service.send_password_changed_notice, user.email, user.full_name)
    return {"message": "Your password was changed. Sign in with the new password."}


@router.get("/me", response_model=CurrentUser)
def me(user: User = Depends(get_current_user)):
    return current_user_payload(user)


@router.post("/change-password")
def change_password(payload: PasswordChange, background: BackgroundTasks, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    """Change your own password (the current one is required). Every other
    session of the account ends; the response carries a new token for this one."""
    account = throttle.normalize_identifier(user.username)
    wait = throttle.login_cooldown_seconds(db, account)
    if wait:
        raise _too_many(f"Too many incorrect passwords. Try again in {_wait_text(wait)}.", wait)
    if not verify_password(payload.current_password, user.password_hash):
        throttle.record(db, throttle.LOGIN_ACCOUNT, account)
        record_audit(db, "PASSWORD_CHANGE_FAILED", actor=user, entity_type="users", entity_id=user.id,
                     result="FAILED")
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The current password is incorrect")
    if payload.new_password == payload.current_password:
        raise HTTPException(status_code=422, detail="Choose a password different from the current one")
    reset_service.set_password(user, payload.new_password)
    record_audit(db, "PASSWORD_CHANGED", actor=user, entity_type="users", entity_id=user.id)
    db.commit()
    background.add_task(reset_service.send_password_changed_notice, user.email, user.full_name)
    return {"access_token": create_session_token(user), "token_type": "bearer"}


@router.post("/logout", status_code=204)
def logout(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Tokens are stateless; the client discards its token. Logged for audit."""
    record_audit(db, "LOGOUT", actor=user, entity_type="users", entity_id=user.id)
    db.commit()


@router.post("/register", status_code=403)
def register(request: Request, db: Session = Depends(get_db)):
    """Staff accounts are created only by the Administrator (Users & Access).
    Kept as an explicit refusal so older desktop builds show a clear message."""
    record_audit_now(db, "STAFF_SELF_REGISTRATION_BLOCKED", actor="UNKNOWN", entity_type="users",
                     result="FAILED", details={"ip": client_ip(request)})
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                        detail="Self-registration is disabled. Accounts are created by the Administrator.")
