import aiohttp
import asyncio
import json
from typing import Callable, Dict, Any, Optional, List
from fastbot.core import Result, Ok, Err
from fastbot.logger.logger import Logger


class SSEClient:
    def __init__(self, url: str, session: Optional[aiohttp.ClientSession] = None):
        self.url = url
        self.session = session or aiohttp.ClientSession()
        self.event_handlers: Dict[str, List[Callable]] = {
            "message": [],
            "end": [],
            "error": [],
        }
        self.running = False
        self.task: Optional[asyncio.Task] = None
        self.should_reconnect = True
        self.reconnect_delay = 1
        self.max_reconnect_delay = 5
        self.last_heartbeat = asyncio.get_event_loop().time()

    def on_data(self, handler: Callable[[Dict[str, Any]], None]):
        self.event_handlers["message"].append(handler)
        return self

    def on_end(self, handler: Callable[[], None]):
        self.event_handlers["end"].append(handler)
        return self

    def on_error(self, handler: Callable[[Exception], None]):
        self.event_handlers["error"].append(handler)
        return self

    def _emit(self, event: str, data: Any = None):
        for handler in self.event_handlers.get(event, []):
            try:
                if data is not None:
                    handler(data)
                else:
                    handler()
            except Exception as e:
                Logger.error(f"Error in SSE handler for {event}: {e}")

    async def _heartbeat_check(self):
        while self.running and self.should_reconnect:
            await asyncio.sleep(60)
            if asyncio.get_event_loop().time() - self.last_heartbeat > 90:
                Logger.warning("No heartbeat received, reconnecting...")
                self.running = False
                break

    async def _connect_and_listen(self, headers: Optional[Dict] = None):
        delay = self.reconnect_delay

        while self.should_reconnect:
            try:
                timeout = aiohttp.ClientTimeout(total=None, sock_read=10)
                async with self.session.get(
                    self.url, headers=headers, timeout=timeout
                ) as response:
                    if response.status != 200:
                        error_msg = f"Failed to connect: {response.status}"
                        Logger.error(error_msg)
                        self._emit("error", Exception(error_msg))

                        if not self.should_reconnect:
                            break

                        await asyncio.sleep(delay)
                        delay = min(delay * 2, self.max_reconnect_delay)
                        continue

                    Logger.info(f"SSE connected to {self.url}")
                    if delay > self.reconnect_delay:
                        Logger.info(f"SSE reconnected after {delay}s delay")

                    delay = self.reconnect_delay
                    self.running = True

                    heartbeat_task = asyncio.create_task(self._heartbeat_check())

                    async for line in response.content:
                        if not self.running or not self.should_reconnect:
                            break

                        line = line.decode("utf-8").rstrip("\n")

                        if line.startswith(": heartbeat"):
                            self.last_heartbeat = asyncio.get_event_loop().time()
                            continue

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
                                self.should_reconnect = False
                                break

                    heartbeat_task.cancel()
                    self.running = False

            except asyncio.CancelledError:
                break
            except aiohttp.ClientError as e:
                Logger.error(f"SSE connection error: {e}")
                self._emit("error", e)

                if not self.should_reconnect:
                    break

                Logger.info(f"Reconnecting in {delay}s...")
                await asyncio.sleep(delay)
                delay = min(delay * 2, self.max_reconnect_delay)

            except Exception as e:
                Logger.error(f"SSE error: {e}")
                self._emit("error", e)
                break

    async def start(self, headers: Optional[Dict] = None):
        self.should_reconnect = True
        self.task = asyncio.create_task(self._connect_and_listen(headers))

    async def stop(self):
        self.should_reconnect = False
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
