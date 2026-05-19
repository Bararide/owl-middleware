import asyncio
from typing import List, Dict, Optional
from fastbot.core import Result, result_try, Ok, Err
from fastbot.logger.logger import Logger
from .client import ApiClient
from .streams.recommendations.recommendations import RecommendationStreamManager
import aiohttp


class RecommendationHandler:
    def __init__(self, client: ApiClient, base_url: str):
        self.client = client
        self.stream_manager = RecommendationStreamManager(base_url)
        self.active_streams: Dict[str, asyncio.Task] = {}
        self.stream_clients: Dict[str, aiohttp.ClientSession] = {}

    @result_try
    async def get_recommendations_stream(
        self,
        user_id: str,
        container_id: str,
        on_paths: Optional[callable] = None,
        on_complete: Optional[callable] = None,
    ) -> Result[str, Exception]:
        stream_id = await self.stream_manager.subscribe(
            user_id, container_id, on_paths, on_complete
        )

        return Ok(stream_id)

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
        self, user_id: str, container_id: str, timeout: int = 30
    ) -> Result[List[str], Exception]:
        result_paths = []
        completed = asyncio.Event()
        retry_count = 0
        max_retries = 3

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
