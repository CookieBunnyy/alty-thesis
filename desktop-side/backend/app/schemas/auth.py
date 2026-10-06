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
