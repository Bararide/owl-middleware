from typing import Optional, Callable, Dict, Any, List
import uuid
import asyncio
from fastbot.logger.logger import Logger

from .client import SSEClient


class RecommendationStream:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.client: Optional[SSEClient] = None
        self._paths_handlers: List[Callable] = []
        self._complete_handlers: List[Callable] = []
        self._is_alive = True

    def is_alive(self) -> bool:
        return self._is_alive and self.client is not None and self.client.running

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
        self._is_alive = False

        for handler in self._complete_handlers:
            try:
                handler()
            except Exception as e:
                Logger.error(f"Error in complete handler: {e}")

    def _handle_error(self, error: Exception):
        Logger.error(f"SSE error: {error}")
        self._is_alive = False

    async def connect(
        self, user_id: str, container_id: str, headers: Optional[Dict] = None
    ):
        url = f"{self.base_url}/recommendations/stream?user_id={user_id}&container_id={container_id}"

        if headers is None:
            headers = {}

        self.client = SSEClient(url)

        Logger.info("CONNECT TO STREAM")

        self.client.on_data(self._handle_data)
        self.client.on_end(self._handle_end)
        self.client.on_error(self._handle_error)

        await self.client.start(headers)
        self._is_alive = True

        return self

    async def close(self):
        self._is_alive = False
        if self.client:
            await self.client.close()
            self.client = None


class RecommendationStreamManager:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.stream: Optional[RecommendationStream] = None
        self.listeners: Dict[str, Dict[str, Callable]] = {}
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

        Logger.info(f"Subscribed listener {listener_id} for {key}")
        return listener_id

    async def reset(self):
        """Полный сброс менеджера"""
        if self.stream:
            await self.stream.close()
            self.stream = None
        self.listeners.clear()
        self.user_container_key = None
        Logger.info("RecommendationStreamManager reset completed")

    async def unsubscribe(self, listener_id: str):
        if listener_id in self.listeners:
            del self.listeners[listener_id]
            Logger.info(f"Unsubscribed listener {listener_id}")

    def _broadcast_paths(self, container_id: str, user_id: str, paths: List[str]):
        to_remove = []
        for listener_id, listener in self.listeners.items():
            try:
                if "on_paths" in listener:
                    listener["on_paths"](container_id, user_id, paths)
            except Exception as e:
                Logger.error(f"Error broadcasting paths to {listener_id}: {e}")
                to_remove.append(listener_id)

        for listener_id in to_remove:
            del self.listeners[listener_id]

    def _broadcast_complete(self):
        to_remove = []
        for listener_id, listener in self.listeners.items():
            try:
                if "on_complete" in listener:
                    listener["on_complete"]()
            except Exception as e:
                Logger.error(f"Error broadcasting complete to {listener_id}: {e}")
                to_remove.append(listener_id)

        for listener_id in to_remove:
            del self.listeners[listener_id]

        if not self.listeners and self.stream:
            asyncio.create_task(self._cleanup_stream())

    async def _cleanup_stream(self):
        await asyncio.sleep(5)
        if not self.listeners and self.stream:
            await self.stream.close()
            self.stream = None
            self.user_container_key = None
