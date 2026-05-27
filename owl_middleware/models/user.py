from pydantic import BaseModel, Field, EmailStr
from typing import Optional
from datetime import datetime
from enum import IntEnum

from .roles.user_role import UserRole


class LANG(IntEnum):
    EN = 0
    RU = 1


class User(BaseModel):
    id: int
    tg_id: Optional[int] = None
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    first_name: str = "Unknown"
    last_name: Optional[str] = None
    is_active: bool = True
    role: UserRole = UserRole.user
    registered_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    lang: LANG = LANG.EN
    auth_method: str = "telegram"


class UserCreate(BaseModel):
    tg_id: Optional[int] = None
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    first_name: str = "Unknown"
    last_name: Optional[str] = None
    password: Optional[str] = None
    auth_method: str = "telegram"
