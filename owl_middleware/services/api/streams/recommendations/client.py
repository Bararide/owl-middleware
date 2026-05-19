import aiohttp
import asyncio
import json
from typing import Callable, Dict, Any, Optional, List
from fastbot.core import Result, Ok, Err
from fastbot.logger.logger import Logger


class SSEClient:
    """Клиент для обработки Server-Sent Events с автоматическим переподключением"""

    def __init__(self, url: str, session: Optional[aiohttp.ClientSession] = None):
        self.url = url
        self.session = session or aiohttp.ClientSession()
        self.event_handlers: Dict[str, List[Callable]] = {
            "message": [],
            "end": [],
            "error": [],
            "reconnected": [],
        }
        self.running = False
        self.task: Optional[asyncio.Task] = None
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        self.reconnect_delay = 1

    def on(self, event: str, handler: Callable):
        if event not in self.event_handlers:
            self.event_handlers[event] = []
        self.event_handlers[event].append(handler)
        return self

    def on_data(self, handler: Callable[[Dict[str, Any]], None]):
        return self.on("message", handler)

    def on_end(self, handler: Callable[[], None]):
        return self.on("end", handler)

    def on_error(self, handler: Callable[[Exception], None]):
        return self.on("error", handler)

    def on_reconnected(self, handler: Callable[[], None]):
        return self.on("reconnected", handler)

    def _emit(self, event: str, data: Any = None):
        if event in self.event_handlers:
            for handler in self.event_handlers[event]:
                try:
                    if data is not None:
                        handler(data)
                    else:
                        handler()
                except Exception as e:
                    Logger.error(f"Error in SSE handler for {event}: {e}")

    async def connect(self, headers: Optional[Dict] = None) -> Result[bool, Exception]:
        while self.reconnect_attempts < self.max_reconnect_attempts:
            try:
                async with self.session.get(self.url, headers=headers) as response:
                    if response.status != 200:
                        error_msg = f"Failed to connect: {response.status}"
                        self._emit("error", Exception(error_msg))
                        raise Exception(error_msg)

                    if self.reconnect_attempts > 0:
                        Logger.info(
                            f"SSE reconnected after {self.reconnect_attempts} attempts"
                        )
                        self._emit("reconnected")
                        self.reconnect_attempts = 0
                    else:
                        Logger.info(f"SSE connected to {self.url}")

                    self.running = True

                    async for line in response.content:
                        if not self.running:
                            break

                        line = line.decode("utf-8").rstrip("\n")

                        if line.startswith("data:"):
                            data_str = line[5:].lstrip()
                            try:
                                data = json.loads(data_str)
                                self._emit("message", data)
                            except json.JSONDecodeError:
                                self._emit("message", data_str)

                        elif line.startswith("event:"):
                            event_name = line[6:].lstrip()
                            if event_name == "end":
                                self._emit("end")
                                return Ok(True)

                        elif line.startswith(":"):
                            continue

                    return Ok(True)

            except aiohttp.ClientError as e:
                Logger.error(f"SSE connection error: {e}")
                self._emit("error", e)

                if self.reconnect_attempts >= self.max_reconnect_attempts - 1:
                    Logger.error("Max reconnect attempts reached")
                    return Err(e)

                self.reconnect_attempts += 1
                delay = self.reconnect_delay * (2 ** (self.reconnect_attempts - 1))
                Logger.info(
                    f"Reconnecting in {delay}s (attempt {self.reconnect_attempts}/{self.max_reconnect_attempts})"
                )
                await asyncio.sleep(delay)

            except Exception as e:
                Logger.error(f"SSE error: {e}")
                self._emit("error", e)
                return Err(e)
            finally:
                self.running = False

        return Err(Exception("Max reconnect attempts exceeded"))

    async def start(self, headers: Optional[Dict] = None):
        self.task = asyncio.create_task(self.connect(headers))

    async def stop(self):
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass

    async def close(self):
        await self.stop()
        await self.session.close()


class SSEConnectionPool:
    def __init__(self):
        self.connections: Dict[str, SSEClient] = {}
        self.sessions: Dict[str, aiohttp.ClientSession] = {}

    def create_client(self, url: str, connection_id: str) -> SSEClient:
        if connection_id not in self.sessions:
            self.sessions[connection_id] = aiohttp.ClientSession()

        client = SSEClient(url, self.sessions[connection_id])
        self.connections[connection_id] = client
        return client

    async def close_client(self, connection_id: str):
        if connection_id in self.connections:
            await self.connections[connection_id].close()
            del self.connections[connection_id]

        if connection_id in self.sessions:
            await self.sessions[connection_id].close()
            del self.sessions[connection_id]

    async def close_all(self):
        for client in self.connections.values():
            await client.close()

        for session in self.sessions.values():
            await session.close()

        self.connections.clear()
        self.sessions.clear()
