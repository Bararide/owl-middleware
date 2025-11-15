import jwt
import hashlib

from datetime import datetime, timedelta
from fastbot.core import Result, result_try
from fastbot.logger import Logger
from models import User, UserCreate


class AuthService:
    def __init__(self, db_service, jwt_secret: str, algorithm: str = "HS256"):
        self.db_service = db_service
        self.users = self.db_service.db["users"]
        self.jwt_secret = jwt_secret
        self.algorithm = algorithm

    async def ensure_indexes(self):
        await self.users.create_index("id", unique=True)
        await self.users.create_index("tg_id", unique=True, sparse=True)
        await self.users.create_index("email", unique=True, sparse=True)

    async def _get_next_id(self) -> int:
        result = await self.users.find_one({}, sort=[("id", -1)])
        return (result["id"] if result else 0) + 1

    @result_try
    async def get_user(self, user_id: int) -> Result[User, Exception]:
        user = await self.users.find_one({"id": user_id})
        return User(**user) if user else None

    @result_try
    async def get_user_by_tg_id(self, tg_id: int) -> Result[User, Exception]:
        user = await self.users.find_one({"tg_id": tg_id})
        Logger.debug(User(**user) if user else None)
        return User(**user) if user else None

    @result_try
    async def get_user_by_email(self, email: str) -> Result[User, Exception]:
        user = await self.users.find_one({"email": email})
        return User(**user) if user else None

    @result_try
    async def create_user(self, user_data: UserCreate) -> Result[User, Exception]:
        if user_data.tg_id and await self.users.find_one({"tg_id": user_data.tg_id}):
            raise ValueError("Telegram user already exists")

        if user_data.email and await self.users.find_one({"email": user_data.email}):
            raise ValueError("Email already registered")

        user_id = await self._get_next_id()
        user_dict = user_data.dict()
        user_dict["id"] = user_id
        user_dict["registered_at"] = datetime.now().isoformat()

        if user_dict.get("password"):
            user_dict["password_hash"] = self._hash_password(user_dict.pop("password"))

        user = User(**user_dict)
        await self.users.insert_one(user.dict())
        return user

    @result_try
    async def register_telegram_user(
        self, tg_user_data: dict
    ) -> Result[User, Exception]:
        user_create = UserCreate(
            tg_id=tg_user_data["id"],
            username=tg_user_data.get("username"),
            first_name=tg_user_data.get("first_name", "Unknown"),
            last_name=tg_user_data.get("last_name"),
            auth_method="telegram",
        )
        return await self.create_user(user_create)

    @result_try
    async def register_email_user(
        self, email: str, password: str, user_data: dict
    ) -> Result[User, Exception]:
        user_create = UserCreate(
            email=email,
            password=password,
            first_name=user_data.get("first_name", "Unknown"),
            last_name=user_data.get("last_name"),
            auth_method="email",
        )
        return await self.create_user(user_create)

    def _hash_password(self, password: str) -> str:
        return hashlib.sha256(password.encode()).hexdigest()

    def _verify_password(self, password: str, password_hash: str) -> bool:
        return self._hash_password(password) == password_hash

    @result_try
    async def authenticate_email(
        self, email: str, password: str
    ) -> Result[User, Exception]:
        user_data = await self.users.find_one({"email": email})
        if not user_data:
            return Result.Err(Exception("User not found"))

        if not self._verify_password(password, user_data.get("password_hash", "")):
            return Result.Err(Exception("Invalid password"))

        return Result.Ok(User(**user_data))

    def generate_jwt_token(self, user, expires_hours: int = 24) -> str:
        payload = {
            "user_id": user.id,
            "exp": datetime.utcnow() + timedelta(hours=expires_hours),
            "iat": datetime.utcnow(),
            "auth_method": getattr(user, "auth_method", "telegram"),
        }
        return jwt.encode(payload, self.jwt_secret, algorithm=self.algorithm)

    def verify_jwt_token(self, token: str):
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=[self.algorithm])
            return payload
        except jwt.ExpiredSignatureError:
            raise Exception("Token expired")
        except jwt.InvalidTokenError:
            raise Exception("Invalid token")

    @result_try
    async def get_user_by_token(self, token: str) -> Result[User, Exception]:
        payload = self.verify_jwt_token(token)
        return await self.get_user(payload["user_id"])

    @result_try
    async def get_user_by_token(self, token: str) -> Result[User, Exception]:
        payload_result = self.verify_jwt_token(token)
        if payload_result.is_err():
            return Result.Err(payload_result.unwrap_err())

        payload = payload_result.unwrap()
        return await self.get_user(payload["user_id"])
