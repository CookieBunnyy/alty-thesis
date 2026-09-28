from typing import Any, List, Optional
from pydantic import BaseModel


class UserPrompt(BaseModel):
    message: str
    workplace_lat: Optional[float] = None
    workplace_lng: Optional[float] = None
    workplace_name: Optional[str] = None