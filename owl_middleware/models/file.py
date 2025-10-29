from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from models import User


class File(BaseModel):
    id: str
    container_id: str
    name: str
    size: Optional[int] = None
    mime_type: Optional[str] = None
    created_at: Optional[datetime] = None
