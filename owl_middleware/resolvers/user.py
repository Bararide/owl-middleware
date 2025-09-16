from typing import Union
from aiogram.types import Message, CallbackQuery

from models import User
from services import AuthService

from fastbot.core import Result


async def resolve_user(
    event: Union[Message, CallbackQuery], auth_service: AuthService
) -> Result[User, Exception]:
    return await auth_service.get_user(event.from_user.id)
