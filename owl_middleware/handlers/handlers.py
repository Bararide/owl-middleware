from datetime import datetime
from aiogram.enums import ParseMode
from aiogram.types import Message

from fastbot.engine import ContextEngine
from fastbot.engine import TemplateEngine
from fastbot.logger import Logger
from models import User
from services import AuthService, FileService
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
        "created_at": datetime.now(),
        "mime_type": document.mime_type or "application/octet-stream",
    }

    result = await file_service.create_file(file_data)

    if result.is_ok():
        file = result.unwrap()
        return {"context": await cen.get("file_upload", success=True, file=file)}
    else:
        error = result.unwrap_err()
        Logger.error(f"Error uploading file: {error}")
        return {"context": await cen.get("file_upload", error=str(error))}
