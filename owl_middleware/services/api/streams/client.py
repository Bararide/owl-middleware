import aiohttp
import asyncio
import json
from typing import Callable, Dict, Any, Optional, List
from fastbot.logger.logger import Logger


class SSEClient:
    def __init__(self, url: str, session: Optional[aiohttp.ClientSession] = None):
        self.url = url
        self._session_owner = session is None
        self.session = session or aiohttp.ClientSession()
        self.event_handlers: Dict[str, List[Callable]] = {
            "message": [],
            "end": [],
            "error": [],
        }
        self.running = False
        self.task: Optional[asyncio.Task] = None
        self.should_reconnect = True

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

    async def _connect_and_listen(self, headers: Optional[Dict] = None):
        while self.should_reconnect:
            try:
                timeout = aiohttp.ClientTimeout(total=10, sock_read=5, sock_connect=3)
                connector = aiohttp.TCPConnector(ttl_dns_cache=300, force_close=True)
                async with aiohttp.ClientSession(
                    connector=connector, timeout=timeout
                ) as sess:
                    async with sess.get(self.url, headers=headers) as response:
                        if response.status != 200:
                            await asyncio.sleep(0.1)
                            continue

                        self.running = True
                        buffer = ""

                        async for chunk in response.content:
                            if not self.running or not self.should_reconnect:
                                break

                            buffer += chunk.decode("utf-8", errors="replace")
                            while "\n\n" in buffer:
                                message, buffer = buffer.split("\n\n", 1)
                                if not message.strip() or message.strip().startswith(
                                    ":"
                                ):
                                    continue

                                event = "message"
                                data_str = None
                                for line in message.split("\n"):
                                    line = line.strip()
                                    if line.startswith("event:"):
                                        event = line[6:].strip()
                                    elif line.startswith("data:"):
                                        data_str = line[5:].strip()

                                if data_str:
                                    try:
                                        data = json.loads(data_str)
                                        self._emit(event, data)
                                    except json.JSONDecodeError:
                                        self._emit(event, data_str)

                                    if event == "end":
                                        self._emit("end")
                                        self.should_reconnect = False
                                        self.running = False
                                        return

                        self.running = False
                        if self.should_reconnect:
                            await asyncio.sleep(0.1)

            except (aiohttp.ClientError, ConnectionError, OSError) as e:
                self.running = False
                self._emit("error", e)
                if self.should_reconnect:
                    await asyncio.sleep(0.1)
            except Exception as e:
                self.running = False
                self._emit("error", e)
                if self.should_reconnect:
                    await asyncio.sleep(0.1)

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
        if self._session_owner:
            await self.session.close()
