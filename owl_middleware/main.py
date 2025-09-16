import asyncio
from os import getenv
from dotenv import load_dotenv

from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F, Router
from aiogram.fsm.storage.memory import MemoryStorage
from fastapi import WebSocket

from fastbot.engine import TemplateEngine
from fastbot.engine import ContextEngine

from fastbot import FastBotBuilder, MiniAppConfig
from fastbot.logger import Logger

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
        template_dirs=["templates", "src/owl_middleware/templates"]
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

    bot_builder = (
        FastBotBuilder()
        .set_bot(Bot(token=getenv("BOT_TOKEN")))
        .set_dispatcher(Dispatcher(storage=storage))
        .add_mini_app(mini_app_config)
    )

    bot_builder.add_dependency(template_service)
    bot_builder.add_dependency(context_service)

    bot = bot_builder.build()

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
