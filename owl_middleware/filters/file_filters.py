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
    callback_query: types.CallbackQuery,
    user: User,
    ten: TemplateEngine,
    cen: ContextEngine,
):
    await callback_query.answer()

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
    containers = container_service.get_containers_by_user_id(user.id)
    return {
        "context": await cen.get(
            "file_list",
            files=[
                await file_service.get_files_by_container(container)
                for container in containers
            ],
        )
    }


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
