from typing import Optional, Callable, Dict, Any, List
import uuid
from fastbot.logger.logger import Logger

from .client import SSEClient


class RecommendationStream:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.client: Optional[SSEClient] = None
        self._paths_handlers: List[Callable] = []
        self._complete_handlers: List[Callable] = []

    def on_paths(self, handler: Callable[[str, str, List[str]], None]):
        self._paths_handlers.append(handler)
        return self

    def on_complete(self, handler: Callable[[], None]):
        self._complete_handlers.append(handler)
        return self

    def _handle_data(self, data: Dict[str, Any]):
        try:
            container_id = data.get("container_id", "")
            user_id = data.get("user_id", "")
            paths = data.get("paths", [])

            Logger.info(
                f"Received {len(paths)} paths for container {container_id}, user_id {user_id}"
            )

            if paths:
                for handler in self._paths_handlers:
                    try:
                        handler(container_id, user_id, paths)
                    except Exception as e:
                        Logger.error(f"Error in paths handler: {e}")

        except Exception as e:
            Logger.error(f"Error processing SSE data: {e}")

    def _handle_end(self):
        Logger.info("Recommendation stream completed")

        for handler in self._complete_handlers:
            try:
                handler()
            except Exception as e:
                Logger.error(f"Error in complete handler: {e}")

    async def connect(
        self, user_id: str, container_id: str, headers: Optional[Dict] = None
    ):
        url = f"{self.base_url}/recommendations/stream"

        if headers is None:
            headers = {}

        params = f"?user_id={user_id}&container_id={container_id}"
        url_with_params = url + params

        self.client = SSEClient(url_with_params)

        Logger.info("CONNECT TO STREAM")

        self.client.on_data(self._handle_data)
        self.client.on_end(self._handle_end)

        await self.client.start(headers)

        return self

    async def close(self):
        if self.client:
            await self.client.close()


class RecommendationStreamManager:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.stream: Optional[RecommendationStream] = None
        self.listeners: Dict[str, List[Callable]] = {}
        self.user_container_key: Optional[str] = None

    async def subscribe(
        self, user_id: str, container_id: str, on_paths: Callable, on_complete: Callable
    ):
        key = f"{user_id}_{container_id}"

        if self.user_container_key != key:
            if self.stream:
                await self.stream.close()

            self.stream = RecommendationStream(self.base_url)
            await self.stream.connect(user_id, container_id)
            self.user_container_key = key

            self.stream.on_paths(self._broadcast_paths)
            self.stream.on_complete(self._broadcast_complete)

        listener_id = str(uuid.uuid4())
        self.listeners[listener_id] = {"on_paths": on_paths, "on_complete": on_complete}
        return listener_id

    def _broadcast_paths(self, container_id: str, user_id: str, paths: List[str]):
        """Шлем всем подписанным клиентам"""
        for listener in self.listeners.values():
            try:
                listener["on_paths"](container_id, user_id, paths)
            except:
                pass

    def _broadcast_complete(self):
        """Шлем всем завершение"""
        for listener in self.listeners.values():
            try:
                listener["on_complete"]()
            except:
                pass
        self.listeners.clear()
