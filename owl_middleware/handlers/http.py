from datetime import datetime
from aiogram.enums import ParseMode
from fastapi import APIRouter, Request

from fastbot.engine import ContextEngine
from fastbot.engine import TemplateEngine
from fastbot.logger import Logger
from models import User
from services import AuthService, FileService, ApiService, ContainerService, TextService
from fastbot.decorators import (
    with_template_engine,
    with_parse_mode,
    with_auto_reply,
)

from fastbot.decorators import inject

http_router = APIRouter()


@http_router.get("/")
async def health_check(request: Request):
    return {"status": "ok", "service": "bot"}
