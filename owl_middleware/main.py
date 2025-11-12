import sys

sys.path.append(".")

import asyncio
from os import getenv
from dotenv import load_dotenv

from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F
from aiogram.fsm.storage.memory import MemoryStorage
from fastapi import WebSocket

from fastbot.engine import ContextEngine
from fastbot.engine import TemplateEngine

from fastbot import FastBotBuilder, MiniAppConfig
from fastbot.logger import Logger

from fastapi import APIRouter

import services
import models
import resolvers
import middleware
import handlers
import filters

load_dotenv()


async def handle_webhook(data: dict):
    Logger.info(f"Received webhook data: {data}")
    return {"status": "ok"}


async def websocket_handler(websocket: WebSocket):
    await websocket.accept()
    while True:
        data = await websocket.receive_text()
        Logger.info(f"WS received: {data}")
        await websocket.send_text(f"Echo: {data}")


async def main() -> None:
    storage = MemoryStorage()

    template_service = TemplateEngine(
        template_dirs=["templates", "owl_middleware/templates"]
    )
    context_service = ContextEngine()

    mini_app_config = MiniAppConfig(
        title="",
        description="Telegram Mini App with FastAPI",
        static_dir="static",
        webhook_path="/webhook",
        webhook_handler=handle_webhook,
        ws_handler=websocket_handler,
    )

    jwt_secret = getenv("JWT_SECRET", "fallback-secret-change-in-production")

    database_service = services.DBService(getenv("MONGO_URI"), getenv("DATABASE_NAME"))
    api_service = services.ApiService(getenv("VFS_HTTP_PATH"))
    auth_service = services.AuthService(database_service, jwt_secret)
    file_service = services.FileService(database_service, api_service)
    container_service = services.ContainerService(database_service, api_service)
    text_service = services.TextService(getenv("MAX_FILE_SIZE"))
    auth_middleware = middleware.AuthMiddleware(auth_service)

    bot_builder = (
        FastBotBuilder()
        .set_bot(Bot(token=getenv("BOT_TOKEN")))
        .set_dispatcher(Dispatcher(storage=storage))
        .add_middleware(middleware.error_handling_middleware)
        .add_middleware(middleware.logger_middleware)
        .add_mini_app(mini_app_config)
    )

    bot_builder.add_dependency("db", database_service)
    bot_builder.add_dependency("auth_service", auth_service)
    bot_builder.add_dependency("auth_middleware", auth_middleware)
    bot_builder.add_dependency("api_service", api_service)
    bot_builder.add_dependency("file_service", file_service)
    bot_builder.add_dependency("template_engine", template_service)
    bot_builder.add_dependency("context_engine", context_service)
    bot_builder.add_dependency("container_service", container_service)
    bot_builder.add_dependency("text_service", text_service)

    bot_builder.add_dependency_resolver(models.User, resolvers.resolve_user)
    bot_builder.add_dependency_resolver(models.File, resolvers.resolve_file)

    await bot_builder.add_contexts(
        [
            resolvers.start_context,
            resolvers.registration_context,
            resolvers.file_list_context,
            resolvers.file_upload_context,
            resolvers.semantic_search_context,
            resolvers.service_status_context,
            resolvers.file_info_context,
            resolvers.search_result_context,
            resolvers.api_error_context,
            resolvers.storage_stats_context,
            resolvers.registration_error_context,
            resolvers.delete_file_context,
            resolvers.read_file_context,
            resolvers.rebuild_index_context,
            resolvers.health_check_context,
            resolvers.list_files_context,
            resolvers.create_container_context,
            resolvers.create_container_help_context,
            resolvers.read_file_impl_context,
            resolvers.download_selection_context,
            resolvers.download_file_context,
            resolvers.file_preview_context,
            resolvers.get_token_context,
        ]
    )

    command_handlers = [
        ("start", handlers.cmd_start, "Начать взаимодействие с ботом"),
        ("register", handlers.cmd_register, "Зарегистрироваться в системе"),
        ("upload", handlers.handle_file_upload, "Загрузить файл"),
        ("search", handlers.handle_search, "Семантический поиск"),
        ("read", handlers.handle_read_file_impl, "Прочитать файл"),
        ("rebuild_index", handlers.handle_rebuild_index, "Перестроить индекс"),
        ("health", handlers.handle_health_check, "Проверить состояние сервиса"),
        ("list", handlers.handle_list_files, "Список загруженных файлов"),
        ("delete", handlers.handle_delete_file, "Удалить файл"),
        ("status", handlers.handle_service_status, "Статус сервиса"),
        ("container", handlers.handle_create_container, "Создание контейнера"),
        ("download", handlers.handle_download_file, "Скачать файл"),
        ("web", handlers.handle_get_token, "Получить токен для web"),
    ]

    for cmd, handler, desc in command_handlers:
        await bot_builder.add_command_handler(cmd, handler, desc)

    await bot_builder.add_callback_query_handler(
        filters.callback_file_list, F.data.contains("file_list")
    )

    await bot_builder.add_callback_query_handler(
        filters.callback_file_upload, F.data.contains("file_upload")
    )

    await bot_builder.add_callback_query_handler(
        filters.handle_create_container_callback, F.data.contains("create_container")
    )

    await bot_builder.add_handler(handlers.handle_file_upload, F.document)

    bot_builder.add_http_router(handlers.http_router)

    bot = bot_builder.build()

    bot.app.state.db = database_service
    bot.app.state.auth_service = auth_service
    bot.app.state.auth_middleware = auth_middleware
    bot.app.state.api_service = api_service
    bot.app.state.file_service = file_service
    bot.app.state.template_service = template_service
    bot.app.state.context_service = context_service
    bot.app.state.container_service = container_service
    bot.app.state.text_service = text_service
    bot.app.state.user_resolver = resolvers.resolve_user

    use_webhook = getenv("USE_WEBHOOK", "").lower() == "true"

    if use_webhook:
        webhook_url = f"https://{getenv('WEBAPP_DOMAIN')}/webhook"
        await bot.start_with_webhook(webhook_url)
    else:
        tasks = [bot.start_polling()]
        if bot.app:
            port = int(getenv("PORT", "8000"))
            tasks.append(bot.run_web_server(port))
        await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
