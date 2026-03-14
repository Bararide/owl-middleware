from typing import Optional, Callable, Dict, Any, List
from fastbot.logger.logger import Logger

from .client import SSEClient


class RecommendationStream:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.client: Optional[SSEClient] = None
        self._paths_handlers: List[Callable] = []
        self._complete_handlers: List[Callable] = []

    def on_paths(self, handler: Callable[[str, str, List[str]], None]):
        self._paths_handlers.append(handler)
        return self

    def on_complete(self, handler: Callable[[], None]):
        self._complete_handlers.append(handler)
        return self

    def _handle_data(self, data: Dict[str, Any]):
        try:
            container_id = data.get("container_id", "")
            user_id = data.get("user_id", "")
            paths = data.get("paths", [])

            if paths:
                Logger.info(f"Received {len(paths)} paths for container {container_id}")

                for handler in self._paths_handlers:
                    try:
                        handler(container_id, user_id, paths)
                    except Exception as e:
                        Logger.error(f"Error in paths handler: {e}")

        except Exception as e:
            Logger.error(f"Error processing SSE data: {e}")

    def _handle_end(self):
        Logger.info("Recommendation stream completed")

        for handler in self._complete_handlers:
            try:
                handler()
            except Exception as e:
                Logger.error(f"Error in complete handler: {e}")

    async def connect(
        self, user_id: str, container_id: str, headers: Optional[Dict] = None
    ):
        url = f"{self.base_url}/recommendations/stream"

        if headers is None:
            headers = {}

        params = f"?user_id={user_id}&container_id={container_id}"
        url_with_params = url + params

        self.client = SSEClient(url_with_params)

        self.client.on_data(self._handle_data)
        self.client.on_end(self._handle_end)

        await self.client.start(headers)

        return self

    async def close(self):
        if self.client:
            await self.client.close()


class RecommendationStreamManager:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.streams: Dict[str, RecommendationStream] = {}

    async def create_stream(
        self, stream_id: str, user_id: str, container_id: str
    ) -> RecommendationStream:
        stream = RecommendationStream(self.base_url)
        await stream.connect(user_id, container_id)
        self.streams[stream_id] = stream
        return stream

    async def close_stream(self, stream_id: str):
        if stream_id in self.streams:
            await self.streams[stream_id].close()
            del self.streams[stream_id]

    async def close_all(self):
        for stream in self.streams.values():
            await stream.close()
        self.streams.clear()
