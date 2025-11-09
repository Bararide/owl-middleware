from typing import Optional, Any, Dict, List
from pydantic import BaseModel
from datetime import datetime


class StateConfig(BaseModel):
    user_id: str
    work_container_id: Optional[str] = None
    last_activity: datetime = datetime.now()
    metadata: Dict[str, Any] = {}


class State:
    def __init__(self):
        self._state_configs: Dict[str, StateConfig] = {}

    def get_state(self, user_id: str) -> StateConfig:
        if user_id not in self._state_configs:
            self._state_configs[user_id] = StateConfig(user_id=user_id)
        return self._state_configs[user_id]

    def set_work_container(self, user_id: str, container_id: str) -> None:
        state = self.get_state(user_id)
        state.work_container_id = container_id
        state.last_activity = datetime.now()

    def get_work_container(self, user_id: str) -> Optional[str]:
        state = self.get_state(user_id)
        return state.work_container_id

    def clear_work_container(self, user_id: str) -> None:
        state = self.get_state(user_id)
        state.work_container_id = None
        state.last_activity = datetime.now()

    def update_metadata(self, user_id: str, key: str, value: Any) -> None:
        state = self.get_state(user_id)
        state.metadata[key] = value
        state.last_activity = datetime.now()

    def get_metadata(self, user_id: str, key: str, default: Any = None) -> Any:
        state = self.get_state(user_id)
        return state.metadata.get(key, default)

    def cleanup_old_states(self, hours: int = 24) -> None:
        cutoff_time = datetime.now().timestamp() - (hours * 3600)
        to_remove = []

        for user_id, state in self._state_configs.items():
            if state.last_activity.timestamp() < cutoff_time:
                to_remove.append(user_id)

        for user_id in to_remove:
            del self._state_configs[user_id]
