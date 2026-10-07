"""User administration (administrators) and read access (management)."""

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import (
    ADMINISTRATOR,
    ROLES,
    canonical_role,
    get_current_user,
    get_password_hash,
    permissions_for,
    require_admin,
    require_management,
)
from app.models.agent import Agent
from app.models.role import Role
from app.models.user import User
from app.schemas.user import PasswordReset, UserCreate, UserResponse, UserUpdate
from app.services.audit import record_audit
from app.services.profile_photos import photo_bytes, photo_version, remove_photo, save_photo

router = APIRouter(prefix="/users", tags=["Users"])


def _valid_role(role: str) -> str:
    canonical = canonical_role(role)
    if canonical.casefold() != (role or "").strip().casefold():
        raise HTTPException(status_code=422, detail=f"Unknown role '{role}'. Roles: {', '.join(ROLES)}")
    return canonical


def _serialize(user: User, db: Session | None = None) -> dict:
    data = UserResponse.model_validate(user).model_dump()
    data["role"] = canonical_role(user.role)
    agent = db.get(Agent, user.agent_id) if db is not None and user.agent_id else None
    data["agent_name"] = agent.full_name if agent else None
    data["photo_version"] = photo_version(user)
    return data


def _valid_agent_link(db: Session, agent_id: str | None, user_id: int | None = None) -> str | None:
    """An agent record may be linked to one staff account only."""
    if not agent_id:
        return None
    if db.get(Agent, agent_id) is None:
        raise HTTPException(status_code=422, detail=f"Agent {agent_id} not found")
    other = db.execute(select(User).where(User.agent_id == agent_id)).scalar_one_or_none()
    if other is not None and other.id != user_id:
        raise HTTPException(status_code=409, detail=f"Agent {agent_id} is already linked to @{other.username}")
    return agent_id


def _active_admins(db: Session) -> int:
    return int(db.scalar(select(func.count(User.id)).where(
        func.lower(User.role) == ADMINISTRATOR.casefold(), User.is_active.is_(True)
    )) or 0)


# ---- profile photos ---------------------------------------------------------
# Declared before the /{user_id} routes so "me" isn't read as an id.

def _staff(user: User) -> User:
    if canonical_role(user.role) == "Client":
        raise HTTPException(status_code=403, detail="Staff accounts only")
    return user


@router.put("/me/photo", response_model=UserResponse)
async def upload_my_photo(file: UploadFile = File(...), db: Session = Depends(get_db),
                          user: User = Depends(get_current_user)):
    """Set your own profile photo (cropped to a square)."""
    _staff(user)
    await save_photo(user, "users", user.id, file)
    record_audit(db, "USER_PHOTO_UPDATED", actor=user, entity_type="users", entity_id=user.id)
    db.commit()
    db.refresh(user)
    return _serialize(user, db)


@router.delete("/me/photo", response_model=UserResponse)
def delete_my_photo(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _staff(user)
    remove_photo(user)
    record_audit(db, "USER_PHOTO_REMOVED", actor=user, entity_type="users", entity_id=user.id)
    db.commit()
    db.refresh(user)
    return _serialize(user, db)


@router.get("/{user_id}/photo")
def get_user_photo(user_id: int, db: Session = Depends(get_db), viewer: User = Depends(get_current_user)):
    """A staff member's photo, for signed-in staff only."""
    _staff(viewer)
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="No photo")
    return Response(content=photo_bytes(user), media_type="image/jpeg",
                    headers={"Cache-Control": "private, max-age=86400", "X-Content-Type-Options": "nosniff"})


@router.put("/{user_id}/photo", response_model=UserResponse)
async def upload_user_photo(user_id: int, file: UploadFile = File(...), db: Session = Depends(get_db),
                            actor: User = Depends(require_admin)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    await save_photo(user, "users", user.id, file)
    record_audit(db, "USER_PHOTO_UPDATED", actor=actor, entity_type="users", entity_id=user.id)
    db.commit()
    db.refresh(user)
    return _serialize(user, db)


@router.delete("/{user_id}/photo", response_model=UserResponse)
def delete_user_photo(user_id: int, db: Session = Depends(get_db), actor: User = Depends(require_admin)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    remove_photo(user)
    record_audit(db, "USER_PHOTO_REMOVED", actor=actor, entity_type="users", entity_id=user.id)
    db.commit()
    db.refresh(user)
    return _serialize(user, db)


@router.get("/roles")
def get_roles(db: Session = Depends(get_db), _user: User = Depends(require_management)):
    descriptions = {role.name: role.description for role in db.execute(select(Role)).scalars()}
    return [{"name": role, "description": descriptions.get(role), "permissions": permissions_for(role)}
            for role in ROLES]


@router.get("", response_model=list[UserResponse])
def get_users(db: Session = Depends(get_db), _user: User = Depends(require_management)):
    # Website client accounts are managed through the website, not here.
    staff = select(User).where(func.lower(User.role) != "client").order_by(User.username)
    return [_serialize(user, db) for user in db.execute(staff).scalars()]


@router.post("", response_model=UserResponse, status_code=201)
def create_user(payload: UserCreate, db: Session = Depends(get_db), actor: User = Depends(require_admin)):
    if db.execute(select(User).where(User.username == payload.username)).scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Username already exists")
    user = User(username=payload.username, full_name=payload.full_name, role=_valid_role(payload.role),
                password_hash=get_password_hash(payload.password), is_active=payload.is_active,
                agent_id=_valid_agent_link(db, payload.agent_id))
    db.add(user)
    db.flush()
    record_audit(db, "USER_CREATED", actor=actor, entity_type="users", entity_id=user.id,
                 details={"username": user.username, "role": user.role, "is_active": user.is_active,
                          "agent_id": user.agent_id})
    db.commit()
    db.refresh(user)
    return _serialize(user, db)


@router.put("/{user_id}", response_model=UserResponse)
def update_user(user_id: int, payload: UserUpdate, db: Session = Depends(get_db),
                actor: User = Depends(require_admin)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    changes = payload.model_dump(exclude_unset=True)
    if "role" in changes:
        changes["role"] = _valid_role(changes["role"])
    if "agent_id" in changes:
        changes["agent_id"] = _valid_agent_link(db, changes["agent_id"], user.id)
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
    return _serialize(user, db)


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
