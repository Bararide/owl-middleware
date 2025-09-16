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


@with_template_engine
@with_auto_reply("commands/start.j2", buttons_template="buttons/start_menu_buttons.j2")
async def cmd_start(
    message: types.Message,
    user: User,
    ten: TemplateEngine,
    cen: ContextEngine,
):
    pass
