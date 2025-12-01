from aiogram import types
from aiogram.enums import ParseMode

from fastbot.engine import ContextEngine
from fastbot.engine import TemplateEngine
from fastbot.logger import Logger
from models import User
from services import AuthService, FileService, ContainerService, ApiService, State
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
    state_service: State,
    ten: TemplateEngine,
    cen: ContextEngine,
    file_service: FileService,
    api_service: ApiService,
):
    try:
        await callback.answer()

        callback_data = callback.data

        if not callback_data.startswith("file_"):
            return {
                "context": await cen.get(
                    "read_file", error="Неверный формат callback_data"
                )
            }

        parts = callback_data[5:].split("_")

        if len(parts) < 2:
            return {
                "context": await cen.get("read_file", error="Неверный формат данных")
            }

        search_id = parts[0]
        try:
            file_index = int(parts[1])
        except ValueError:
            return {
                "context": await cen.get("read_file", error="Неверный индекс файла")
            }

        file_path = state_service.get_file_path(str(user.tg_id), search_id, file_index)

        if not file_path:
            return {
                "context": await cen.get(
                    "read_file", error="Файл не найден или результаты поиска устарели"
                )
            }

        read_result = await api_service.read_file(file_path)

        if read_result.is_err():
            error = read_result.unwrap_err()
            Logger.error(f"Read file error for path {file_path}: {error}")
            return {
                "context": await cen.get(
                    "read_file", error=f"Ошибка чтения файла: {error}"
                )
            }

        file_data = read_result.unwrap()

        return {
            "context": await cen.get(
                "read_file",
                path=file_data.get("path", file_path),
                content=file_data.get("content", ""),
                size=file_data.get("size", 0),
            )
        }

    except Exception as e:
        Logger.error(f"Error in handle_read_file_callback: {e}")
        return {
            "context": await cen.get(
                "read_file",
                error=f"Ошибка при чтении файла: {str(e)}",
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
