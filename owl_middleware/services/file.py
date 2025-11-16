from typing import Any, Dict
from models import File, User, Container
from fastbot.core import Result, result_try, Err, Ok
from .db import DBService
from .api import ApiService


class FileService:
    def __init__(self, db_service: DBService, api_service: ApiService):
        self.db_service = db_service
        self.api_service = api_service
        self.files = self.db_service.db["files"]

    @result_try
    async def get_file(self, file_id: str) -> File:
        file = await self.files.find_one({"id": file_id})
        return File(**file) if file else None

    @result_try
    async def create_file(self, file_data: dict) -> File:
        existing_file = await self.files.find_one({"id": file_data["id"]})
        if existing_file:
            return Err(ValueError("File with this ID already exists"))

        file = File(**file_data)
        await self.files.insert_one(file.model_dump())
        return Ok(file)

    @result_try
    async def create_file_with_sync(
        self, file_data: dict, content: str
    ) -> Result[File, Exception]:
        create_db_result = await self.create_file(file_data)
        if create_db_result.is_err():
            return create_db_result

        file = create_db_result.unwrap()

        create_api_result = await self.api_service.create_file_from_model(file, content)
        if create_api_result.is_err():
            await self.delete_file(file.id)
            return create_api_result

        return Ok(file)

    @result_try
    async def get_file_with_content(
        self, file_id: str
    ) -> Result[Dict[str, Any], Exception]:
        file_result = await self.get_file(file_id)
        if file_result.is_err() or file_result.unwrap() is None:
            return file_result

        file = file_result.unwrap()

        path = f"/{file.id}_{file.name}" if file.name else f"/{file.id}"
        content_result = await self.api_service.read_file(path)

        if content_result.is_err():
            return content_result

        content_data = content_result.unwrap()

        combined_data = {
            **file.model_dump(),
            "content": content_data.get("content", ""),
            "api_size": content_data.get("size", 0),
        }

        return Ok(combined_data)

    @result_try
    async def update_file(
        self, file_id: str, update_data: dict
    ) -> Result[bool, Exception]:
        result = await self.files.update_one({"id": file_id}, {"$set": update_data})
        return result.modified_count > 0

    @result_try
    async def delete_file(self, file_id: str) -> Result[bool, Exception]:
        result = await self.files.delete_one({"id": file_id})
        return result.deleted_count > 0

    @result_try
    async def get_files_by_container(self, container_id: str) -> list[File]:
        files = await self.files.find({"container_id": container_id}).to_list(None)
        return [File(**file) for file in files]
