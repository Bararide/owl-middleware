import asyncio
from typing import List, Dict, Optional
from fastbot.core import Result, result_try, Ok, Err
from fastbot.logger.logger import Logger
from .client import ApiClient
from .streams.logs.logs import LogsStreamManager
import aiohttp


class LogsHandler:
    def __init__(self, client: ApiClient, base_url: str):
        self.client = client
        self.stream_manager = LogsStreamManager(base_url)
        self.active_streams: Dict[str, asyncio.Task] = {}
        self._current_stream_id: Optional[str] = None

    @result_try
    async def get_logs_stream(
        self,
        container_id: str,
        on_log: Optional[callable] = None,
    ) -> Result[str, Exception]:
        stream_id = await self.stream_manager.subscribe(container_id, on_log)
        self._current_stream_id = stream_id
        return Ok(stream_id)

    async def reset(self):
        Logger.info("Resetting LogsHandler for new connection")
        await self.stream_manager.reset()
        self.active_streams.clear()
        self._current_stream_id = None

    @result_try
    async def close_stream(self, stream_id: str) -> Result[bool, Exception]:
        if stream_id in self.active_streams:
            self.active_streams[stream_id].cancel()
            del self.active_streams[stream_id]

        await self.stream_manager.unsubscribe(stream_id)
        return Ok(True)
