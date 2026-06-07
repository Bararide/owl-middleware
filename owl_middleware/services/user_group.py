from typing import Any, Dict, List, Optional
from fastbot.logger import Logger
from models import (
    User,
    Tariff,
    Label,
    Container,
    UserGroup,
    User2Group,
    Container2Group,
)
from fastbot.core import Result, result_try, Err, Ok
from models.roles.group_role import GroupRole
from models.permissions.container_permission import ContainerPermission
from .db import DBService
from .api import ApiService
from .file import FileService
from datetime import datetime


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
        group = await self.user_groups.find_one({"id": group_id})
        return group is not None

    @result_try
    async def get_all_groups(self) -> Result[List[UserGroup], Exception]:
        groups = await self.user_groups.find({}).to_list(None)
        return Ok([UserGroup(**group) for group in groups]) if groups else Ok([])

    @result_try
    async def get_group_users(self, group_id: str) -> Result[List[User], Exception]:
        users = await self.user_groups.find({"id": group_id}).to_list(None)
        return (
            Ok([User(**user) for user in users])
            if users
            else Err(Exception("Users not found"))
        )

    @result_try
    async def create_user_group(self, group: UserGroup) -> Result[UserGroup, Exception]:
        existing = await self.user_groups.find_one({"id": group.id})
        if existing:
            return Err(ValueError("Group with this ID already exists"))

        group_data = {
            "id": group.id,
            "description": group.description,
            "created_at": group.created_at or datetime.now().isoformat(),
            "color": getattr(group, "color", "#ff9800"),
        }
        await self.user_groups.insert_one(group_data)
        return Ok(group)

    @result_try
    async def update_user_group(
        self,
        group_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        color: Optional[str] = None,
    ) -> Result[UserGroup, Exception]:
        group = await self.user_groups.find_one({"id": group_id})
        if not group:
            return Err(Exception("Group not found"))

        update_data = {}
        if description is not None:
            update_data["description"] = description
        if color is not None:
            update_data["color"] = color

        if update_data:
            await self.user_groups.update_one({"id": group_id}, {"$set": update_data})

        updated_group = await self.user_groups.find_one({"id": group_id})
        return Ok(UserGroup(**updated_group))

    @result_try
    async def delete_user_group(self, group_id: str) -> Result[bool, Exception]:
        result = await self.user_groups.delete_one({"id": group_id})
        return Ok(result.deleted_count > 0)

    @result_try
    async def delete_all_members(self, group_id: str) -> Result[bool, Exception]:
        result = await self.user2group.delete_many({"group_id": group_id})
        return Ok(True)

    @result_try
    async def delete_all_container_accesses(
        self, group_id: str
    ) -> Result[bool, Exception]:
        result = await self.container2group.delete_many({"group_id": group_id})
        return Ok(True)

    @result_try
    async def add_user_to_group(
        self, user: User, group: UserGroup, role: GroupRole = GroupRole.member
    ) -> Result[bool, Exception]:
        existing = await self.user2group.find_one(
            {"user_id": str(user.id), "group_id": str(group.id)}
        )
        if existing:
            return Err(ValueError("User already belongs to this group"))

        member_data = {
            "user_id": str(user.id),
            "group_id": str(group.id),
            "role": role.value if hasattr(role, "value") else str(role),
            "joined_at": datetime.now().isoformat(),
        }
        await self.user2group.insert_one(member_data)
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
    async def update_member_role(
        self, group_id: str, user_id: str, new_role: GroupRole
    ) -> Result[bool, Exception]:
        result = await self.user2group.update_one(
            {"user_id": user_id, "group_id": group_id},
            {
                "$set": {
                    "role": (
                        new_role.value if hasattr(new_role, "value") else str(new_role)
                    )
                }
            },
        )
        if result.matched_count == 0:
            return Err(Exception("Member not found"))
        return Ok(True)

    @result_try
    async def get_user_groups(self, user: User) -> Result[List[UserGroup], Exception]:
        membership = await self.user2group.find({"user_id": str(user.id)}).to_list(None)
        if not membership:
            return Ok([])

        group_ids = [m["group_id"] for m in membership]
        groups = await self.user_groups.find({"id": {"$in": group_ids}}).to_list(None)
        return Ok([UserGroup(**group) for group in groups])

    @result_try
    async def get_group_members(self, group_id: str) -> Result[List[Any], Exception]:
        members = await self.user2group.find({"group_id": group_id}).to_list(None)
        return Ok(members) if members else Ok([])

    @result_try
    async def get_group_containers(
        self, group: UserGroup
    ) -> Result[List[Any], Exception]:
        containers = await self.container2group.find(
            {"group_id": str(group.id)}
        ).to_list(None)
        return Ok(containers) if containers else Ok([])

    @result_try
    async def add_container_to_group(
        self,
        container: Container,
        group: UserGroup,
        permission: ContainerPermission = ContainerPermission.read_write,
    ) -> Result[bool, Exception]:
        existing = await self.container2group.find_one(
            {"container_id": str(container.id), "group_id": str(group.id)}
        )
        if existing:
            return Err(ValueError("Group already has access to this container"))

        access_data = {
            "container_id": str(container.id),
            "group_id": str(group.id),
            "permission": (
                permission.value if hasattr(permission, "value") else str(permission)
            ),
            "granted_at": datetime.now().isoformat(),
        }
        await self.container2group.insert_one(access_data)
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
    async def get_container_accesses(
        self, container_id: str
    ) -> Result[List[Any], Exception]:
        accesses = await self.container2group.find(
            {"container_id": container_id}
        ).to_list(None)
        return Ok(accesses) if accesses else Ok([])

    @result_try
    async def get_user_container_accesses(
        self, user_id: str
    ) -> Result[List[Dict], Exception]:
        memberships = await self.user2group.find({"user_id": user_id}).to_list(None)
        if not memberships:
            return Ok([])

        group_ids = [m["group_id"] for m in memberships]
        accesses = await self.container2group.find(
            {"group_id": {"$in": group_ids}}
        ).to_list(None)

        return Ok(accesses) if accesses else Ok([])

    @result_try
    async def get_group_by_id(self, group_id: str) -> Result[UserGroup, Exception]:
        group = await self.user_groups.find_one({"id": group_id})
        return Ok(UserGroup(**group)) if group else Err(Exception("Group not found"))
