from datetime import datetime
from typing import Any
from aiogram import types
from aiogram.enums import ParseMode

from aiogram.utils.keyboard import InlineKeyboardBuilder

from fastbot.engine import ContextEngine
from fastbot.engine import TemplateEngine
from fastbot.logger import Logger
from models import User, File
from services import AuthService, FileService
from celery.result import AsyncResult
from fastbot.decorators import (
    with_template_engine,
    with_parse_mode,
    with_auto_reply,
)


@with_template_engine
@with_parse_mode(ParseMode.HTML)
@with_auto_reply("filters/file_list.j2")
async def callback_file_list(
    callback: types.CallbackQuery,
    user: User,
    ten: TemplateEngine,
    file_service: FileService,
    auth_service: AuthService,
    cen: ContextEngine,
):
    return {
        "context": await cen.get(
            "file_list", files=await file_service.get_files_by_user(user)
        )
    }
