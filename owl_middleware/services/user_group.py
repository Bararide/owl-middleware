from typing import Any, Dict, List
from fastbot.logger import Logger
from models import User, Tariff, Label, Container, UserGroup, User2Group
from fastbot.core import Result, result_try, Err, Ok
from .db import DBService
from .api import ApiService
from .file import FileService


class UserGroupService:
    def __init__(
        self,
        db_service: DBService,
    ):
        self.db_service = db_service
        self.user_groups = self.db_service.db["user_groups"]
        self.user2group = self.db_service.db["user2group"]
        self.container2group = self.db_service.db["container2group"]

    @result_try
    async def _exist_group(self, group_id: str) -> bool:
        return await self.user_groups.find_one({"id": group_id})

    @result_try
    async def get_group_users(self, group_id: str) -> Result[List[User], Exception]:
        users = await self.user_groups.find({"id": id}).to_list(None)
        return (
            Ok([User(**user) for user in users])
            if users
            else Err(Exception("Users not found"))
        )

    @result_try
    async def create_user_group(self, group: UserGroup) -> Result[UserGroup, Exception]:
        if self._exist_group(group.id):
            return Err(ValueError("Group with this ID already exists"))

        await self.user_groups.insert_one(group.model_dump())
        return Ok(group)

    @result_try
    async def delete_user_group(self, group_id: str) -> Result[bool, Exception]:
        result = await self.user_groups.delete_one({"id": group_id})
        return Ok(result.deleted_count > 0)

    @result_try
    async def add_user_to_group(
        self, user: User, group: UserGroup
    ) -> Result[bool, Exception]:
        if self._exist_group(group.id):
            return Err(ValueError("User already belongs to this group"))

        await self.user2group.insert_one(group.model_dump())
        return Ok(True)

    @result_try
    async def delete_user_from_group(
        self, user: User, group: UserGroup
    ) -> Result[bool, Exception]:
        result = await self.user2group.delete_one(
            {"user_id": str(user.id), "group_id": str(group.id)}
        )
        return Ok(result.deleted_count > 0)

    @result_try
    async def get_user_groups(self, user: User) -> Result[List[UserGroup], Exception]:
        groups = await self.user2group.find({"user_id": str(user.id)}).to_list(None)
        return (
            Ok([UserGroup(**group) for group in groups])
            if groups
            else Err(Exception("Groups not found"))
        )

    @result_try
    async def get_group_containers(
        self, group: UserGroup
    ) -> Result[List[Container], Exception]:
        containers = await self.container2group.find(
            {"group_id": str(group.id)}
        ).to_list(None)
        return (
            Ok([Container(**container) for container in containers])
            if containers
            else Err(Exception("Containers not found"))
        )

    @result_try
    async def add_container_to_group(
        self, container: Container, group: UserGroup
    ) -> Result[bool, Exception]:
        await self.container2group.insert_one(
            {"container_id": str(container.id), "group_id": str(group.id)}
        )
        return Ok(True)

    @result_try
    async def delete_container_from_group(
        self, container: Container, group: UserGroup
    ) -> Result[bool, Exception]:
        result = await self.container2group.delete_one(
            {"container_id": str(container.id), "group_id": str(group.id)}
        )
        return Ok(result.deleted_count > 0)

    @result_try
    async def get_group_by_id(self, group_id: str) -> Result[UserGroup, Exception]:
        group = await self.user_groups.find_one({"id": group_id})
        return Ok(UserGroup(**group)) if group else Err(Exception("Group not found"))
