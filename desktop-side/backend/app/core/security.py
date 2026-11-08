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
# Same scheme, but a missing token is allowed (public pages that show more to
# signed-in clients).
optional_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

# Canonical role names (users.role). Comparisons are case-insensitive.
# The four user groups confirmed in the Abellar Realty interview:
ADMINISTRATOR = "Administrator"   # Admin / Marketing staff: runs the system day to day
BROKER = "Broker"                 # Broker / company owner: company-wide authority
FILING_MANAGER = "Filing Manager" # sales reports, commission vouchers, documents
SELLER = "Seller"                 # seller / agent: own listings and records only
ROLES = (ADMINISTRATOR, BROKER, FILING_MANAGER, SELLER)
# Website client accounts share the users table, hashing and tokens, but are
# not an internal role: they cannot use any internal endpoint (see
# get_current_user) and cannot be assigned from the Users page. Developers
# never get an account.
CLIENT = "Client"

# Names used before the interview, still accepted on read (tokens, old rows,
# the retired desktop client). Migration 0016 rewrites the stored values.
LEGACY_ROLES = {
    "president": BROKER,
    "general manager": ADMINISTRATOR,
    "employee": FILING_MANAGER,
    "agent": SELLER,
}

MANAGEMENT_ROLES = {ADMINISTRATOR, BROKER}
# Company staff: everyone except sellers (company-wide records and reports).
COMPANY_ROLES = MANAGEMENT_ROLES | {FILING_MANAGER}
FILING_ROLES = COMPANY_ROLES

# Page keys each role may open in the Management System. The API enforces the
# same boundaries independently; this list only drives what the menu shows.
_COMPANY_PAGES = [
    "dashboard", "reports", "properties", "partners", "clients", "transactions", "commissions",
    "documents", "media", "agents", "recruitment", "branches", "workforce", "analytics",
    "forecasting", "dss", "users", "audit", "settings",
]
ROLE_PERMISSIONS: dict[str, list[str]] = {
    ADMINISTRATOR: _COMPANY_PAGES,
    # The owner sees everything; the Users page is read-only for the Broker.
    BROKER: _COMPANY_PAGES,
    FILING_MANAGER: ["dashboard", "reports", "transactions", "commissions", "documents", "properties", "settings"],
    SELLER: ["my-work", "my-listings", "my-deals", "my-commissions", "settings"],
}


def canonical_role(role: str | None) -> str:
    lowered = (role or "").strip().casefold()
    if lowered == CLIENT.casefold():
        return CLIENT
    for name in ROLES:
        if name.casefold() == lowered:
            return name
    # Unknown or legacy names: the legacy mapping, otherwise the least access.
    return LEGACY_ROLES.get(lowered, SELLER)


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


_dummy_hash: str | None = None


def verify_password_or_dummy(plain_password: str, user: User | None) -> bool:
    """Check ``plain_password``; for an unknown account still run one bcrypt
    check, so the response time doesn't reveal whether the account exists."""
    global _dummy_hash
    if user is None:
        if _dummy_hash is None:
            _dummy_hash = get_password_hash("alty-timing-equalizer")
        verify_password(plain_password, _dummy_hash)
        return False
    return verify_password(plain_password, user.password_hash)


def create_access_token(subject: str, expires_delta: timedelta | None = None, session_version: int = 0) -> str:
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    now = datetime.now(timezone.utc)
    # "sv": the account's session version; a password change bumps it, which
    # ends every session started before the change.
    payload = {"sub": subject, "exp": now + expires_delta, "iat": now, "sv": session_version}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_session_token(user: User) -> str:
    return create_access_token(subject=user.username, session_version=user.session_version or 0)


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
        payload = decode_access_token(token)
    except ValueError as exc:
        raise credentials_error from exc

    user = db.query(User).filter(User.username == payload.get("sub")).first()
    if user is None or not user.is_active:
        raise credentials_error
    try:
        version = int(payload.get("sv", 0))
    except (TypeError, ValueError):
        raise credentials_error from None
    if version != (user.session_version or 0):
        raise credentials_error  # signed out by a password change
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


def get_optional_client(
    token: str | None = Depends(optional_oauth2_scheme),
    db: Session = Depends(get_db),
) -> User | None:
    """The signed-in website client, or None (no, expired or staff token)."""
    if not token:
        return None
    try:
        user = _user_from_token(token, db)
    except HTTPException:
        return None
    return user if is_client(user) and user.client_id else None


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


def get_company_user(user: User = Depends(get_current_user)) -> User:
    """Company staff (Administrator, Broker, Filing Manager). Seller accounts
    are refused: company-wide records and reports are not theirs to see."""
    if canonical_role(user.role) not in COMPANY_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Seller accounts can only open their own listings and records.",
        )
    return user


def get_seller_user(user: User = Depends(get_current_user)) -> User:
    """A seller account linked to its seller (agent) record."""
    if canonical_role(user.role) != SELLER or not user.agent_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This page is for seller accounts linked to a seller record.",
        )
    return user
