from typing import Any, Dict
from models import User, Tariff, Label, Container
from fastbot.core import Result, result_try, Err, Ok
from .db import DBService
from .api import ApiService


class ContainerService:
    def __init__(self, db_service: DBService, api_service: ApiService):
        self.db_service = db_service
        self.api_service = api_service
        self.containers = self.db_service.db["containers"]

    @result_try
    async def get_container(self, container_id: str) -> Container:
        container = await self.containers.find_one({"id": container_id})
        return Container(**container) if container else None

    @result_try
    async def get_containers_by_user_id(self, user_id: str) -> Container:
        containers = await self.containers.find({"user_id": user_id}).to_list(None)
        return [Container(**container) for container in containers]
