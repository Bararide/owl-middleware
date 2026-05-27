from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from .roles.group_role import GroupRole


class User2Group(BaseModel):
    user_id: str
    container_id: str
    role: GroupRole = GroupRole.member
