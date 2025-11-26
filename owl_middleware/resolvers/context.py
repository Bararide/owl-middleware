from models import User, File
from fastbot.decorators import register_context
from typing import List, Dict, Any


@register_context("start")
async def start_context(user: User):
    return {
        "user": user,
        "welcome_message": f"Добро пожаловать, {user.first_name}!",
        "is_admin": user.is_admin,
    }


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
async def file_list_context(files: list[File]):
    return {"files": files}


@register_context("read_file_impl")
async def read_file_impl_context(
    content: str, truncated: str, error: str, is_pdf: bool
):
    return {
        "content": content,
        "truncated": truncated,
        "error": error,
        "is_pdf": is_pdf,
    }


@register_context("create_container_help")
async def create_container_help_context(user_id: str = ""):
    return {"user_id": user_id}


@register_context("create_container")
async def create_container_context(
    success: bool = False,
    container_id: str = "",
    user_id: str = "",
    error: str = "",
    container: Dict[str, Any] = None,
    limits: Dict[str, Any] = None,
):
    return {
        "success": success,
        "container_id": container_id,
        "user_id": user_id,
        "error": error,
        "container": container or {},
        "limits": limits or {},
        "has_limits": bool(limits),
    }


@register_context("file_upload")
async def file_upload_context(
    success: bool = False, error: str = "", file: File = None, container_name: str = ""
):
    return {
        "success": success,
        "error": error,
        "file": file,
        "container_name": container_name,
    }


@register_context("process_photo")
async def process_photo_context(
    success: bool = False,
    extracted_text: str = "",
    characters_count: int = 0,
    container_name: str = "",
    file_id: str = "",
    error: str = "",
    is_truncated: bool = False,
):
    return {
        "success": success,
        "extracted_text": extracted_text,
        "characters_count": characters_count,
        "container_name": container_name,
        "file_id": file_id,
        "error": error,
        "is_truncated": is_truncated,
        "has_text": bool(extracted_text.strip()),
        "text_preview": (
            extracted_text[:100] + "..."
            if len(extracted_text) > 100
            else extracted_text
        ),
        "characters_k": (
            f"{characters_count / 1000:.1f}k"
            if characters_count >= 1000
            else str(characters_count)
        ),
    }


@register_context("get_token")
async def get_token_context(
    success: bool = False,
    token: str = "",
    web_url: str = "",
    user_id: int = 0,
    expires_hours: int = 24,
    error: str = "",
):
    return {
        "success": success,
        "token": token,
        "web_url": web_url,
        "user_id": user_id,
        "expires_hours": expires_hours,
        "error": error,
        "has_token": bool(token),
        "token_preview": token[:50] + "..." if len(token) > 50 else token,
    }


@register_context("download_file")
async def download_file_context(
    success: bool = False,
    filename: str = "",
    size: int = 0,
    error: str = "",
    files: List[File] = None,
    files_count: int = 0,
    container_id: str = "",
):
    if files is None:
        files = []

    return {
        "success": success,
        "filename": filename,
        "size": size,
        "error": error,
        "files": files,
        "files_count": files_count,
        "has_files": files_count > 0,
        "size_kb": size / 1024 if size > 0 else 0,
        "size_mb": size / (1024 * 1024) if size > 0 else 0,
        "container_id": container_id,
    }


@register_context("download_selection")
async def download_selection_context(
    containers: List[Any] = None,
    files: List[File] = None,
    selected_container: str = "",
    error: str = "",
):
    if containers is None:
        containers = []
    if files is None:
        files = []

    return {
        "containers": containers,
        "files": files,
        "selected_container": selected_container,
        "error": error,
        "has_containers": len(containers) > 0,
        "has_files": len(files) > 0,
        "containers_count": len(containers),
        "files_count": len(files),
        "total_files_size": sum(file.size for file in files if file.size),
    }


@register_context("file_preview")
async def file_preview_context(
    file: File = None,
    preview_content: str = "",
    full_content: str = "",
    error: str = "",
    is_truncated: bool = False,
    max_preview_length: int = 500,
):
    if file is None:
        file = File()

    return {
        "file": file,
        "preview_content": preview_content,
        "full_content": full_content,
        "error": error,
        "is_truncated": is_truncated,
        "max_preview_length": max_preview_length,
        "has_preview": bool(preview_content.strip()),
        "has_full_content": bool(full_content.strip()),
        "can_download_full": bool(full_content.strip()) and not error,
    }


@register_context("semantic_search")
async def semantic_search_context(
    query: str = "",
    results: List[Dict[str, Any]] = None,
    count: int = 0,
    error: str = "",
):
    if results is None:
        results = []

    return {
        "query": query,
        "results": results,
        "count": count,
        "error": error,
        "has_results": count > 0,
    }


@register_context("read_file")
async def read_file_context(
    path: str = "", content: str = "", size: int = 0, error: str = ""
):
    return {
        "path": path,
        "content": content,
        "size": size,
        "error": error,
        "has_content": bool(content.strip()),
        "preview": content[:200] + "..." if len(content) > 200 else content,
    }


@register_context("rebuild_index")
async def rebuild_index_context(message: str = "", error: str = ""):
    return {"message": message, "error": error, "success": not bool(error)}


@register_context("health_check")
async def health_check_context(
    status: str = "unknown", message: str = "", error: str = ""
):
    return {
        "status": status,
        "message": message,
        "error": error,
        "is_online": status == "online",
        "is_offline": status == "offline",
    }


@register_context("list_files")
async def list_files_context(
    files: List[Dict[str, Any]] = None, count: int = 0, error: str = ""
):
    if files is None:
        files = []

    return {
        "files": files,
        "count": count,
        "error": error,
        "has_files": count > 0,
        "total_size": sum(
            f.get("size", 0) for f in files if isinstance(f.get("size"), int)
        ),
    }


@register_context("delete_file")
async def delete_file_context(
    success: bool = False, file_id: str = "", file_name: str = "", error: str = ""
):
    return {
        "success": success,
        "file_id": file_id,
        "file_name": file_name,
        "error": error,
    }


@register_context("service_status")
async def service_status_context(
    status: str = "unknown", message: str = "", error: str = "", is_online: bool = False
):
    return {
        "status": status,
        "message": message,
        "error": error,
        "is_online": is_online,
        "is_offline": not is_online,
        "status_emoji": "✅" if is_online else "❌",
    }


@register_context("file_info")
async def file_info_context(
    file: File = None, content: str = "", api_size: int = 0, error: str = ""
):
    if file is None:
        file = File()

    return {
        "file": file,
        "content": content,
        "api_size": api_size,
        "error": error,
        "has_content": bool(content.strip()),
        "size_match": file.size == api_size if file.size and api_size else True,
    }


@register_context("search_result")
async def search_result_context(result: Dict[str, Any] = None, error: str = ""):
    if result is None:
        result = {}

    return {
        "result": result,
        "error": error,
        "has_result": bool(result),
        "query": result.get("query", ""),
        "results": result.get("results", []),
        "count": result.get("count", 0),
    }


@register_context("api_error")
async def api_error_context(operation: str = "", error: str = "", suggestion: str = ""):
    suggestions = {
        "connection": "Проверьте, запущен ли C++ сервис на localhost:9999",
        "timeout": "Сервис отвечает слишком долго, попробуйте позже",
        "not_found": "Файл не найден в хранилище",
        "permission": "Недостаточно прав для выполнения операции",
    }

    return {
        "operation": operation,
        "error": error,
        "suggestion": suggestion
        or suggestions.get(operation.lower(), "Обратитесь к администратору"),
        "is_connection_error": "connection" in error.lower()
        or "connect" in error.lower(),
        "is_timeout_error": "timeout" in error.lower(),
        "is_not_found_error": "not found" in error.lower() or "404" in error,
    }


@register_context("storage_stats")
async def storage_stats_context(
    total_files: int = 0, total_size: int = 0, avg_file_size: int = 0, error: str = ""
):
    return {
        "total_files": total_files,
        "total_size": total_size,
        "avg_file_size": avg_file_size,
        "error": error,
        "total_size_mb": total_size / (1024 * 1024) if total_size > 0 else 0,
        "has_data": total_files > 0,
    }
