import asyncio
from typing import List, Dict, Optional
from fastbot.core import Result, result_try, Ok, Err
from fastbot.logger.logger import Logger
from .client import ApiClient
from .streams.recommendations.recommendations import (
    RecommendationStream,
    RecommendationStreamManager,
)
import aiohttp


class RecommendationHandler:
    def __init__(self, client: ApiClient, base_url: str):
        self.client = client
        self.stream_manager = RecommendationStreamManager(base_url)
        self.active_streams: Dict[str, asyncio.Task] = {}
        self.stream_clients: Dict[str, aiohttp.ClientSession] = {}
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
        consecutive_failures = 0
        while True:
            await asyncio.sleep(1)

            stream = self.stream_manager.stream
            if stream is None:
                continue

            if not stream.is_alive():
                consecutive_failures += 1
                if consecutive_failures >= 2:
                    Logger.warning("SSE stream is dead, recreating immediately...")
                    await self._recreate_stream(user_id, container_id)
                    consecutive_failures = 0
            else:
                consecutive_failures = 0

    async def _recreate_stream(self, user_id: str, container_id: str):
        if self._is_reconnecting:
            return

        self._is_reconnecting = True
        try:
            if self.stream_manager.stream:
                await self.stream_manager.stream.close()

            self.stream_manager.stream = RecommendationStream(
                self.stream_manager.base_url
            )
            await self.stream_manager.stream.connect(user_id, container_id)
            self.stream_manager.stream.on_paths(self.stream_manager._broadcast_paths)
            self.stream_manager.stream.on_complete(
                self.stream_manager._broadcast_complete
            )

            Logger.info("SSE stream recreated successfully")
        except Exception as e:
            Logger.error(f"Failed to recreate SSE stream: {e}")
        finally:
            self._is_reconnecting = False

    async def reset(self):
        Logger.info("Resetting RecommendationHandler for new connection")

        if self._current_stream_id and self._current_stream_id in self.active_streams:
            self.active_streams[self._current_stream_id].cancel()

        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()

        await self.stream_manager.reset()

        self.active_streams.clear()
        self.stream_clients.clear()
        self._current_stream_id = None
        self._reconnect_task = None
        self._is_reconnecting = False

    @result_try
    async def close_stream(self, stream_id: str) -> Result[bool, Exception]:
        if stream_id in self.active_streams:
            self.active_streams[stream_id].cancel()
            del self.active_streams[stream_id]

        if stream_id in self.stream_clients:
            await self.stream_clients[stream_id].close()
            del self.stream_clients[stream_id]

        if stream_id in self.stream_manager.listeners:
            del self.stream_manager.listeners[stream_id]

        return Ok(True)

    @result_try
    async def get_recommendations_blocking(
        self, user_id: str, container_id: str, timeout: int = 20
    ) -> Result[List[str], Exception]:
        result_paths = []
        completed = asyncio.Event()
        retry_count = 0
        max_retries = 1

        while retry_count < max_retries:
            try:

                def on_paths(container_id: str, user_id: str, paths: List[str]):
                    result_paths.extend(paths)

                def on_complete():
                    completed.set()

                stream_id = await self.stream_manager.subscribe(
                    user_id, container_id, on_paths, on_complete
                )

                try:
                    await asyncio.wait_for(completed.wait(), timeout=timeout)
                    return Ok(result_paths)
                except asyncio.TimeoutError:
                    return Err(Exception(f"Timeout after {timeout} seconds"))
                finally:
                    if stream_id in self.stream_manager.listeners:
                        del self.stream_manager.listeners[stream_id]

            except aiohttp.ClientError as e:
                retry_count += 1
                Logger.warning(
                    f"Connection error (attempt {retry_count}/{max_retries}): {e}"
                )

                if retry_count >= max_retries:
                    return Err(Exception(f"Failed after {max_retries} attempts: {e}"))

                await asyncio.sleep(2**retry_count)

            except Exception as e:
                return Err(e)

        return Err(Exception("Max retries exceeded"))
