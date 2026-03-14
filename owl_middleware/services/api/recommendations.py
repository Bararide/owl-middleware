import asyncio
from typing import List, Dict, Any, Optional
from fastbot.core import Result, result_try, Ok, Err
from fastbot.logger.logger import Logger
from .client import ApiClient
from .streams.recommendations.recommendations import RecommendationStreamManager


class RecommendationHandler:
    """Обработчик для работы с рекомендациями"""

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
        """Получение потока рекомендаций"""
        stream_id = f"{user_id}_{container_id}"

        stream = await self.stream_manager.create_stream(
            stream_id, user_id, container_id
        )

        if on_paths:
            stream.on_paths(on_paths)

        if on_complete:
            stream.on_complete(on_complete)

        return Ok(stream_id)

    @result_try
    async def close_stream(self, stream_id: str) -> Result[bool, Exception]:
        """Закрытие потока рекомендаций"""
        await self.stream_manager.close_stream(stream_id)
        return Ok(True)

    @result_try
    async def get_recommendations_blocking(
        self, user_id: str, container_id: str, timeout: int = 30
    ) -> Result[List[str], Exception]:
        """Блокирующее получение рекомендаций (ждет завершения потока)"""
        result_paths = []
        completed = asyncio.Event()

        def on_paths(container_id: str, user_id: str, paths: List[str]):
            result_paths.extend(paths)

        def on_complete():
            completed.set()

        stream_id = f"{user_id}_{container_id}_blocking"
        stream = await self.stream_manager.create_stream(
            stream_id, user_id, container_id
        )
        stream.on_paths(on_paths).on_complete(on_complete)

        try:
            await asyncio.wait_for(completed.wait(), timeout=timeout)
            return Ok(result_paths)
        except asyncio.TimeoutError:
            return Err(Exception(f"Timeout after {timeout} seconds"))
        finally:
            await self.stream_manager.close_stream(stream_id)
