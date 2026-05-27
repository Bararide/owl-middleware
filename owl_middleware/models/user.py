from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List
from datetime import datetime
from enum import IntEnum, Enum

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
    password_hash: Optional[str] = None
    permissions: List[str] = Field(default_factory=list)
    created_by: Optional[int] = None
    promoted_at: Optional[str] = None
    promoted_by: Optional[int] = None


class UserCreate(BaseModel):
    tg_id: Optional[int] = None
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    first_name: str = "Unknown"
    last_name: Optional[str] = None
    password: Optional[str] = None
    auth_method: str = "telegram"
    role: UserRole = UserRole.user
    permissions: List[str] = Field(default_factory=list)
