from aiogram import types
from aiogram.enums import ParseMode

from fastbot.engine import ContextEngine
from fastbot.engine import TemplateEngine
from fastbot.logger import Logger
from models import User
from services import AuthService, FileService, ContainerService, ApiService
from fastbot.decorators import (
    with_template_engine,
    with_parse_mode,
    with_auto_reply,
)


@with_template_engine
@with_parse_mode(ParseMode.HTML)
@with_auto_reply("commands/read_file.j2")
async def handle_read_file_callback(
    callback: types.CallbackQuery,
    user: User,
    ten: TemplateEngine,
    cen: ContextEngine,
    file_service: FileService,
    api_service: ApiService,
):
    await callback.answer()

    file_id = callback.data.replace("file_", "")

    file_result = await file_service.get_file(file_id)
    if file_result.is_ok() and file_result.unwrap():
        file = file_result.unwrap()
        path = f"/{file.id}_{file.name}"
    else:
        path = file_id

    read_result = await api_service.read_file(path)

    if read_result.is_err():
        error = read_result.unwrap_err()
        Logger.error(f"Read file error: {error}")
        return {"context": await cen.get("read_file", error=f"Read error: {error}")}

    file_data = read_result.unwrap()

    return {
        "context": await cen.get(
            "read_file",
            path=file_data.get("path", path),
            content=file_data.get("content", ""),
            size=file_data.get("size", 0),
        )
    }

    try:
        pass
    except Exception as e:
        Logger.error(f"Error in handle_read_file_callback: {e}")
        return {
            "context": await cen.get(
                "read_file",
                error=f"Ошибка при выборе контейнера: {str(e)}",
            )
        }


@with_template_engine
@with_parse_mode(ParseMode.HTML)
@with_auto_reply("filters/create_container_help.j2")
async def handle_create_container_callback(
    callback: types.CallbackQuery,
    user: User,
    ten: TemplateEngine,
    cen: ContextEngine,
):
    await callback.answer()

    return {"context": await cen.get("create_container_help", user_id=user.tg_id)}


@with_template_engine
@with_parse_mode(ParseMode.HTML)
@with_auto_reply("filters/file_list.j2")
async def callback_file_list(
    callback: types.CallbackQuery,
    user: User,
    ten: TemplateEngine,
    file_service: FileService,
    auth_service: AuthService,
    container_service: ContainerService,
    cen: ContextEngine,
):
    containers_result = await container_service.get_containers_by_user_id(
        str(user.tg_id)
    )

    if containers_result.is_err():
        return {
            "context": await cen.get(
                "file_list", error="Ошибка при получении контейнеров"
            )
        }

    containers = containers_result.unwrap()

    all_files = []
    for container in containers:
        files_result = await file_service.get_files_by_container(container.id)
        if files_result.is_ok():
            all_files.extend(files_result.unwrap())

    return {"context": await cen.get("file_list", files=all_files)}


@with_template_engine
@with_parse_mode(ParseMode.HTML)
@with_auto_reply("filters/file_upload.j2")
async def callback_file_upload(
    callback: types.CallbackQuery,
    user: User,
    ten: TemplateEngine,
    file_service: FileService,
    auth_service: AuthService,
    cen: ContextEngine,
):
    return {"context": await cen.get("file_upload")}
