from models import User
from fastbot.decorators import register_context


@register_context("start")
async def start_context(user: User):
    return {"user": user, "welcome_message": f"Добро пожаловать, {user.first_name}!"}
