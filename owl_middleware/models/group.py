from typing import Optional

from .base_group import BaseGroup


class Group(BaseGroup):
    container_id: str
    color: Optional[str] = "#ff9800"
