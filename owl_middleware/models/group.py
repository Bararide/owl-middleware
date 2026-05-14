from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class Group(BaseModel):
    id: str
    container_id: str
    description: Optional[str] = None
    created_at: Optional[datetime] = None
