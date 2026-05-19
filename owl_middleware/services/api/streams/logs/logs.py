from typing import Optional, Callable, Dict, Any, List
import uuid
import asyncio
from fastbot.logger.logger import Logger

from ..client import SSEClient


class LogsStream:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.client: Optional[SSEClient] = None
        self._logs_handlers: List[Callable] = []
        self._is_alive = True

    def is_alive(self) -> bool:
        return self._is_alive and self.client is not None and self.client.running

    def on_log(self, handler: Callable[[str], None]):
        self._logs_handlers.append(handler)
        return self

    def _handle_data(self, data: Dict[str, Any]):
        try:
            log_message = data.get("message", "")
            if isinstance(data, str):
                log_message = data
            elif data.get("log"):
                log_message = data.get("log")

            Logger.info(f"Received log: {log_message}")

            if log_message:
                for handler in self._logs_handlers:
                    try:
                        handler(log_message)
                    except Exception as e:
                        Logger.error(f"Error in log handler: {e}")

        except Exception as e:
            Logger.error(f"Error processing SSE data: {e}")

    def _handle_end(self):
        Logger.info("Logs stream completed")
        self._is_alive = False

    def _handle_error(self, error: Exception):
        Logger.error(f"SSE error: {error}")
        self._is_alive = False

    async def connect(self, container_id: str, headers: Optional[Dict] = None):
        url = f"{self.base_url}/logs/stream?container_id={container_id}"

        if headers is None:
            headers = {}

        self.client = SSEClient(url)

        Logger.info("CONNECT TO LOGS STREAM")

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


class LogsStreamManager:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.stream: Optional[LogsStream] = None
        self.listeners: Dict[str, List[Callable]] = {}
        self.container_key: Optional[str] = None

    async def subscribe(self, container_id: str, on_log: Callable):
        key = container_id

        if self.container_key != key:
            if self.stream:
                await self.stream.close()

            self.stream = LogsStream(self.base_url)
            await self.stream.connect(container_id)
            self.container_key = key

            self.stream.on_log(self._broadcast_log)

        listener_id = str(uuid.uuid4())
        self.listeners[listener_id] = on_log

        Logger.info(f"Subscribed log listener {listener_id} for container {key}")
        return listener_id

    async def reset(self):
        if self.stream:
            await self.stream.close()
            self.stream = None
        self.listeners.clear()
        self.container_key = None
        Logger.info("LogsStreamManager reset completed")

    async def unsubscribe(self, listener_id: str):
        if listener_id in self.listeners:
            del self.listeners[listener_id]
            Logger.info(f"Unsubscribed log listener {listener_id}")

    def _broadcast_log(self, log_message: str):
        to_remove = []
        for listener_id, handler in self.listeners.items():
            try:
                handler(log_message)
            except Exception as e:
                Logger.error(f"Error broadcasting log to {listener_id}: {e}")
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
            self.container_key = None
