from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class UserRegister(BaseModel):
    model_config = ConfigDict(extra='forbid')

    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str = Field(..., min_length=1, max_length=200)

    @field_validator('username', 'full_name', mode='before')
    @classmethod
    def strip_required_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class PasswordChange(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)


EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class PasswordResetRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=254, pattern=EMAIL_PATTERN)
    captcha_token: str | None = Field(default=None, max_length=2048)

    @field_validator("email", mode="before")
    @classmethod
    def strip_email(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class PasswordResetConfirm(BaseModel):
    token: str = Field(..., min_length=1, max_length=200)
    new_password: str = Field(..., min_length=8, max_length=128)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class CurrentUser(BaseModel):
    id: int
    username: str
    full_name: str
    role: str
    permissions: list[str]
    branch_id: int | None = None
    is_active: bool
    last_login_at: datetime | None = None
    agent_id: str | None = None
    photo_version: int | None = None
    email: str | None = None
