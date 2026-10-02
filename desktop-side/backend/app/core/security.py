from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.user import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

# Canonical role names (users.role). Comparisons are case-insensitive.
ADMINISTRATOR = "Administrator"
GENERAL_MANAGER = "General Manager"
PRESIDENT = "President"
FILING_MANAGER = "Filing Manager"
AGENT = "Agent"
EMPLOYEE = "Employee"
ROLES = (ADMINISTRATOR, GENERAL_MANAGER, PRESIDENT, FILING_MANAGER, AGENT, EMPLOYEE)
# Website client accounts share the users table, hashing and tokens, but are
# not an internal role: they cannot use any internal endpoint (see
# get_current_user) and cannot be assigned from the desktop Users page.
CLIENT = "Client"

MANAGEMENT_ROLES = {ADMINISTRATOR, GENERAL_MANAGER, PRESIDENT}
FILING_ROLES = MANAGEMENT_ROLES | {FILING_MANAGER}

_ALL_PAGES = [
    "dashboard", "properties", "partners", "clients", "transactions",
    "documents", "media", "agents", "workforce", "analytics",
    "forecasting", "dss", "users", "audit", "settings",
]
# Desktop navigation keys each role may open. The API enforces the same
# boundaries independently; this list only drives what the UI shows.
# Audit Logs are for the Administrator only. Every role keeps "settings",
# but only the Administrator sees system settings there (the rest see
# appearance and language).
ROLE_PERMISSIONS: dict[str, list[str]] = {
    ADMINISTRATOR: _ALL_PAGES,
    GENERAL_MANAGER: [page for page in _ALL_PAGES if page != "audit"],
    PRESIDENT: [page for page in _ALL_PAGES if page not in {"users", "audit"}],
    FILING_MANAGER: ["dashboard", "properties", "partners", "clients", "transactions",
                     "documents", "media", "agents", "settings"],
    AGENT: ["dashboard", "properties", "partners", "clients", "transactions",
            "documents", "media", "agents", "settings"],
    EMPLOYEE: ["dashboard", "properties", "partners", "clients", "transactions",
               "documents", "media", "agents", "settings"],
}


def canonical_role(role: str | None) -> str:
    lowered = (role or "").strip().casefold()
    if lowered == CLIENT.casefold():
        return CLIENT
    for name in ROLES:
        if name.casefold() == lowered:
            return name
    return EMPLOYEE


def permissions_for(role: str | None) -> list[str]:
    return list(ROLE_PERMISSIONS.get(canonical_role(role), []))


def is_client(user: User) -> bool:
    return canonical_role(user.role) == CLIENT


def has_role(user: User, roles: set[str]) -> bool:
    return canonical_role(user.role) in roles


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    expire = datetime.now(timezone.utc) + expires_delta
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError as exc:
        raise ValueError("Invalid token") from exc


def _user_from_token(token: str, db: Session) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        username = decode_access_token(token).get("sub")
    except ValueError as exc:
        raise credentials_error from exc

    user = db.query(User).filter(User.username == username).first()
    if user is None or not user.is_active:
        raise credentials_error
    return user


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Internal (desktop/staff) user. Website client accounts are refused, so
    every internal endpoint stays closed to them."""
    user = _user_from_token(token, db)
    if is_client(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Client accounts can only use the Abellar Realty website.",
        )
    return user


def get_current_client(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Website client account linked to a client record."""
    user = _user_from_token(token, db)
    if not is_client(user) or not user.client_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Sign in with a client account to continue.")
    return user


def require_roles(*roles: str):
    """Dependency factory: the current user must hold one of ``roles``."""
    allowed = {canonical_role(role) for role in roles}

    def dependency(user: User = Depends(get_current_user)) -> User:
        if canonical_role(user.role) not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your role does not permit this action ("
                + ", ".join(sorted(allowed)) + " required).",
            )
        return user

    return dependency


require_management = require_roles(*MANAGEMENT_ROLES)
require_filing = require_roles(*FILING_ROLES)
require_admin = require_roles(ADMINISTRATOR)
