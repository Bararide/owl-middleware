from .client import ApiClient
from .container import ContainerHandler
from .file import FileHandler
from .system import SystemHandler
from .recommendations import RecommendationHandler


class ApiService:
    def __init__(self, base_url: str):
        self.client = ApiClient(base_url)
        self.containers = ContainerHandler(self.client)
        self.files = FileHandler(self.client)
        self.system = SystemHandler(self.client)
        self.recommendations = RecommendationHandler(self.client, base_url)

    async def __aenter__(self):
        await self.client.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.close()
        await self.recommendations.stream_manager.close_all()
