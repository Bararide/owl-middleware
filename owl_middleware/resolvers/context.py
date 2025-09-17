from models import User
from fastbot.decorators import register_context


@register_context("start")
async def start_context(user: User):
    return {"user": user, "welcome_message": f"Добро пожаловать, {user.first_name}!"}


@register_context("registration_error")
async def registration_error_context(error: str):
    return {"error": error, "has_access": False, "success": False}


@register_context("registration")
async def registration_context(user: User, success: bool):
    return {
        "success": success,
        "user": user,
        "message": "Регистрация прошла успешно!" if success else "Ошибка регистрации",
    }


@register_context("file_list")
async def file_list_context(files: list):
    return {"files": files}
