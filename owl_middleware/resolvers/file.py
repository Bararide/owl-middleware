from typing import Union
from aiogram.types import Message, CallbackQuery

from models import File
from services import FileService, AuthService

from fastbot.core import Result, Err


async def resolve_file(
    event: Union[Message, CallbackQuery],
    file_service: FileService,
    auth_service: AuthService,
) -> Result[File, Exception]:
    user = await auth_service.get_user(event.from_user.id)
    if user.is_ok():
        return await file_service.get_files_by_user(user.unwrap())
    else:
        return Err(Exception("User not found"))
