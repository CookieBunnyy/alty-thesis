from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SessionState:
    token: str | None = None
    user: dict[str, Any] | None = None
    role: str = "Employee"
    permissions: list[str] = field(default_factory=list)
    branch_id: int | None = None


class SessionManager:
    def __init__(self) -> None:
        self.state = SessionState()

    def set_session(self, token: str, user: dict[str, Any] | None = None, role: str = "Employee", permissions: list[str] | None = None, branch_id: int | None = None) -> None:
        self.state.token = token
        self.state.user = user
        self.state.role = role
        self.state.permissions = permissions or []
        self.state.branch_id = branch_id

    def clear(self) -> None:
        self.state = SessionState()

    @property
    def is_authenticated(self) -> bool:
        return bool(self.state.token)

    @property
    def user_name(self) -> str:
        if not self.state.user:
            return "Guest"
        return str(self.state.user.get("full_name") or self.state.user.get("username") or "Guest")
