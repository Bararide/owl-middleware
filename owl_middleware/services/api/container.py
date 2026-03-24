import os
from typing import List, Dict, Any
from fastbot.core import Result, result_try, Ok
from fastbot.logger.logger import Logger
from models import Tariff, Label, User, Container, SemanticEdge

from .client import ApiClient


class ContainerHandler:
    def __init__(self, client: ApiClient):
        self.client = client

    @result_try
    async def get_files_by_container_id_and_rebuild_index(
        self,
        user_id: str,
        container_id: str,
    ) -> Result[List[Dict[str, Any]], Exception]:
        payload = {
            "user_id": str(user_id),
            "container_id": str(container_id),
        }

        result = await self.client._make_request(
            "GET", "/container/files/refresh", json_data=payload
        )

        if result.is_ok():
            data = result.unwrap()
            if isinstance(data, dict) and "files" in data:
                return Ok(data["files"])
            return Ok([])

        return result

    @result_try
    async def get_files_by_container_id(
        self,
        user_id: str,
        container_id: str,
    ) -> Result[List[Dict[str, Any]], Exception]:
        payload = {
            "user_id": str(user_id),
            "container_id": str(container_id),
        }

        result = await self.client._make_request(
            "GET", "/container/files", json_data=payload
        )

        if result.is_ok():
            data = result.unwrap()
            if isinstance(data, dict):
                if "files" in data:
                    Logger.info(f"Files data: {data}")
                    return Ok(data["files"])
                elif "paths" in data:
                    files_list = [
                        {"path": path, "name": os.path.basename(path)}
                        for path in data["paths"]
                    ]
                    return Ok(files_list)
            return Ok([])

        return result

    @result_try
    async def create_container(
        self,
        user_id: str,
        container_id: str,
        tariff: Tariff,
        env_label: Label,
        type_label: Label,
        commands: List[str],
        privileged: bool,
    ) -> Result[Dict[str, Any], Exception]:
        payload = {
            "user_id": user_id,
            "container_id": container_id,
            "memory_limit": tariff.memory_limit,
            "storage_quota": tariff.storage_quota,
            "file_limit": tariff.file_limit,
            "env_label": {"key": env_label.key, "value": env_label.value},
            "type_label": {"key": type_label.key, "value": type_label.value},
            "commands": commands,
            "privileged": privileged,
        }

        return await self.client._make_request(
            "POST", "/containers/create", json_data=payload
        )

    @result_try
    async def delete_container(
        self, user_id: str, container_id: str
    ) -> Result[bool, Exception]:
        payload = {
            "user_id": str(user_id),
            "container_id": str(container_id),
        }

        result = await self.client._make_request(
            "DELETE", "/containers/delete", json_data=payload
        )

        if result.is_ok():
            data = result.unwrap()
            if isinstance(data, dict):
                status = data.get("status")
                return Ok(status in ["deleted", "deletion_pending"])
            return Ok(True)

        return result

    @result_try
    async def semantic_search(
        self, query: str, user: User, container: Container, limit: int = 5
    ) -> Result[Dict[str, Any], Exception]:
        Logger.info(container.id)

        payload = {
            "query": query,
            "limit": limit,
            "user_id": str(user.id),
            "container_id": str(container.id),
        }

        return await self.client._make_request(
            "POST", "/containers/semantic", json_data=payload
        )

    @result_try
    async def get_semantic_graph(
        self, user: User, container: Container
    ) -> Result[List[SemanticEdge], Exception]:
        Logger.info(container.id)

        payload = {
            "user_id": str(user.id),
            "container_id": str(container.id),
        }

        return await self.client._make_request(
            "GET",
            "/containers/semantic/graph",
            params=payload,
        )
