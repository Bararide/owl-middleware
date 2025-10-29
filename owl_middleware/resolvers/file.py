from typing import Union
from aiogram.types import Message, CallbackQuery

from models import File
from services import FileService, AuthService, ContainerService

from fastbot.core import Result, Err


async def resolve_file(
    event: Union[Message, CallbackQuery],
    file_service: FileService,
    auth_service: AuthService,
    container_service: ContainerService,
) -> Result[File, Exception]:
    user = await auth_service.get_user(event.from_user.id)
    if user.is_ok():
        containers = await container_service.get_containers_by_user_id(user.unwrap().id)
        return [
            await file_service.get_files_by_container(container)
            for container in containers
        ]
    else:
        return Err(Exception("User not found"))
