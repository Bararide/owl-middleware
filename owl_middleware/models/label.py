from pydantic import BaseModel
from typing import Optional


class Label(BaseModel):
    key: str
    value: Optional[str] = None
