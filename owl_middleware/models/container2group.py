from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from .permissions.container_permission import ContainerPermission


class Container2Group(BaseModel):
    group_id: str
    container_id: str
    permission: ContainerPermission = ContainerPermission.read_write
    granted_at: Optional[str] = None
