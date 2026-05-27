from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class Container2Group(BaseModel):
    group_id: str
    container_id: str
