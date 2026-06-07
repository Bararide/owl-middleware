from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from abc import ABC


class BaseGroup(BaseModel, ABC):
    id: str
    description: Optional[str] = None
    created_at: Optional[datetime] = None
    color: str = "#ff9800"
