from typing import Union
from aiogram.types import Message, CallbackQuery
from fastapi import Request
from fastbot.logger import Logger
from models import User
from services import AuthService
from fastbot.core import Result


async def resolve_user(
    source: Union[Message, CallbackQuery, Request], auth_service: AuthService
) -> Result[User, Exception]:
    if hasattr(source, "from_user"):
        tg_id = source.from_user.id
        Logger.debug("ITS WORK")
        return await auth_service.get_user_by_tg_id(tg_id)

    elif isinstance(source, Request):
        auth_header = source.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]
            user_result = await auth_service.get_user_by_token(token)
            if user_result.is_ok():
                return user_result

        token = source.query_params.get("token")
        if token:
            user_result = await auth_service.get_user_by_token(token)
            if user_result.is_ok():
                return user_result

        tg_id_header = source.headers.get("X-Telegram-User-ID")
        if tg_id_header and tg_id_header.isdigit():
            return await auth_service.get_user_by_tg_id(int(tg_id_header))

    return Result.Err(Exception("Authentication required"))
