from datetime import datetime
from aiogram.enums import ParseMode
from aiogram.types import Message

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

from aiogram.types import BufferedInputFile

import fitz
import base64


@with_template_engine
@with_parse_mode(ParseMode.HTML)
@with_auto_reply("commands/download_file.j2")
async def handle_download_file(
    message: Message,
    user: User,
    ten: TemplateEngine,
    file_service: FileService,
    api_service: ApiService,
    container_service: ContainerService,
    cen: ContextEngine,
):
    args = message.text.split()[1:]

    if not args:
        containers_result = await container_service.get_containers_by_user_id(
            str(user.id)
        )

        if containers_result.is_err():
            return {
                "context": await cen.get(
                    "download_file", error="Ошибка при получении контейнеров"
                )
            }

        containers = containers_result.unwrap()

        if not containers:
            return {
                "context": await cen.get(
                    "download_file",
                    error="У вас нет контейнеров. Сначала создайте контейнер командой /container",
                )
            }

        all_files = []
        for container in containers:
            files_result = await file_service.get_files_by_container(container.id)
            if files_result.is_ok():
                container_files = files_result.unwrap()
                for file in container_files:
                    file.container_name = container.id
                all_files.extend(container_files)

        if not all_files:
            return {
                "context": await cen.get(
                    "download_file",
                    error="У вас нет загруженных файлов. Сначала загрузите файлы с помощью команды /upload",
                )
            }

        return {
            "context": await cen.get(
                "download_file", files=all_files, files_count=len(all_files)
            )
        }

    if len(args) >= 2:
        file_id = args[0]
        container_id = args[1]

        Logger.info(f"Downloading file: {file_id} from container: {container_id}")

        content_result = await api_service.get_file_content(
            str(file_id), str(container_id)
        )

        if content_result.is_err():
            error = content_result.unwrap_err()
            Logger.error(f"Download file error: {error}")
            return {
                "context": await cen.get(
                    "download_file", error=f"Ошибка при чтении файла: {error}"
                )
            }

        content = content_result.unwrap()

        if not content:
            return {
                "context": await cen.get(
                    "download_file", error="Файл пуст или не содержит данных"
                )
            }

        try:
            try:
                binary_content = base64.b64decode(content)
                file_data_to_send = binary_content
                is_binary = True
                filename = f"file_{file_id}.bin"
            except:
                file_data_to_send = content.encode("utf-8")
                is_binary = False
                filename = f"file_{file_id}.txt"

            file_to_send = BufferedInputFile(file_data_to_send, filename=filename)

            await message.answer_document(
                document=file_to_send,
                caption=f"📎 Файл из контейнера {container_id}\n"
                f"📊 Размер: {len(file_data_to_send)} байт\n"
                f"🔧 Тип: {'Бинарный' if is_binary else 'Текстовый'}",
            )

            Logger.info(
                f"File downloaded successfully: {file_id} from container {container_id} by user {user.id}"
            )

            return {
                "context": await cen.get(
                    "download_file",
                    success=True,
                    filename=filename,
                    size=len(file_data_to_send),
                    container_id=container_id,
                )
            }

        except Exception as e:
            Logger.error(f"Error creating/downloading file: {e}")
            return {
                "context": await cen.get(
                    "download_file",
                    error=f"Ошибка при создании файла для скачивания: {str(e)}",
                )
            }
    else:
        return {
            "context": await cen.get(
                "download_file",
                error="Использование: /download_file <file_id> <container_id>\nПример: /download_file file123 dev_env",
            )
        }


@with_template_engine
@with_parse_mode(ParseMode.HTML)
@with_auto_reply("commands/create_container.j2")
async def handle_create_container(
    message: Message,
    user: User,
    ten: TemplateEngine,
    container_service: ContainerService,
    auth_service: AuthService,
    api_service: ApiService,
    cen: ContextEngine,
):
    args = message.text.split()[1:]

    if not args:
        return {
            "context": await cen.get(
                "create_container",
                error="Использование: /create_container <container_id> [memory_limit] [storage_quota] [file_limit]",
            )
        }

    container_id = args[0]

    memory_limit = int(args[1]) if len(args) > 1 else 512
    storage_quota = int(args[2]) if len(args) > 2 else 1024
    file_limit = int(args[3]) if len(args) > 3 else 10

    if memory_limit <= 0 or storage_quota <= 0 or file_limit <= 0:
        return {
            "context": await cen.get(
                "create_container",
                error="Все лимиты должны быть положительными числами",
            )
        }

    if memory_limit > 4096:
        return {
            "context": await cen.get(
                "create_container", error="Лимит памяти не может превышать 4096 MB"
            )
        }

    if storage_quota > 10240:
        return {
            "context": await cen.get(
                "create_container", error="Лимит хранилища не может превышать 10240 MB"
            )
        }

    container_data = {
        "user_id": str(user.id),
        "container_id": container_id,
        "memory_limit": memory_limit,
        "storage_quota": storage_quota,
        "file_limit": file_limit,
        "env_label": {"key": "environment", "value": "development"},
        "type_label": {"key": "type", "value": "workspace"},
        "commands": ["search", "debug", "all", "create"],
        "privileged": False,
    }

    try:
        db_result = await container_service.create_container(container_data)

        if db_result.is_err():
            error = db_result.unwrap_err()
            Logger.error(f"Error creating container in DB: {error}")
            return {
                "context": await cen.get(
                    "create_container", error=f"Ошибка базы данных: {error}"
                )
            }

        container = db_result.unwrap()

        api_result = await api_service.create_container(
            user_id=str(user.id),
            container_id=container_id,
            tariff=container.tariff,
            env_label=container.env_label,
            type_label=container.type_label,
            commands=container.commands,
            privileged=container.privileged,
        )

        if api_result.is_err():
            await container_service.delete_container(container_id)
            error = api_result.unwrap_err()
            Logger.error(f"Error creating container in C++ service: {error}")
            return {
                "context": await cen.get(
                    "create_container", error=f"Ошибка сервиса контейнеров: {error}"
                )
            }

        limits_result = await container_service.check_container_limits(container_id)
        limits = limits_result.unwrap() if limits_result.is_ok() else {}

        Logger.info(
            f"Container created successfully: {container_id} for user {user.id}"
        )

        return {
            "context": await cen.get(
                "create_container",
                success=True,
                container_id=container_id,
                user_id=str(user.id),
                container=container,
                limits=limits,
            )
        }

    except Exception as e:
        Logger.error(f"Unexpected error in create_container: {e}")
        return {
            "context": await cen.get(
                "create_container", error=f"Неожиданная ошибка: {str(e)}"
            )
        }


@with_template_engine
@with_parse_mode(ParseMode.HTML)
@with_auto_reply("filters/select_container.j2")
async def handle_select_container(
    message: Message,
    user: User,
    ten: TemplateEngine,
    container_service: ContainerService,
    cen: ContextEngine,
):
    containers_result = await container_service.get_containers_by_user_id(str(user.id))

    if containers_result.is_err() or not containers_result.unwrap():
        return {
            "context": await cen.get(
                "select_container",
                error="У вас нет контейнеров. Сначала создайте контейнер командой /container",
            )
        }

    containers = containers_result.unwrap()

    return {
        "context": await cen.get(
            "select_container", containers=containers, containers_count=len(containers)
        )
    }


@with_template_engine
@with_parse_mode(ParseMode.HTML)
@with_auto_reply("filters/file_upload.j2")
async def handle_file_upload(
    message: Message,
    user: User,
    ten: TemplateEngine,
    file_service: FileService,
    auth_service: AuthService,
    api_service: ApiService,
    container_service: ContainerService,
    text_service: TextService,
    cen: ContextEngine,
):
    if not message.document:
        return {
            "context": await cen.get("file_upload", error="Пожалуйста, отправьте файл")
        }

    containers_result = await container_service.get_containers_by_user_id(str(user.id))

    if containers_result.is_err():
        return {
            "context": await cen.get(
                "file_upload",
                error="Ошибка при получении контейнеров. Сначала создайте контейнер.",
            )
        }

    containers = containers_result.unwrap()

    if not containers:
        return {
            "context": await cen.get(
                "file_upload",
                error="У вас нет контейнеров. Сначала создайте контейнер командой /container",
            )
        }

    container = containers[0]

    document = message.document

    if document.file_size and document.file_size > text_service.max_file_size:
        return {
            "context": await cen.get(
                "file_upload",
                error=f"Файл слишком большой. Максимальный размер: {text_service.max_file_size // 1024 // 1024}MB",
            )
        }

    file_data = {
        "id": document.file_id,
        "container_id": container.id,
        "name": document.file_name or f"file_{document.file_id}",
        "size": document.file_size,
        "user_id": str(user.id),
        "created_at": datetime.now(),
        "mime_type": document.mime_type or "application/octet-stream",
    }

    db_result = await file_service.create_file(file_data)

    if db_result.is_err():
        error = db_result.unwrap_err()
        Logger.error(f"Error creating file in DB: {error}")
        return {
            "context": await cen.get(
                "file_upload", error=f"Ошибка базы данных: {error}"
            )
        }

    file = db_result.unwrap()

    try:
        file_info = await message.bot.get_file(document.file_id)
        file_content = await message.bot.download_file(file_info.file_path)

        binary_content = file_content.read()

        Logger.info(
            f"File info: name={file.name}, size={len(binary_content)} bytes, container={container.id}, mime_type={document.mime_type}"
        )

        if document.mime_type == "application/pdf":
            text_result = await text_service.extract_text_from_pdf(
                stream=binary_content
            )

            if text_result.is_err():
                await file_service.delete_file(file.id)
                error = text_result.unwrap_err()
                Logger.error(f"Error extracting text from PDF: {error}")
                return {
                    "context": await cen.get(
                        "file_upload",
                        error=f"Ошибка извлечения текста из PDF: {str(error)}",
                    )
                }

            extracted_text = text_result.unwrap()
            Logger.info(f"Extracted {len(extracted_text)} characters from PDF")

            if not extracted_text.strip():
                await file_service.delete_file(file.id)
                return {
                    "context": await cen.get(
                        "file_upload",
                        error="Не удалось извлечь текст из PDF файла. Файл может быть сканом или защищенным.",
                    )
                }

            api_result = await api_service.create_file(
                path=file.id,
                content=extracted_text,
                user_id=str(user.id),
                container_id=container.id,
            )

        elif document.mime_type and document.mime_type.startswith("text/"):
            content_text = binary_content.decode("utf-8", errors="ignore")
            api_result = await api_service.create_file(
                path=file.id,
                content=content_text,
                user_id=str(user.id),
                container_id=container.id,
            )
        else:
            content_base64 = base64.b64encode(binary_content).decode("ascii")
            api_result = await api_service.create_file(
                path=file.id,
                content=content_base64,
                user_id=str(user.id),
                container_id=container.id,
            )

        if api_result.is_err():
            await file_service.delete_file(file.id)
            error = api_result.unwrap_err()
            Logger.error(f"Error uploading to C++ service: {error}")

            error_msg = str(error)
            if "413" in error_msg:
                error_msg = f"Файл слишком большой ({len(binary_content)} bytes). Попробуйте файл меньшего размера."
            elif "mimetype" in error_msg.lower():
                error_msg = "Ошибка связи с сервисом хранения. Попробуйте позже."

            return {
                "context": await cen.get(
                    "file_upload", error=f"Ошибка загрузки: {error_msg}"
                )
            }

        return {
            "context": await cen.get(
                "file_upload", success=True, file=file, container_name=container.id
            )
        }

    except Exception as e:
        await file_service.delete_file(file.id)
        Logger.error(f"Error processing file upload: {e}")
        return {"context": await cen.get("file_upload", error=f"Ошибка обработки: {e}")}


@with_template_engine
@with_parse_mode(ParseMode.HTML)
@with_auto_reply("commands/semantic_search.j2")
async def handle_search(
    message: Message,
    user: User,
    ten: TemplateEngine,
    file_service: FileService,
    auth_service: AuthService,
    container_service: ContainerService,
    api_service: ApiService,
    cen: ContextEngine,
):
    query = message.text.strip()
    query = query.replace("/search", "").strip()

    if not query:
        return {
            "context": await cen.get(
                "semantic_search", error="Please provide a search query"
            )
        }

    containers_result = await container_service.get_containers_by_user_id(str(user.id))

    Logger.info(containers_result.unwrap())

    search_result = await api_service.semantic_search(
        query,
        user,
        containers_result.unwrap()[0],
        limit=10,
    )

    if search_result.is_err():
        error = search_result.unwrap_err()
        Logger.error(f"Semantic search error: {error}")
        return {
            "context": await cen.get("semantic_search", error=f"Search error: {error}")
        }

    search_data = search_result.unwrap()
    results = search_data.get("results", [])

    return {
        "context": await cen.get(
            "semantic_search", query=query, results=results, count=len(results)
        )
    }


@with_template_engine
@with_parse_mode(ParseMode.HTML)
@with_auto_reply("commands/read_file.j2")
async def handle_read_file(
    message: Message,
    user: User,
    ten: TemplateEngine,
    file_service: FileService,
    api_service: ApiService,
    cen: ContextEngine,
):
    args = message.text.split()[1:]
    if not args:
        return {
            "context": await cen.get(
                "read_file", error="Please provide file path or ID"
            )
        }

    file_identifier = args[0]

    file_result = await file_service.get_file(file_identifier)
    if file_result.is_ok() and file_result.unwrap():
        file = file_result.unwrap()
        path = f"/{file.id}_{file.name}"
    else:
        path = file_identifier

    read_result = await api_service.read_file(path)

    if read_result.is_err():
        error = read_result.unwrap_err()
        Logger.error(f"Read file error: {error}")
        return {"context": await cen.get("read_file", error=f"Read error: {error}")}

    file_data = read_result.unwrap()

    return {
        "context": await cen.get(
            "read_file",
            path=file_data.get("path", path),
            content=file_data.get("content", ""),
            size=file_data.get("size", 0),
        )
    }


@with_template_engine
@with_parse_mode(ParseMode.HTML)
@with_auto_reply("commands/read_file_impl.j2")
async def handle_read_file_impl(
    message: Message,
    user: User,
    ten: TemplateEngine,
    api_service: ApiService,
    cen: ContextEngine,
):
    import html
    import base64

    args = message.text.split()[1:]

    if not args:
        return {
            "context": await cen.get(
                "read_file",
                error="Использование: /read_file <file_id> /container_id <container_id>",
            )
        }

    file_id = args[0]
    container_id = args[1]

    content_result = await api_service.get_file_content(str(file_id), str(container_id))

    if content_result.is_err():
        error = content_result.unwrap_err()
        Logger.error(f"Error read file: {error}")
        return {
            "context": await cen.get("read_file", error=f"Ошибка чтения файла: {error}")
        }

    content = content_result.unwrap()

    def is_base64_encoded(s):
        try:
            if len(s) > 100 and all(
                c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/="
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


@with_template_engine
@with_parse_mode(ParseMode.HTML)
@with_auto_reply("commands/rebuild_index.j2")
async def handle_rebuild_index(
    message: Message,
    user: User,
    ten: TemplateEngine,
    api_service: ApiService,
    cen: ContextEngine,
):
    if not user.is_admin:
        return {
            "context": await cen.get("rebuild_index", error="Insufficient permissions")
        }

    rebuild_result = await api_service.rebuild_index()

    if rebuild_result.is_err():
        error = rebuild_result.unwrap_err()
        Logger.error(f"Rebuild index error: {error}")
        return {
            "context": await cen.get("rebuild_index", error=f"Rebuild error: {error}")
        }

    rebuild_data = rebuild_result.unwrap()

    return {
        "context": await cen.get(
            "rebuild_index",
            message=rebuild_data.get("message", "Index rebuilt successfully"),
        )
    }


@with_template_engine
@with_parse_mode(ParseMode.HTML)
@with_auto_reply("commands/health_check.j2")
async def handle_health_check(
    message: Message,
    user: User,
    ten: TemplateEngine,
    api_service: ApiService,
    cen: ContextEngine,
):
    health_result = await api_service.health_check()

    if health_result.is_err():
        error = health_result.unwrap_err()
        Logger.error(f"Health check error: {error}")
        return {
            "context": await cen.get("health_check", status="offline", error=str(error))
        }

    is_healthy = health_result.unwrap()

    return {
        "context": await cen.get(
            "health_check",
            status="online" if is_healthy else "offline",
            message=(
                "C++ service is operational" if is_healthy else "C++ service is down"
            ),
        )
    }


@with_template_engine
@with_parse_mode(ParseMode.HTML)
@with_auto_reply("commands/list_files.j2")
async def handle_list_files(
    message: Message,
    user: User,
    ten: TemplateEngine,
    file_service: FileService,
    api_service: ApiService,
    container_service: ContainerService,
    cen: ContextEngine,
):
    containers = await container_service.get_containers_by_user_id(user.id)
    files_result = [
        await file_service.get_files_by_container(container) for container in containers
    ]

    if files_result.is_err():
        error = files_result.unwrap_err()
        Logger.error(f"List files error: {error}")
        return {
            "context": await cen.get("list_files", error=f"Database error: {error}")
        }

    files = files_result.unwrap()

    files_info = []
    for file in files:
        path = f"/{file.id}_{file.name}"
        read_result = await api_service.read_file(path)

        if read_result.is_ok():
            file_data = read_result.unwrap()
            files_info.append(
                {
                    "id": file.id,
                    "name": file.name,
                    "path": file_data.get("path", path),
                    "size": file_data.get("size", 0),
                    "db_size": file.size,
                    "created_at": file.created_at,
                }
            )
        else:
            files_info.append(
                {
                    "id": file.id,
                    "name": file.name,
                    "path": path,
                    "size": "N/A",
                    "db_size": file.size,
                    "created_at": file.created_at,
                    "error": "Not found in storage",
                }
            )

    return {
        "context": await cen.get("list_files", files=files_info, count=len(files_info))
    }


@with_template_engine
@with_parse_mode(ParseMode.HTML)
@with_auto_reply("commands/delete_file.j2")
async def handle_delete_file(
    message: Message,
    user: User,
    ten: TemplateEngine,
    file_service: FileService,
    api_service: ApiService,
    cen: ContextEngine,
):
    args = message.text.split()[1:]
    if not args:
        return {"context": await cen.get("delete_file", error="Please provide file ID")}

    file_id = args[0]

    file_result = await file_service.get_file(file_id)
    if file_result.is_err() or not file_result.unwrap():
        return {
            "context": await cen.get("delete_file", error="File not found in database")
        }

    file = file_result.unwrap()

    if file.user_id != user.id and not user.is_admin:
        return {"context": await cen.get("delete_file", error="Access denied")}

    delete_result = await file_service.delete_file(file_id)

    if delete_result.is_err():
        error = delete_result.unwrap_err()
        Logger.error(f"Delete file error: {error}")
        return {"context": await cen.get("delete_file", error=f"Delete error: {error}")}

    return {
        "context": await cen.get(
            "delete_file", success=True, file_id=file_id, file_name=file.name
        )
    }


@with_template_engine
@with_parse_mode(ParseMode.HTML)
async def handle_service_status(
    message: Message,
    user: User,
    ten: TemplateEngine,
    api_service: ApiService,
    cen: ContextEngine,
):
    """Команда для проверки статуса C++ сервиса"""
    if not user.is_admin:
        return await message.answer("❌ Insufficient permissions")

    health_result = await api_service.health_check()
    root_result = await api_service.get_root()

    status_text = "<b>C++ Service Status</b>\n\n"

    if health_result.is_ok() and health_result.unwrap():
        status_text += "✅ <b>Status:</b> Online\n"

        if root_result.is_ok():
            root_data = root_result.unwrap()
            status_text += (
                f"📊 <b>Message:</b> {root_data.get('message', 'No message')}\n"
            )
        else:
            status_text += "⚠️ <b>Root endpoint:</b> Error\n"
    else:
        status_text += "❌ <b>Status:</b> Offline\n"
        if health_result.is_err():
            status_text += f"🔴 <b>Error:</b> {health_result.unwrap_err()}\n"

    await message.answer(status_text, parse_mode=ParseMode.HTML)
