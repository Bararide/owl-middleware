from datetime import datetime
from aiogram import types
from aiogram.enums import ParseMode

from fastbot.engine import ContextEngine
from fastbot.engine import TemplateEngine
from fastbot.logger import Logger
from models import User
from services import AuthService, FileService, ContainerService, ApiService, State
from fastbot.decorators import (
    with_template_engine,
    with_parse_mode,
    with_auto_reply,
)

import base64
import html
import fitz


@with_template_engine
@with_parse_mode(ParseMode.HTML)
@with_auto_reply("commands/read_file_impl.j2")
async def handle_read_file_callback(
    callback: types.CallbackQuery,
    user: User,
    state_service: State,
    ten: TemplateEngine,
    cen: ContextEngine,
    api_service: ApiService,
):
    try:
        await callback.answer()

        callback_data = callback.data

        if not callback_data.startswith("file_"):
            return {
                "context": await cen.get(
                    "read_file", error="Неверный формат callback_data"
                )
            }

        parts = callback_data[5:].split("_")

        if len(parts) < 2:
            return {
                "context": await cen.get("read_file", error="Неверный формат данных")
            }

        search_id = parts[0]
        try:
            file_index = int(parts[1])
        except ValueError:
            return {
                "context": await cen.get("read_file", error="Неверный индекс файла")
            }

        file_path = state_service.get_file_path(str(user.tg_id), search_id, file_index)

        if not file_path:
            return {
                "context": await cen.get(
                    "read_file", error="Файл не найден или результаты поиска устарели"
                )
            }

        file_id = file_path
        if file_path.startswith("/"):
            file_id = file_path[1:]

        container_id = state_service.get_work_container(str(user.tg_id))

        if not container_id:
            return {
                "context": await cen.get(
                    "read_file", error="Сначала выберите контейнер для работы"
                )
            }

        content_result = await api_service.get_file_content(
            str(file_id), str(container_id)
        )

        if content_result.is_err():
            error = content_result.unwrap_err()
            Logger.error(f"Error read file: {error}")
            return {
                "context": await cen.get(
                    "read_file", error=f"Ошибка чтения файла: {error}"
                )
            }

        content = content_result.unwrap()

        def is_base64_encoded(s):
            try:
                if len(s) > 100 and all(
                    c
                    in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/="
                    for c in s[:100]
                ):
                    decoded = base64.b64decode(s[:100])
                    return True
                return False
            except:
                return False

        if content.startswith("%PDF-") or (
            is_base64_encoded(content)
            and base64.b64decode(content[:20]).startswith(b"%PDF-")
        ):
            try:
                if is_base64_encoded(content):
                    pdf_bytes = base64.b64decode(content)
                else:
                    pdf_bytes = content.encode("latin-1")

                pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")

                extracted_text = ""
                for page_num in range(pdf_document.page_count):
                    page = pdf_document.load_page(page_num)
                    page_text = page.get_text()
                    if page_text:
                        extracted_text += page_text + "\n\n"

                pdf_document.close()

                if extracted_text.strip():
                    content = html.escape(extracted_text.strip())

                    max_length = 3000
                    if len(content) > max_length:
                        content = content[:max_length] + "\n\n... (текст обрезан)"

                    return {
                        "context": await cen.get(
                            "read_file_impl",
                            content=content,
                            truncated=len(extracted_text) > max_length,
                            error="0",
                            is_pdf=True,
                        )
                    }
                else:
                    return {
                        "context": await cen.get(
                            "read_file_impl",
                            content="",
                            truncated="",
                            error="PDF файл не содержит извлекаемого текста (возможно, это сканированное изображение)",
                            is_pdf=True,
                        )
                    }

            except Exception as e:
                Logger.error(f"PDF extraction error: {e}")
                return {
                    "context": await cen.get(
                        "read_file_impl",
                        content="",
                        truncated="",
                        error=f"Ошибка извлечения текста из PDF: {str(e)}",
                        is_pdf=True,
                    )
                }

        content = html.escape(content)

        max_length = 3000
        if len(content) > max_length:
            content = content[:max_length] + "\n\n... (сообщение обрезано)"

        return {
            "context": await cen.get(
                "read_file_impl",
                content=content,
                truncated=len(content_result.unwrap()) > max_length,
                error="",
                is_pdf=False,
            )
        }

    except Exception as e:
        Logger.error(f"Error in handle_read_file_callback: {e}")
        return {
            "context": await cen.get(
                "read_file",
                error=f"Ошибка при чтении файла: {str(e)}",
            )
        }


@with_template_engine
@with_parse_mode(ParseMode.HTML)
@with_auto_reply("filters/create_container_help.j2")
async def handle_create_container_callback(
    callback: types.CallbackQuery,
    user: User,
    ten: TemplateEngine,
    cen: ContextEngine,
):
    await callback.answer()

    return {"context": await cen.get("create_container_help", user_id=user.tg_id)}


@with_template_engine
@with_parse_mode(ParseMode.HTML)
@with_auto_reply("filters/file_list.j2")
async def callback_file_list(
    callback: types.CallbackQuery,
    user: User,
    ten: TemplateEngine,
    file_service: FileService,
    auth_service: AuthService,
    container_service: ContainerService,
    cen: ContextEngine,
):
    containers_result = await container_service.get_containers_by_user_id(
        str(user.tg_id)
    )

    if containers_result.is_err():
        return {
            "context": await cen.get(
                "file_list", error="Ошибка при получении контейнеров"
            )
        }

    containers = containers_result.unwrap()

    all_files = []
    for container in containers:
        files_result = await file_service.get_files_by_container(container.id)
        if files_result.is_ok():
            all_files.extend(files_result.unwrap())

    return {"context": await cen.get("file_list", files=all_files)}


@with_template_engine
@with_parse_mode(ParseMode.HTML)
@with_auto_reply("filters/ocr_save.j2")
async def callback_ocr_file_filter(
    callback: types.CallbackQuery,
    user: User,
    state_service: State,
    ten: TemplateEngine,
    cen: ContextEngine,
    api_service: ApiService,
):
    try:
        await callback.answer()

        state = state_service.get_state(str(user.tg_id))
        ocr_data = state.metadata.get("last_ocr_result")

        if not ocr_data:
            return {
                "context": await cen.get(
                    "ocr_save",
                    error="Данные OCR не найдены. Пожалуйста, отправьте новое фото.",
                )
            }

        container_id = ocr_data.get("container_id") or state_service.get_work_container(
            str(user.tg_id)
        )

        if not container_id:
            return {
                "context": await cen.get(
                    "ocr_save",
                    error="Контейнер не выбран. Сначала выберите контейнер командой /container.",
                )
            }

        file_name = f"ocr_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

        result = await api_service.create_file(
            path=file_name,
            content=ocr_data["text"],
            user_id=str(user.id),
            container_id=container_id,
        )

        if result.is_err():
            error = result.unwrap_err()
            Logger.error(f"Error saving OCR result: {error}")
            return {
                "context": await cen.get(
                    "ocr_save", error=f"Ошибка сохранения: {error}"
                )
            }

        if "last_ocr_result" in state.metadata:
            del state.metadata["last_ocr_result"]
        if "last_ocr_photo" in state.metadata:
            del state.metadata["last_ocr_photo"]

        return {
            "context": await cen.get(
                "ocr_save",
                file_name=file_name,
                characters_count=len(ocr_data["text"]),
                container_id=container_id,
            )
        }

    except Exception as e:
        Logger.error(f"Error in handle_ocr_save_callback: {e}")
        return {
            "context": await cen.get("ocr_save", error=f"Ошибка сохранения: {str(e)}")
        }


@with_template_engine
@with_parse_mode(ParseMode.HTML)
@with_auto_reply("filters/file_upload.j2")
async def callback_file_upload(
    callback: types.CallbackQuery,
    user: User,
    ten: TemplateEngine,
    file_service: FileService,
    auth_service: AuthService,
    cen: ContextEngine,
):
    return {"context": await cen.get("file_upload")}
