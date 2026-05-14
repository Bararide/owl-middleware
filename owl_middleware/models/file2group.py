from pydantic import BaseModel
from typing import Optional


class File2Group(BaseModel):
    file_id: str
    group_id: str
