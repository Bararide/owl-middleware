import asyncio

from aiogram import types
from aiogram.enums import ParseMode

from fastbot.engine import ContextEngine
from fastbot.engine import TemplateEngine
from fastbot.logger import Logger
from models import User
from services import AuthService, FileService, ContainerService, State
from fastbot.decorators import (
    with_template_engine,
    with_parse_mode,
    with_auto_reply,
)


@with_template_engine
@with_parse_mode(ParseMode.HTML)
@with_auto_reply("filters/choose_container_filter.j2")
async def handle_choose_container_callback(
    callback: types.CallbackQuery,
    user: User,
    state_service: State,
    ten: TemplateEngine,
    container_service: ContainerService,
    cen: ContextEngine,
):
    await callback.answer()

    container_id = callback.data.replace("container_", "")

    try:
        container_result = await container_service.get_container(str(container_id))

        if container_result.is_err():
            return {
                "context": await cen.get(
                    "choose_container_filter", error="Контейнер не найден"
                )
            }

        container = container_result.unwrap()

        if container.user_id != str(user.tg_id):
            return {
                "context": await cen.get(
                    "choose_container_filter",
                    error="У вас нет доступа к этому контейнеру",
                )
            }

        state_service.set_work_container(str(user.tg_id), str(container.id))

        context = await cen.get(
            "choose_container_filter", container=container, success=True
        )

        await callback.message.edit_text(
            f"✅ <b>Контейнер выбран:</b> {container.id}\n",
            parse_mode="HTML",
        )

        await asyncio.sleep(2)

        try:
            await callback.message.pin(disable_notification=True)
        except Exception as pin_error:
            Logger.warning(f"Не удалось закрепить сообщение: {pin_error}")
            await callback.message.reply("⚠️ Не удалось закрепить сообщение")

        return {
            "context": await cen.get(
                "choose_container_filter", container=container, success=True
            )
        }

    except Exception as e:
        Logger.error(f"Error in handle_choose_container_callback: {e}")
        return {
            "context": await cen.get(
                "choose_container_filter",
                error=f"Ошибка при выборе контейнера: {str(e)}",
            )
        }
