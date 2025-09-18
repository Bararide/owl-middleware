from models import File, User
from fastbot.core import Result, result_try, Err, Ok
from .db import DBService


class FileService:
    def __init__(self, db_service: DBService):
        self.db_service = db_service
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
    async def get_files_by_user(self, user: User) -> list[File]:
        files = await self.files.find({"user_id": user.id}).to_list(None)
        return [File(**file) for file in files]
