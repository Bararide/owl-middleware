from typing import Any, Dict, List
from fastbot.logger import Logger
from models import User, Tariff, Label, Container
from fastbot.core import Result, result_try, Err, Ok
from .db import DBService
from .api import ApiService
from .file import FileService


class ContainerService:
    def __init__(
        self, db_service: DBService, api_service: ApiService, file_service: FileService
    ):
        self.db_service = db_service
        self.api_service = api_service
        self.containers = self.db_service.db["containers"]
        self.file_service = file_service

    @result_try
    async def get_container(self, container_id: str) -> Result[Container, Exception]:
        container = await self.containers.find_one({"id": container_id})
        return (
            Ok(Container(**container))
            if container
            else Err(ValueError("Container not found"))
        )

    @result_try
    async def get_containers_by_user_id(
        self, user_id: str
    ) -> Result[List[Container], Exception]:
        Logger.debug("ITS WORK TOO")
        containers = await self.containers.find({"user_id": user_id}).to_list(None)
        Logger.debug([Container(**container) for container in containers])
        return Ok([Container(**container) for container in containers])

    @result_try
    async def create_container(
        self, container_data: dict
    ) -> Result[Container, Exception]:
        existing_container = await self.containers.find_one(
            {"tg_id": container_data["container_id"]}
        )
        if existing_container:
            return Err(ValueError("Container with this ID already exists"))

        tariff = Tariff(
            memory_limit=container_data["memory_limit"],
            storage_quota=container_data["storage_quota"],
            file_limit=container_data["file_limit"],
        )

        env_label = Label(
            key=container_data["env_label"]["key"],
            value=container_data["env_label"]["value"],
        )

        type_label = Label(
            key=container_data["type_label"]["key"],
            value=container_data["type_label"]["value"],
        )

        container = Container(
            id=container_data["container_id"],
            user_id=container_data["user_id"],
            tariff=tariff,
            env_label=env_label,
            type_label=type_label,
            privileged=container_data.get("privileged", False),
            commands=container_data.get("commands", []),
        )

        await self.containers.insert_one(container.model_dump())
        return Ok(container)

    @result_try
    async def delete_container(self, container_id: str) -> Result[bool, Exception]:
        result = await self.containers.delete_one({"id": container_id})
        return Ok(result.deleted_count > 0)

    @result_try
    async def check_container_limits(
        self, container_id: str
    ) -> Result[Dict[str, Any], Exception]:
        container_result = await self.get_container(container_id)
        if container_result.is_err():
            return container_result

        file_service = FileService(self.db_service, self.api_service)
        container = container_result.unwrap()
        files = await file_service.get_files_by_container(container)

        total_size = sum(file.size or 0 for file in files)

        limits_status = {
            "storage": {
                "used": total_size,
                "limit": container.tariff.storage_quota,
                "exceeded": total_size > container.tariff.storage_quota,
                "usage_percent": (
                    (total_size / container.tariff.storage_quota * 100)
                    if container.tariff.storage_quota > 0
                    else 0
                ),
            },
            "files": {
                "used": len(files),
                "limit": container.tariff.file_limit,
                "exceeded": len(files) > container.tariff.file_limit,
                "usage_percent": (
                    (len(files) / container.tariff.file_limit * 100)
                    if container.tariff.file_limit > 0
                    else 0
                ),
            },
        }

        return Ok(limits_status)

    @result_try
    async def update_container(
        self, container_id: str, update_data: dict
    ) -> Result[bool, Exception]:
        if (
            "memory_limit" in update_data
            or "storage_quota" in update_data
            or "file_limit" in update_data
        ):
            current_result = await self.get_container(container_id)
            if current_result.is_err():
                return current_result

            current = current_result.unwrap()
            tariff_update = {
                "memory_limit": update_data.pop(
                    "memory_limit", current.tariff.memory_limit
                ),
                "storage_quota": update_data.pop(
                    "storage_quota", current.tariff.storage_quota
                ),
                "file_limit": update_data.pop("file_limit", current.tariff.file_limit),
            }
            update_data["tariff"] = Tariff(**tariff_update).model_dump()

        result = await self.containers.update_one(
            {"id": container_id}, {"$set": update_data}
        )
        return Ok(result.modified_count > 0)

    @result_try
    async def delete_container(
        self, user_id: str, container_id: str
    ) -> Result[bool, Exception]:
        container_result = await self.get_container(container_id)
        if container_result.is_err():
            return container_result

        files = await self.file_service.get_files_by_container(
            container_result.unwrap()
        )

        [await self.file_service.delete_file(file.id) for file in files]

        self.api_service.delete_container(user_id, container_id)

        result = await self.containers.delete_one({"id": container_id})
        return Ok(result.deleted_count > 0)

    @result_try
    async def get_container_stats(
        self, container_id: str
    ) -> Result[Dict[str, Any], Exception]:
        container_result = await self.get_container(container_id)
        if container_result.is_err():
            return container_result

        container = container_result.unwrap()
        files = await self.file_service.get_files_by_container(container)

        total_size = sum(file.size or 0 for file in files)
        storage_usage_percent = (
            (total_size / container.tariff.storage_quota * 100)
            if container.tariff.storage_quota > 0
            else 0
        )

        stats = {
            "container_id": container_id,
            "user_id": container.user_id,
            "total_files": len(files),
            "total_size": total_size,
            "storage_quota": container.tariff.storage_quota,
            "storage_usage_percent": round(storage_usage_percent, 2),
            "memory_limit": container.tariff.memory_limit,
            "file_limit": container.tariff.file_limit,
            "files_usage_percent": (
                (len(files) / container.tariff.file_limit * 100)
                if container.tariff.file_limit > 0
                else 0
            ),
            "privileged": container.privileged,
            "commands": container.commands,
            "environment": container.env_label.value,
            "type": container.type_label.value,
        }

        return Ok(stats)

    @result_try
    async def check_container_limits(
        self, container_id: str
    ) -> Result[Dict[str, Any], Exception]:
        """Проверка лимитов контейнера"""
        container_result = await self.get_container(container_id)
        if container_result.is_err():
            return container_result

        file_service = FileService(self.db_service, self.api_service)
        container = container_result.unwrap()
        files = await file_service.get_files_by_container(container)

        total_size = sum(file.size or 0 for file in files)

        limits_status = {
            "storage": {
                "used": total_size,
                "limit": container.tariff.storage_quota,
                "exceeded": total_size > container.tariff.storage_quota,
            },
            "files": {
                "used": len(files),
                "limit": container.tariff.file_limit,
                "exceeded": len(files) > container.tariff.file_limit,
            },
            "memory": {"limit": container.tariff.memory_limit},
        }

        return Ok(limits_status)
