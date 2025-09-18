from pydantic import BaseModel
from typing import Optional

from models import User


class File(BaseModel):
    id: int
    name: str
    user_id: int
    user: Optional["User"] = None
