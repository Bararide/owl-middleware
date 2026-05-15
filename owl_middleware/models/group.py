from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class Group(BaseModel):
    id: str
    container_id: str
    description: Optional[str] = None
    color: Optional[str] = "#ff9800"
    created_at: Optional[datetime] = None
