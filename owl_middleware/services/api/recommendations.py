import asyncio
from typing import List, Dict, Any, Optional
from fastbot.core import Result, result_try, Ok, Err
from fastbot.logger.logger import Logger
from .client import ApiClient
from .streams.recommendations.recommendations import RecommendationStreamManager


class RecommendationHandler:
    def __init__(self, client: ApiClient, base_url: str):
        self.client = client
        self.stream_manager = RecommendationStreamManager(base_url)

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
        if stream_id in self.stream_manager.listeners:
            del self.stream_manager.listeners[stream_id]
        return Ok(True)

    @result_try
    async def get_recommendations_blocking(
        self, user_id: str, container_id: str, timeout: int = 30
    ) -> Result[List[str], Exception]:
        result_paths = []
        completed = asyncio.Event()

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
