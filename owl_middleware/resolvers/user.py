from typing import Union
from aiogram.types import Message, CallbackQuery

from models import User
from services import AuthService

from fastbot.core import Result


async def resolve_user(
    event: Union[Message, CallbackQuery], auth_service: AuthService
) -> Result[User, Exception]:
    return await auth_service.get_user(event.from_user.id)


async def resolve_user_http(
    request, auth_service: AuthService
) -> Result[User, Exception]:
    user_id = request.headers.get("X-User-ID")
    if not user_id:
        return Result.Err(Exception("Not authenticated"))

    return await auth_service.get_user_by_id(user_id)
