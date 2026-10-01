"""User administration (administrators) and read access (management)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import (
    ADMINISTRATOR,
    ROLES,
    canonical_role,
    get_password_hash,
    permissions_for,
    require_admin,
    require_management,
)
from app.models.role import Role
from app.models.user import User
from app.schemas.user import PasswordReset, UserCreate, UserResponse, UserUpdate
from app.services.audit import record_audit

router = APIRouter(prefix="/users", tags=["Users"])


def _valid_role(role: str) -> str:
    canonical = canonical_role(role)
    if canonical.casefold() != (role or "").strip().casefold():
        raise HTTPException(status_code=422, detail=f"Unknown role '{role}'. Roles: {', '.join(ROLES)}")
    return canonical


def _serialize(user: User) -> dict:
    data = UserResponse.model_validate(user).model_dump()
    data["role"] = canonical_role(user.role)
    return data


def _active_admins(db: Session) -> int:
    return int(db.scalar(select(func.count(User.id)).where(
        func.lower(User.role) == ADMINISTRATOR.casefold(), User.is_active.is_(True)
    )) or 0)


@router.get("/roles")
def get_roles(db: Session = Depends(get_db), _user: User = Depends(require_management)):
    descriptions = {role.name: role.description for role in db.execute(select(Role)).scalars()}
    return [{"name": role, "description": descriptions.get(role), "permissions": permissions_for(role)}
            for role in ROLES]


@router.get("", response_model=list[UserResponse])
def get_users(db: Session = Depends(get_db), _user: User = Depends(require_management)):
    return [_serialize(user) for user in db.execute(select(User).order_by(User.username)).scalars()]


@router.post("", response_model=UserResponse, status_code=201)
def create_user(payload: UserCreate, db: Session = Depends(get_db), actor: User = Depends(require_admin)):
    if db.execute(select(User).where(User.username == payload.username)).scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Username already exists")
    user = User(username=payload.username, full_name=payload.full_name, role=_valid_role(payload.role),
                password_hash=get_password_hash(payload.password), is_active=payload.is_active)
    db.add(user)
    db.flush()
    record_audit(db, "USER_CREATED", actor=actor, entity_type="users", entity_id=user.id,
                 details={"username": user.username, "role": user.role, "is_active": user.is_active})
    db.commit()
    db.refresh(user)
    return _serialize(user)


@router.put("/{user_id}", response_model=UserResponse)
def update_user(user_id: int, payload: UserUpdate, db: Session = Depends(get_db),
                actor: User = Depends(require_admin)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    changes = payload.model_dump(exclude_unset=True)
    if "role" in changes:
        changes["role"] = _valid_role(changes["role"])
    was_admin = canonical_role(user.role) == ADMINISTRATOR and user.is_active
    stays_admin = (
        changes.get("role", canonical_role(user.role)) == ADMINISTRATOR
        and changes.get("is_active", user.is_active)
    )
    if was_admin and not stays_admin and _active_admins(db) <= 1:
        raise HTTPException(
            status_code=409,
            detail="The last active administrator cannot be demoted or deactivated",
        )
    audit_changes = {}
    for key, value in changes.items():
        if getattr(user, key) != value:
            audit_changes[key] = {"old": getattr(user, key), "new": value}
            setattr(user, key, value)
    if audit_changes:
        action = "USER_STATUS_CHANGED" if set(audit_changes) == {"is_active"} else "USER_UPDATED"
        record_audit(db, action, actor=actor, entity_type="users", entity_id=user.id,
                     details={"username": user.username, "changes": audit_changes})
    db.commit()
    db.refresh(user)
    return _serialize(user)


@router.post("/{user_id}/reset-password", status_code=204)
def reset_password(user_id: int, payload: PasswordReset, db: Session = Depends(get_db),
                   actor: User = Depends(require_admin)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    user.password_hash = get_password_hash(payload.password)
    record_audit(db, "USER_PASSWORD_RESET", actor=actor, entity_type="users", entity_id=user.id,
                 details={"username": user.username})
    db.commit()
