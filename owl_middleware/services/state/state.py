from typing import Optional, Any, Dict, List
from pydantic import BaseModel
from datetime import datetime
import uuid


class SearchResult(BaseModel):
    query: str
    paths: List[str]
    timestamp: datetime = datetime.now()


class StateConfig(BaseModel):
    user_id: str
    work_container_id: Optional[str] = None
    search_results: Dict[str, SearchResult] = {}
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

    def add_search_results(self, user_id: str, query: str, paths: List[str]) -> str:
        state = self.get_state(user_id)
        search_id = str(uuid.uuid4())[:8]

        state.search_results[search_id] = SearchResult(
            query=query, paths=paths, timestamp=datetime.now()
        )
        state.last_activity = datetime.now()

        return search_id

    def get_search_result(self, user_id: str, search_id: str) -> Optional[SearchResult]:
        state = self.get_state(user_id)
        return state.search_results.get(search_id)

    def get_file_path(
        self, user_id: str, search_id: str, file_index: int
    ) -> Optional[str]:
        result = self.get_search_result(user_id, search_id)
        if result and 0 <= file_index < len(result.paths):
            return result.paths[file_index]
        return None

    def set_metadata(self, user_id: str, key: str, value: Any) -> None:
        state = self.get_state(user_id)
        state.metadata[key] = value
        state.last_activity = datetime.now()

    def get_metadata(self, user_id: str, key: str) -> Any:
        state = self.get_state(user_id)
        return state.metadata.get(key)

    def delete_metadata(self, user_id: str, key: str) -> None:
        state = self.get_state(user_id)
        if key in state.metadata:
            del state.metadata[key]
            state.last_activity = datetime.now()

    def cleanup_old_states(self, hours: int = 24) -> None:
        self._state_configs.clear()
