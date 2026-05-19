import asyncio
from typing import List, Dict, Optional
from fastbot.core import Result, result_try, Ok, Err
from fastbot.logger.logger import Logger
from .client import ApiClient
from .streams.recommendations.recommendations import (
    RecommendationStream,
    RecommendationStreamManager,
)


class RecommendationHandler:
    def __init__(self, client: ApiClient, base_url: str):
        self.client = client
        self.stream_manager = RecommendationStreamManager(base_url)
        self.active_streams: Dict[str, asyncio.Task] = {}
        self.current_user_id: Optional[str] = None
        self.current_container_id: Optional[str] = None
        self._reconnect_task: Optional[asyncio.Task] = None
        self._is_reconnecting = False
        self._current_stream_id: Optional[str] = None

    @result_try
    async def get_recommendations_stream(
        self,
        user_id: str,
        container_id: str,
        on_paths: Optional[callable] = None,
        on_complete: Optional[callable] = None,
    ) -> Result[str, Exception]:
        self.current_user_id = user_id
        self.current_container_id = container_id
        stream_id = await self.stream_manager.subscribe(
            user_id, container_id, on_paths, on_complete
        )
        self._current_stream_id = stream_id
        if self._reconnect_task is None or self._reconnect_task.done():
            self._reconnect_task = asyncio.create_task(
                self._keep_alive(user_id, container_id)
            )
        return Ok(stream_id)

    async def _keep_alive(self, user_id: str, container_id: str):
        last_alive = True
        while True:
            await asyncio.sleep(0.1)
            stream = self.stream_manager.stream
            if stream is None:
                last_alive = True
                continue
            is_alive = stream.is_alive()
            if not is_alive and last_alive:
                Logger.warning("SSE stream dead, forcing reconnect")
                await self.stream_manager._trigger_reconnect()
            last_alive = is_alive

    async def reset(self):
        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()
        await self.stream_manager.reset()
        self.active_streams.clear()
        self._current_stream_id = None
        self._reconnect_task = None
        self._is_reconnecting = False

    @result_try
    async def close_stream(self, stream_id: str) -> Result[bool, Exception]:
        self.active_streams.pop(stream_id, None)
        self.stream_manager.listeners.pop(stream_id, None)
        return Ok(True)

    @result_try
    async def get_recommendations_blocking(
        self, user_id: str, container_id: str, timeout: int = 5
    ) -> Result[List[str], Exception]:
        result_paths = []
        completed = asyncio.Event()
        stream_id = await self.stream_manager.subscribe(
            user_id,
            container_id,
            lambda c, u, p: result_paths.extend(p),
            lambda: completed.set(),
        )
        try:
            await asyncio.wait_for(completed.wait(), timeout=timeout)
            return Ok(result_paths)
        except asyncio.TimeoutError:
            return Err(Exception(f"Timeout after {timeout} seconds"))
        finally:
            self.stream_manager.listeners.pop(stream_id, None)
