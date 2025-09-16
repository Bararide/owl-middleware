from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import IntEnum


class LANG(IntEnum):
    EN = 0
    RU = 1


class User(BaseModel):
    id: int
    username: Optional[str] = None
    first_name: str = "Unknown"
    last_name: Optional[str] = None
    is_active: bool = True
    is_admin: bool = False
    registered_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    lang: LANG = LANG.EN
