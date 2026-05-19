from typing import Optional, Callable, Dict, Any, List
import uuid
import asyncio
from fastbot.logger.logger import Logger

from ..client import SSEClient


class RecommendationStream:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.client: Optional[SSEClient] = None
        self._paths_handlers: List[Callable] = []
        self._complete_handlers: List[Callable] = []
        self._error_handlers: List[Callable] = []
        self._is_alive = True
        self._reconnect_callback: Optional[Callable] = None
        self._user_id: Optional[str] = None
        self._container_id: Optional[str] = None
        self._headers: Optional[Dict] = None

    def is_alive(self) -> bool:
        return self._is_alive and self.client is not None and self.client.running

    def on_paths(self, handler: Callable[[str, str, List[str]], None]):
        self._paths_handlers.append(handler)
        return self

    def on_complete(self, handler: Callable[[], None]):
        self._complete_handlers.append(handler)
        return self

    def on_error(self, handler: Callable[[Exception], None]):
        self._error_handlers.append(handler)
        return self

    def on_reconnect(self, callback: Callable):
        self._reconnect_callback = callback

    def _handle_data(self, data: Dict[str, Any]):
        try:
            container_id = data.get("container_id", "")
            user_id = data.get("user_id", "")
            paths = data.get("paths", [])
            if paths:
                for handler in self._paths_handlers:
                    try:
                        handler(container_id, user_id, paths)
                    except Exception as e:
                        Logger.error(f"Error in paths handler: {e}")
        except Exception as e:
            Logger.error(f"Error processing SSE data: {e}")

    def _handle_end(self):
        self._is_alive = False
        for handler in self._complete_handlers:
            try:
                handler()
            except Exception as e:
                Logger.error(f"Error in complete handler: {e}")

    def _handle_error(self, error: Exception):
        self._is_alive = False
        for handler in self._error_handlers:
            try:
                handler(error)
            except:
                pass
        if self._reconnect_callback:
            asyncio.create_task(self._reconnect_callback())

    async def connect(
        self, user_id: str, container_id: str, headers: Optional[Dict] = None
    ):
        self._user_id = user_id
        self._container_id = container_id
        self._headers = headers or {}
        url = f"{self.base_url}/recommendations/stream?user_id={user_id}&container_id={container_id}"
        if self.client:
            await self.client.stop()
        self.client = SSEClient(url)
        self.client.on_data(self._handle_data)
        self.client.on_end(self._handle_end)
        self.client.on_error(self._handle_error)
        await self.client.start(self._headers)
        self._is_alive = True
        return self

    async def close(self):
        self._is_alive = False
        if self.client:
            await self.client.close()
            self.client = None

    async def force_reconnect(self):
        await self.close()
        await asyncio.sleep(0.05)
        await self.connect(self._user_id, self._container_id, self._headers)


class RecommendationStreamManager:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.stream: Optional[RecommendationStream] = None
        self.listeners: Dict[str, Dict[str, Callable]] = {}
        self.user_container_key: Optional[str] = None
        self._current_user_id: Optional[str] = None
        self._current_container_id: Optional[str] = None
        self._reconnect_lock = asyncio.Lock()

    async def subscribe(
        self, user_id: str, container_id: str, on_paths: Callable, on_complete: Callable
    ):
        key = f"{user_id}_{container_id}"
        self._current_user_id = user_id
        self._current_container_id = container_id

        if self.user_container_key != key:
            if self.stream:
                await self.stream.close()
            self.stream = RecommendationStream(self.base_url)
            self.stream.on_reconnect(lambda: self._trigger_reconnect())
            await self.stream.connect(user_id, container_id)
            self.user_container_key = key
            self.stream.on_paths(self._broadcast_paths)
            self.stream.on_complete(self._broadcast_complete)
            self.stream.on_error(self._broadcast_error)

        listener_id = str(uuid.uuid4())
        self.listeners[listener_id] = {"on_paths": on_paths, "on_complete": on_complete}
        Logger.info(f"Subscribed listener {listener_id} for {key}")
        return listener_id

    async def _trigger_reconnect(self):
        async with self._reconnect_lock:
            if self._current_user_id and self._current_container_id and self.stream:
                Logger.warning("Triggering immediate SSE reconnect")
                await self.stream.force_reconnect()
                self.stream.on_paths(self._broadcast_paths)
                self.stream.on_complete(self._broadcast_complete)
                self.stream.on_error(self._broadcast_error)
                self._is_alive = True

    async def reset(self):
        if self.stream:
            await self.stream.close()
        self.stream = None
        self.listeners.clear()
        self.user_container_key = None
        self._current_user_id = None
        self._current_container_id = None

    async def unsubscribe(self, listener_id: str):
        self.listeners.pop(listener_id, None)

    def _broadcast_paths(self, container_id: str, user_id: str, paths: List[str]):
        for lid, listener in list(self.listeners.items()):
            try:
                listener.get("on_paths")(container_id, user_id, paths)
            except:
                pass

    def _broadcast_complete(self):
        for lid, listener in list(self.listeners.items()):
            try:
                listener.get("on_complete")()
            except:
                pass

    def _broadcast_error(self, error: Exception):
        pass
