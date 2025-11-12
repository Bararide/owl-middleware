# resolvers/file.py
from typing import Union, List
from aiogram.types import Message, CallbackQuery

from fastbot.logger import Logger
from models import File
from services import FileService, AuthService, ContainerService

from fastbot.core import Result, Ok, Err


async def resolve_file(
    event: Union[Message, CallbackQuery],
    file_service: FileService,
    auth_service: AuthService,
    container_service: ContainerService,
) -> Result[List[File], Exception]:
    Logger.debug(f"Resolving files for user: {event.from_user.id}")

    user = await auth_service.get_user_by_tg_id(event.from_user.id)

    if user.is_err():
        return Err(Exception("User not found"))

    containers = await container_service.get_containers_by_user_id(user.unwrap().id)
    all_files = []

    for container in containers:
        files_result = await file_service.get_files_by_container(container.id)
        if files_result.is_ok():
            all_files.extend(files_result.unwrap())

    return Ok(all_files)
