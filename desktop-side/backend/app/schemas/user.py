from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


def _clean_email(value: object) -> object:
    if isinstance(value, str):
        value = value.strip().lower()
        return value or None
    return value


class UserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=3, max_length=100)
    full_name: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=8, max_length=128)
    role: str
    is_active: bool = True
    agent_id: str | None = None  # link to the agent record (agent accounts)
    # Registered email for password recovery (optional for older clients).
    email: str | None = Field(default=None, max_length=254, pattern=EMAIL_PATTERN)

    @field_validator("username", "full_name", mode="before")
    @classmethod
    def strip(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    _email = field_validator("email", mode="before")(_clean_email)


class UserUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    role: str | None = None
    is_active: bool | None = None
    agent_id: str | None = None
    email: str | None = Field(default=None, max_length=254, pattern=EMAIL_PATTERN)

    _email = field_validator("email", mode="before")(_clean_email)


class PasswordReset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    password: str = Field(min_length=8, max_length=128)


class UserResponse(BaseModel):
    id: int
    username: str
    full_name: str
    role: str
    is_active: bool
    branch_id: int | None = None
    last_login_at: datetime | None = None
    agent_id: str | None = None
    agent_name: str | None = None
    email: str | None = None
    photo_version: int | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
