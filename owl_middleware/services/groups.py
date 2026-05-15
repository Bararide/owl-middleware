from typing import Any, Dict, List
from fastbot.logger import Logger
from models import File, Group, File2Group
from fastbot.core import Result, result_try, Err, Ok
from datetime import datetime
from .db import DBService
from .file import FileService
from .container import ContainerService
from .api import ApiService


class GroupService:
    def __init__(
        self,
        db_service: DBService,
        container_service: ContainerService,
        file_service: FileService,
        api_service: ApiService,
    ):
        self.db_service = db_service
        self.container_service = container_service
        self.file_service = file_service
        self.api_service = api_service
        self.groups = self.db_service.db["groups"]
        self.file2group = self.db_service.db["file2group"]

    @result_try
    async def get_group(self, group_id: str) -> Result[Group, Exception]:
        group = await self.groups.find_one({"id": group_id})
        return (
            Ok(Group(**group))
            if group
            else Err(ValueError(f"Group {group_id} not found"))
        )

    @result_try
    async def get_groups_by_container(
        self, container_id: str
    ) -> Result[List[Group], Exception]:
        groups = await self.groups.find({"container_id": container_id}).to_list(None)
        return Ok([Group(**group) for group in groups])

    @result_try
    async def create_group(
        self, name: str, container_id: str, description: str = ""
    ) -> Result[Group, Exception]:
        existing_group = await self.groups.find_one(
            {"id": name, "container_id": container_id}
        )
        if existing_group:
            return Err(
                ValueError(f"Group {name} already exists in container {container_id}")
            )

        group = Group(
            id=name,
            container_id=container_id,
            description=description,
            created_at=datetime.utcnow(),
        )
        await self.groups.insert_one(group.dict())
        Logger.info(f"Group {name} created in container {container_id}")
        return Ok(group)

    @result_try
    async def update_group(
        self, group_id: str, container_id: str, description: str
    ) -> Result[bool, Exception]:
        result = await self.groups.update_one(
            {"id": group_id, "container_id": container_id},
            {"$set": {"description": description}},
        )
        if result.matched_count == 0:
            return Err(
                ValueError(f"Group {group_id} not found in container {container_id}")
            )

        Logger.info(f"Group {group_id} updated")
        return Ok(result.modified_count > 0)

    @result_try
    async def delete_group(
        self, group_id: str, container_id: str
    ) -> Result[bool, Exception]:
        await self.file2group.delete_many({"group_id": group_id})

        result = await self.groups.delete_one(
            {"id": group_id, "container_id": container_id}
        )

        if result.deleted_count > 0:
            Logger.info(f"Group {group_id} deleted from container {container_id}")
        return Ok(result.deleted_count > 0)

    @result_try
    async def add_file_to_group(
        self, file_id: str, group_id: str
    ) -> Result[File2Group, Exception]:
        existing = await self.file2group.find_one(
            {"file_id": file_id, "group_id": group_id}
        )
        if existing:
            return Err(ValueError(f"File {file_id} already in group {group_id}"))

        file2group = File2Group(file_id=file_id, group_id=group_id)
        await self.file2group.insert_one(file2group.dict())
        Logger.info(f"File {file_id} added to group {group_id}")
        return Ok(file2group)

    @result_try
    async def remove_file_from_group(
        self, file_id: str, group_id: str
    ) -> Result[bool, Exception]:
        result = await self.file2group.delete_one(
            {"file_id": file_id, "group_id": group_id}
        )
        if result.deleted_count > 0:
            Logger.info(f"File {file_id} removed from group {group_id}")
        return Ok(result.deleted_count > 0)

    @result_try
    async def get_files_by_group(
        self, group_id: str, container_id: str
    ) -> Result[List[File], Exception]:
        group_result = await self.get_group(group_id)
        if group_result.is_err():
            return group_result
        group = group_result.unwrap()

        file_relations = await self.file2group.find({"group_id": group_id}).to_list(
            None
        )
        if not file_relations:
            return Ok([])

        files = []
        for rel in file_relations:
            file_path = rel["file_id"]
            result = await self.api_service.files.get_file_content(
                str(file_path), str(container_id)
            )
            if result.is_ok():
                data = result.unwrap()
                if isinstance(data, dict):
                    file_obj = File(
                        id=file_path,
                        name=data.get("name", file_path.split("/")[-1]),
                        path=file_path,
                        size=data.get("size", 0),
                        container_id=group.container_id,
                        user_id="",
                        created_at=data.get(
                            "created_at", datetime.utcnow().isoformat()
                        ),
                        mime_type=data.get("mime_type", "application/octet-stream"),
                    )
                    files.append(file_obj)
                else:
                    Logger.warning(f"Unexpected response for {file_path}: {data}")
            else:
                Logger.warning(
                    f"Failed to fetch file {file_path}: {result.unwrap_err()}"
                )
        return Ok(files)

    @result_try
    async def get_groups_by_file(self, file_id: str) -> Result[List[Group], Exception]:
        file_relations = await self.file2group.find({"file_id": file_id}).to_list(None)

        if not file_relations:
            return Ok([])

        groups = []
        for rel in file_relations:
            group_result = await self.get_group(rel["group_id"])
            if group_result.is_ok():
                groups.append(group_result.unwrap())

        return Ok(groups)

    @result_try
    async def move_file_between_groups(
        self, file_id: str, from_group_id: str, to_group_id: str
    ) -> Result[bool, Exception]:
        existing = await self.file2group.find_one(
            {"file_id": file_id, "group_id": from_group_id}
        )
        if not existing:
            return Err(ValueError(f"File {file_id} not found in group {from_group_id}"))

        await self.remove_file_from_group(file_id, from_group_id)

        await self.add_file_to_group(file_id, to_group_id)

        Logger.info(f"File {file_id} moved from group {from_group_id} to {to_group_id}")
        return Ok(True)

    @result_try
    async def add_multiple_files_to_group(
        self, file_ids: List[str], group_id: str
    ) -> Result[List[File2Group], Exception]:
        results = []
        for file_id in file_ids:
            result = await self.add_file_to_group(file_id, group_id)
            if result.is_ok():
                results.append(result.unwrap())
            else:
                Logger.warning(
                    f"Failed to add file {file_id} to group {group_id}: {result.unwrap_err()}"
                )

        Logger.info(f"Added {len(results)} files to group {group_id}")
        return Ok(results)

    @result_try
    async def remove_multiple_files_from_group(
        self, file_ids: List[str], group_id: str
    ) -> Result[int, Exception]:
        removed_count = 0
        for file_id in file_ids:
            result = await self.remove_file_from_group(file_id, group_id)
            if result.is_ok() and result.unwrap():
                removed_count += 1

        Logger.info(f"Removed {removed_count} files from group {group_id}")
        return Ok(removed_count)

    @result_try
    async def get_group_stats(self, group_id: str) -> Result[Dict[str, Any], Exception]:
        group_result = await self.get_group(group_id)
        if group_result.is_err():
            return group_result

        group = group_result.unwrap()
        files = await self.get_files_by_group(group_id)

        total_size = sum(file.size or 0 for file in files)

        stats = {
            "group_id": group.id,
            "container_id": group.container_id,
            "description": group.description,
            "created_at": group.created_at,
            "total_files": len(files),
            "total_size": total_size,
            "average_file_size": total_size / len(files) if files else 0,
            "files": [
                {
                    "id": file.id,
                    "name": file.name,
                    "size": file.size,
                    "created_at": file.created_at,
                }
                for file in files
            ],
        }

        return Ok(stats)

    @result_try
    async def delete_container_groups(
        self, container_id: str
    ) -> Result[int, Exception]:
        groups = await self.get_groups_by_container(container_id)

        deleted_count = 0
        for group in groups:
            result = await self.delete_group(group.id, container_id)
            if result.is_ok() and result.unwrap():
                deleted_count += 1

        Logger.info(f"Deleted {deleted_count} groups from container {container_id}")
        return Ok(deleted_count)
