from pydantic import BaseModel, Field
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

    @classmethod
    def from_dict(cls, data: dict) -> "Container":
        return cls(
            id=data.get("container_id") or data.get("id"),
            user_id=data.get("user_id"),
            tariff=Tariff(
                memory_limit=data.get("memory_limit", 0),
                storage_quota=data.get("storage_quota", 0),
                file_limit=data.get("file_limit", 0),
            ),
            env_label=Label(
                key=data.get("env_label", {}).get("key", ""),
                value=data.get("env_label", {}).get("value", ""),
            ),
            type_label=Label(
                key=data.get("type_label", {}).get("key", ""),
                value=data.get("type_label", {}).get("value", ""),
            ),
            privileged=data.get("privileged", False),
            commands=data.get("commands", []),
        )
