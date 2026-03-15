import aiohttp
import asyncio
import json
from typing import Callable, Dict, Any, Optional, List
from fastbot.core import Result, Ok, Err
from fastbot.logger.logger import Logger


class SSEClient:
    """Клиент для обработки Server-Sent Events"""

    def __init__(self, url: str, session: Optional[aiohttp.ClientSession] = None):
        self.url = url
        self.session = session or aiohttp.ClientSession()
        self.event_handlers: Dict[str, List[Callable]] = {
            "message": [],  # для data: события
            "end": [],  # для event: end
            "error": [],  # для ошибок
        }
        self.running = False
        self.task: Optional[asyncio.Task] = None

    def on(self, event: str, handler: Callable):
        """Регистрация обработчика для события"""
        if event not in self.event_handlers:
            self.event_handlers[event] = []
        self.event_handlers[event].append(handler)
        return self

    def on_data(self, handler: Callable[[Dict[str, Any]], None]):
        """Регистрация обработчика для data: событий"""
        return self.on("message", handler)

    def on_end(self, handler: Callable[[], None]):
        """Регистрация обработчика для event: end"""
        return self.on("end", handler)

    def _emit(self, event: str, data: Any = None):
        """Вызов обработчиков события"""
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
        try:
            async with self.session.get(self.url, headers=headers) as response:
                if response.status != 200:
                    return Err(Exception(f"Failed to connect: {response.status}"))

                Logger.info(f"SSE connected to {self.url}")
                Logger.info(f"CONTENT: {response.content}")

                self.running = True

                async for line in response.content:
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
                            break

                    elif line == "":
                        continue

                return Ok(True)

        except aiohttp.ClientError as e:
            self._emit("error", e)
            return Err(e)
        except Exception as e:
            self._emit("error", e)
            return Err(e)
        finally:
            self.running = False

    async def start(self, headers: Optional[Dict] = None):
        """Запуск SSE клиента в фоновом режиме"""
        self.task = asyncio.create_task(self.connect(headers))

    async def stop(self):
        """Остановка SSE клиента"""
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass

    async def close(self):
        """Закрытие клиента"""
        await self.stop()
        await self.session.close()


class SSEConnectionPool:
    """Пул SSE соединений для управления несколькими потоками"""

    def __init__(self):
        self.connections: Dict[str, SSEClient] = {}
        self.sessions: Dict[str, aiohttp.ClientSession] = {}

    def create_client(self, url: str, connection_id: str) -> SSEClient:
        """Создание нового SSE клиента"""
        if connection_id not in self.sessions:
            self.sessions[connection_id] = aiohttp.ClientSession()

        client = SSEClient(url, self.sessions[connection_id])
        self.connections[connection_id] = client
        return client

    async def close_client(self, connection_id: str):
        """Закрытие SSE клиента"""
        if connection_id in self.connections:
            await self.connections[connection_id].close()
            del self.connections[connection_id]

        if connection_id in self.sessions:
            await self.sessions[connection_id].close()
            del self.sessions[connection_id]

    async def close_all(self):
        """Закрытие всех соединений"""
        for client in self.connections.values():
            await client.close()

        for session in self.sessions.values():
            await session.close()

        self.connections.clear()
        self.sessions.clear()
