from pydantic import BaseModel
from typing import List, Optional

from .label import Label
from .tariff import Tariff


class Container(BaseModel):
    id: str
    user_id: str
    tariff: Tariff
    env_label: Label
    type_label: Label
    privileged: bool
    commands: Optional[List[str]] = []
