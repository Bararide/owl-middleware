from datetime import datetime
from aiogram.enums import ParseMode
from aiogram.types import Message

from fastbot.engine import ContextEngine
from fastbot.engine import TemplateEngine
from fastbot.logger import Logger
from models import User
from services import AuthService, FileService, ApiService
from fastbot.decorators import (
    with_template_engine,
    with_parse_mode,
    with_auto_reply,
)


@with_template_engine
@with_parse_mode(ParseMode.HTML)
@with_auto_reply("filters/file_upload.j2")
async def handle_file_upload(
    message: Message,
    user: User,
    ten: TemplateEngine,
    file_service: FileService,
    auth_service: AuthService,
    api_service: ApiService,
    cen: ContextEngine,
):
    if not message.document:
        return {
            "context": await cen.get("file_upload", error="Please send a document file")
        }

    document = message.document
    file_data = {
        "id": document.file_id,
        "name": document.file_name or f"file_{document.file_id}",
        "size": document.file_size,
        "user_id": user.id,
        "user": user,
        "created_at": datetime.now(),
        "mime_type": document.mime_type or "application/octet-stream",
    }

    db_result = await file_service.create_file(file_data)

    if db_result.is_err():
        error = db_result.unwrap_err()
        Logger.error(f"Error creating file in DB: {error}")
        return {
            "context": await cen.get("file_upload", error=f"Database error: {error}")
        }

    file = db_result.unwrap()

    try:
        file_info = await message.bot.get_file(document.file_id)

        file_content = await message.bot.download_file(file_info.file_path)
        content_text = file_content.read().decode("utf-8", errors="ignore")

        api_result = await api_service.create_file(
            path=f"/{file.id}_{file.name}", content=content_text
        )

        if api_result.is_err():
            Logger.info(f"File content: {content_text}")
            await file_service.delete_file(file.id)
            error = api_result.unwrap_err()
            Logger.error(f"Error uploading to C++ service: {error}")
            return {
                "context": await cen.get("file_upload", error=f"Storage error: {error}")
            }

        return {"context": await cen.get("file_upload", success=True, file=file)}

    except Exception as e:
        await file_service.delete_file(file.id)
        Logger.error(f"Error processing file upload: {e}")
        return {"context": await cen.get("file_upload", error=f"Processing error: {e}")}


@with_template_engine
@with_parse_mode(ParseMode.HTML)
@with_auto_reply("commands/semantic_search.j2")
async def handle_search(
    message: Message,
    user: User,
    ten: TemplateEngine,
    file_service: FileService,
    auth_service: AuthService,
    api_service: ApiService,
    cen: ContextEngine,
):
    query = message.text.strip()

    if not query:
        return {
            "context": await cen.get(
                "semantic_search", error="Please provide a search query"
            )
        }

    search_result = await api_service.semantic_search(query, limit=10)

    if search_result.is_err():
        error = search_result.unwrap_err()
        Logger.error(f"Semantic search error: {error}")
        return {
            "context": await cen.get("semantic_search", error=f"Search error: {error}")
        }

    search_data = search_result.unwrap()
    results = search_data.get("results", [])

    return {
        "context": await cen.get(
            "semantic_search", query=query, results=results, count=len(results)
        )
    }


@with_template_engine
@with_parse_mode(ParseMode.HTML)
@with_auto_reply("commands/read_file.j2")
async def handle_read_file(
    message: Message,
    user: User,
    ten: TemplateEngine,
    file_service: FileService,
    api_service: ApiService,
    cen: ContextEngine,
):
    args = message.text.split()[1:]
    if not args:
        return {
            "context": await cen.get(
                "read_file", error="Please provide file path or ID"
            )
        }

    file_identifier = args[0]

    file_result = await file_service.get_file(file_identifier)
    if file_result.is_ok() and file_result.unwrap():
        file = file_result.unwrap()
        path = f"/{file.id}_{file.name}"
    else:
        path = file_identifier

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


@with_template_engine
@with_parse_mode(ParseMode.HTML)
@with_auto_reply("commands/rebuild_index.j2")
async def handle_rebuild_index(
    message: Message,
    user: User,
    ten: TemplateEngine,
    api_service: ApiService,
    cen: ContextEngine,
):
    if not user.is_admin:
        return {
            "context": await cen.get("rebuild_index", error="Insufficient permissions")
        }

    rebuild_result = await api_service.rebuild_index()

    if rebuild_result.is_err():
        error = rebuild_result.unwrap_err()
        Logger.error(f"Rebuild index error: {error}")
        return {
            "context": await cen.get("rebuild_index", error=f"Rebuild error: {error}")
        }

    rebuild_data = rebuild_result.unwrap()

    return {
        "context": await cen.get(
            "rebuild_index",
            message=rebuild_data.get("message", "Index rebuilt successfully"),
        )
    }


@with_template_engine
@with_parse_mode(ParseMode.HTML)
@with_auto_reply("commands/health_check.j2")
async def handle_health_check(
    message: Message,
    user: User,
    ten: TemplateEngine,
    api_service: ApiService,
    cen: ContextEngine,
):
    health_result = await api_service.health_check()

    if health_result.is_err():
        error = health_result.unwrap_err()
        Logger.error(f"Health check error: {error}")
        return {
            "context": await cen.get("health_check", status="offline", error=str(error))
        }

    is_healthy = health_result.unwrap()

    return {
        "context": await cen.get(
            "health_check",
            status="online" if is_healthy else "offline",
            message=(
                "C++ service is operational" if is_healthy else "C++ service is down"
            ),
        )
    }


@with_template_engine
@with_parse_mode(ParseMode.HTML)
@with_auto_reply("commands/list_files.j2")
async def handle_list_files(
    message: Message,
    user: User,
    ten: TemplateEngine,
    file_service: FileService,
    api_service: ApiService,
    cen: ContextEngine,
):
    files_result = await file_service.get_files_by_user(user)

    if files_result.is_err():
        error = files_result.unwrap_err()
        Logger.error(f"List files error: {error}")
        return {
            "context": await cen.get("list_files", error=f"Database error: {error}")
        }

    files = files_result.unwrap()

    files_info = []
    for file in files:
        path = f"/{file.id}_{file.name}"
        read_result = await api_service.read_file(path)

        if read_result.is_ok():
            file_data = read_result.unwrap()
            files_info.append(
                {
                    "id": file.id,
                    "name": file.name,
                    "path": file_data.get("path", path),
                    "size": file_data.get("size", 0),
                    "db_size": file.size,
                    "created_at": file.created_at,
                }
            )
        else:
            files_info.append(
                {
                    "id": file.id,
                    "name": file.name,
                    "path": path,
                    "size": "N/A",
                    "db_size": file.size,
                    "created_at": file.created_at,
                    "error": "Not found in storage",
                }
            )

    return {
        "context": await cen.get("list_files", files=files_info, count=len(files_info))
    }


@with_template_engine
@with_parse_mode(ParseMode.HTML)
@with_auto_reply("commands/delete_file.j2")
async def handle_delete_file(
    message: Message,
    user: User,
    ten: TemplateEngine,
    file_service: FileService,
    api_service: ApiService,
    cen: ContextEngine,
):
    args = message.text.split()[1:]
    if not args:
        return {"context": await cen.get("delete_file", error="Please provide file ID")}

    file_id = args[0]

    file_result = await file_service.get_file(file_id)
    if file_result.is_err() or not file_result.unwrap():
        return {
            "context": await cen.get("delete_file", error="File not found in database")
        }

    file = file_result.unwrap()

    if file.user_id != user.id and not user.is_admin:
        return {"context": await cen.get("delete_file", error="Access denied")}

    delete_result = await file_service.delete_file(file_id)

    if delete_result.is_err():
        error = delete_result.unwrap_err()
        Logger.error(f"Delete file error: {error}")
        return {"context": await cen.get("delete_file", error=f"Delete error: {error}")}

    return {
        "context": await cen.get(
            "delete_file", success=True, file_id=file_id, file_name=file.name
        )
    }


@with_template_engine
@with_parse_mode(ParseMode.HTML)
async def handle_service_status(
    message: Message,
    user: User,
    ten: TemplateEngine,
    api_service: ApiService,
    cen: ContextEngine,
):
    """Команда для проверки статуса C++ сервиса"""
    if not user.is_admin:
        return await message.answer("❌ Insufficient permissions")

    health_result = await api_service.health_check()
    root_result = await api_service.get_root()

    status_text = "<b>C++ Service Status</b>\n\n"

    if health_result.is_ok() and health_result.unwrap():
        status_text += "✅ <b>Status:</b> Online\n"

        if root_result.is_ok():
            root_data = root_result.unwrap()
            status_text += (
                f"📊 <b>Message:</b> {root_data.get('message', 'No message')}\n"
            )
        else:
            status_text += "⚠️ <b>Root endpoint:</b> Error\n"
    else:
        status_text += "❌ <b>Status:</b> Offline\n"
        if health_result.is_err():
            status_text += f"🔴 <b>Error:</b> {health_result.unwrap_err()}\n"

    await message.answer(status_text, parse_mode=ParseMode.HTML)
