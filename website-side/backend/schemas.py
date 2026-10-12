from typing import Any, Optional
from pydantic import BaseModel


class UserPrompt(BaseModel):
    message: str
    workplace_lat: Optional[float] = None
    workplace_lng: Optional[float] = None
    workplace_name: Optional[str] = None
    # MIA's understanding of the previous search ("context" from the last reply),
    # so a follow-up like "how about 3 bedrooms?" refines it.
    context: Optional[dict[str, Any]] = None
