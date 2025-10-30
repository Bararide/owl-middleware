from aiogram import types
from aiogram.enums import ParseMode

from fastbot.engine import ContextEngine
from fastbot.engine import TemplateEngine
from models import User
from services import AuthService, FileService, ContainerService
from fastbot.decorators import (
    with_template_engine,
    with_parse_mode,
    with_auto_reply,
)


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

    return {"context": await cen.get("create_container_help", user_id=user.id)}


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
    containers_result = await container_service.get_containers_by_user_id(str(user.id))

    if containers_result.is_err():
        return {
            "context": await cen.get(
                "file_list", error="Ошибка при получении контейнеров"
            )
        }

    containers = containers_result.unwrap()

    all_files = []
    for container in containers:
        files_result = await file_service.get_files_by_container(container)
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
