from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    EMPLOYEE,
    canonical_role,
    create_access_token,
    get_current_user,
    get_password_hash,
    permissions_for,
    verify_password,
)
from app.models.user import User
from app.schemas.auth import CurrentUser, Token, UserRegister
from app.services.audit import record_audit, record_audit_now

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
    }


@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        record_audit_now(db, "LOGIN_FAILED", actor=form_data.username[:120] or "UNKNOWN",
                         entity_type="users", result="FAILED",
                         details={"reason": "invalid credentials"})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        record_audit_now(db, "LOGIN_FAILED", actor=user, entity_type="users", entity_id=user.id,
                         result="FAILED", details={"reason": "account inactive"})
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account is inactive")

    user.last_login_at = datetime.utcnow()
    record_audit(db, "LOGIN", actor=user, entity_type="users", entity_id=user.id)
    db.commit()
    access_token = create_access_token(
        subject=user.username,
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=CurrentUser)
def me(user: User = Depends(get_current_user)):
    return current_user_payload(user)


@router.post("/logout", status_code=204)
def logout(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Tokens are stateless; the client discards its token. Logged for audit."""
    record_audit(db, "LOGOUT", actor=user, entity_type="users", entity_id=user.id)
    db.commit()


@router.post("/register", status_code=201)
def register(payload: UserRegister, db: Session = Depends(get_db)):
    """Self-registration always creates a least-privilege Employee account."""
    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists")
    user = User(
        username=payload.username,
        full_name=payload.full_name,
        role=EMPLOYEE,
        password_hash=get_password_hash(payload.password),
        is_active=True,
    )
    db.add(user)
    try:
        db.flush()
        record_audit(db, "USER_REGISTERED", actor=user, entity_type="users", entity_id=user.id,
                     details={"role": EMPLOYEE})
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists") from exc
    db.refresh(user)
    return {"message": "Account created successfully", "user": current_user_payload(user)}
