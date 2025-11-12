# resolvers.py
from typing import Union
from aiogram.types import Message, CallbackQuery
from fastapi import Request
from models import User
from services import AuthService
from fastbot.core import Result


async def resolve_user(
    source: Union[Message, CallbackQuery, Request], auth_service: AuthService
) -> Result[User, Exception]:
    if hasattr(source, "from_user"):
        tg_user = source.from_user
        user_result = await auth_service.get_user_by_tg_id(tg_user.id)

        if user_result.is_err() or not user_result.unwrap():
            user_data = {
                "id": tg_user.id,
                "username": tg_user.username,
                "first_name": tg_user.first_name,
                "last_name": tg_user.last_name,
            }
            user_result = await auth_service.register_telegram_user(user_data)

        return user_result

    elif isinstance(source, Request):
        auth_header = source.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]
            return await auth_service.get_user_by_token(token)

        token = source.query_params.get("token")
        if token:
            return await auth_service.get_user_by_token(token)

    return Result.Err(Exception("Authentication required"))
