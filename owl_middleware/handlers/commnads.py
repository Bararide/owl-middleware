from datetime import datetime
from aiogram import types
from aiogram.enums import ParseMode

from fastbot.decorators import (
    with_auto_reply,
    with_context,
    with_parse_mode,
    with_template_engine,
)
from fastbot.engine import TemplateEngine, ContextEngine

from models import User
from services import AuthService


@with_template_engine
@with_auto_reply("commands/start.j2", buttons_template="buttons/start_menu_buttons.j2")
async def cmd_start(
    message: types.Message,
    user: User,
    ten: TemplateEngine,
    cen: ContextEngine,
):
    pass


@with_template_engine
@with_auto_reply("commands/register.j2")
@with_parse_mode(ParseMode.HTML)
async def cmd_register(
    message: types.Message,
    ten: TemplateEngine,
    auth_service: AuthService,
    cen: ContextEngine,
):
    user = message.from_user
    result = await auth_service.register_user(
        {
            "id": user.id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "registered_at": datetime.now().isoformat(),
        }
    )

    if result.is_ok():
        return {
            "context": await cen.get("registration", user=result.unwrap(), success=True)
        }
    else:
        return {"context": await cen.get("registration_error", error=str(result.err()))}
