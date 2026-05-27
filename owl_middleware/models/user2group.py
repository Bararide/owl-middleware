from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class User2Group(BaseModel):
    user_id: str
    container_id: str
