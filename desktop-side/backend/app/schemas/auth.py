from pydantic import BaseModel, ConfigDict, Field, field_validator


class UserRegister(BaseModel):
    model_config = ConfigDict(extra='forbid')

    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=6)
    full_name: str = Field(..., min_length=1, max_length=200)

    @field_validator('username', 'full_name', mode='before')
    @classmethod
    def strip_required_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
