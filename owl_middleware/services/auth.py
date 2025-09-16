from models import User
from fastbot.core import Result, result_try
from fastbot.logger import Logger
from .db import DBService


class AuthService:
    def __init__(self, db_service: DBService):
        self.db_service = db_service
        self.users = self.db_service.db["users"]

    @result_try
    async def get_user(self, user_id: int) -> User:
        user = await self.users.find_one({"id": user_id})
        return User(**user) if user else User(id=user_id)

    @result_try
    async def register_user(self, user_data: dict) -> User:
        if await self.users.find_one({"id": user_data["id"]}):
            raise ValueError("User already exists")

        user = User(**user_data)
        await self.users.insert_one(user.dict())
        return user

    @result_try
    async def update_user(
        self, user_id: int, update_data: dict
    ) -> Result[bool, Exception]:
        result = await self.users.update_one({"id": user_id}, {"$set": update_data})
        return result.modified_count > 0

    @result_try
    async def delete_user(self, user_id: int) -> Result[bool, Exception]:
        result = await self.users.delete_one({"id": user_id})
        return result.deleted_count > 0
