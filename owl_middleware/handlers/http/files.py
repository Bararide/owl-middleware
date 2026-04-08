from fastapi import APIRouter, HTTPException, Request, BackgroundTasks
from fastbot.decorators import inject
from .dependencies import get_current_user_from_request
from services import ContainerService, ApiService, AuthService, FileService, TextService
from models import User
from datetime import datetime
import base64

router = APIRouter(prefix="/containers/{container_id}/files", tags=["files"])


def _detect_mime_type(filename: str) -> str:
    extension = filename.lower().split(".")[-1] if "." in filename else ""
    mime_map = {
        "txt": "text/plain",
        "py": "text/x-python",
        "cpp": "text/x-c++",
        "c": "text/x-c",
        "h": "text/x-c",
        "json": "application/json",
        "yaml": "application/x-yaml",
        "yml": "application/x-yaml",
        "md": "text/markdown",
        "html": "text/html",
        "css": "text/css",
        "js": "application/javascript",
    }
    return mime_map.get(extension, "text/plain")


@router.post("")
@inject("container_service")
@inject("api_service")
@inject("auth_service")
@inject("file_service")
@inject("text_service")
async def upload_file_in_container(
    container_id: str,
    container_service: ContainerService,
    api_service: ApiService,
    auth_service: AuthService,
    file_service: FileService,
    text_service: TextService,
    request: Request,
    background_tasks: BackgroundTasks,
):
    current_user = await get_current_user_from_request(request, auth_service)

    container_result = await container_service.get_container(container_id)
    if container_result.is_err():
        raise HTTPException(status_code=500, detail="Error accessing container")

    container = container_result.unwrap()
    if not container:
        raise HTTPException(status_code=404, detail="Container not found")

    if container.user_id != str(current_user.tg_id) and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Access denied")

    form = await request.form()
    file_upload = form.get("file")
    if not file_upload:
        raise HTTPException(status_code=400, detail="No file provided")

    file_content = await file_upload.read()
    file_size = len(file_content)
    file_name = (
        file_upload.filename or f"file_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )
    mime_type = file_upload.content_type or "application/octet-stream"

    max_file_size = 10 * 1024 * 1024
    if file_size > max_file_size:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {max_file_size // 1024 // 1024}MB",
        )

    file_data = {
        "id": f"http_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file_name}",
        "container_id": container_id,
        "name": file_name,
        "size": file_size,
        "user_id": str(current_user.tg_id),
        "created_at": datetime.now(),
        "mime_type": mime_type,
    }

    db_result = await file_service.create_file(file_data)
    if db_result.is_err():
        raise HTTPException(
            status_code=500, detail=f"Database error: {db_result.unwrap_err()}"
        )

    file_entity = db_result.unwrap()

    try:
        binary_content = file_content
        if mime_type == "application/pdf":
            text_result = await text_service.extract_text_from_pdf(
                stream=binary_content
            )
            if text_result.is_err():
                background_tasks.add_task(file_service.delete_file, file_entity.id)
                raise HTTPException(
                    status_code=400,
                    detail=f"Error extracting text from PDF: {text_result.unwrap_err()}",
                )
            extracted_text = text_result.unwrap()
            if not extracted_text.strip():
                background_tasks.add_task(file_service.delete_file, file_entity.id)
                raise HTTPException(
                    status_code=400, detail="Could not extract text from PDF file"
                )
            api_result = await api_service.files.create_file(
                path=file_entity.id,
                content=extracted_text,
                user_id=str(current_user.id),
                container_id=container.id,
            )
        elif mime_type and mime_type.startswith("text/"):
            content_text = binary_content.decode("utf-8", errors="ignore")
            api_result = await api_service.files.create_file(
                path=file_entity.id,
                content=content_text,
                user_id=str(current_user.id),
                container_id=container.id,
            )
        else:
            content_base64 = base64.b64encode(binary_content).decode("ascii")
            api_result = await api_service.files.create_file(
                path=file_entity.id,
                content=content_base64,
                user_id=str(current_user.id),
                container_id=container.id,
            )

        if api_result.is_err():
            background_tasks.add_task(file_service.delete_file, file_entity.id)
            raise HTTPException(
                status_code=500, detail=f"Upload error: {api_result.unwrap_err()}"
            )

        return {
            "data": {
                "success": True,
                "file": {
                    "id": file_entity.id,
                    "name": file_entity.name,
                    "size": file_entity.size,
                    "mime_type": file_entity.mime_type,
                    "container_id": file_entity.container_id,
                    "created_at": (
                        file_entity.created_at.isoformat()
                        if file_entity.created_at
                        else None
                    ),
                },
                "container_name": container.id,
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        background_tasks.add_task(file_service.delete_file, file_entity.id)
        raise HTTPException(status_code=500, detail=f"Processing error: {str(e)}")


@router.get("/{file_id}/content")
@inject("auth_service")
@inject("container_service")
@inject("api_service")
@inject("file_service")
async def get_file_content(
    container_id: str,
    file_id: str,
    auth_service: AuthService,
    container_service: ContainerService,
    api_service: ApiService,
    file_service: FileService,
    request: Request,
):
    current_user = await get_current_user_from_request(request, auth_service)

    container_result = await container_service.get_container(container_id)
    if container_result.is_err() or not container_result.unwrap():
        raise HTTPException(status_code=404, detail="Container not found")

    container = container_result.unwrap()
    if container.user_id != str(current_user.tg_id) and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Access denied")

    content_result = await api_service.files.get_file_content(
        str(file_id), str(container_id)
    )
    if content_result.is_err():
        raise HTTPException(
            status_code=500,
            detail=f"Error reading file content: {content_result.unwrap_err()}",
        )

    content, explanation = content_result.unwrap()

    file_service_result = await file_service.get_file(file_id)
    file_metadata = (
        file_service_result.unwrap() if file_service_result.is_ok() else None
    )

    response_data = {
        "content": content,
        "encoding": "utf-8",
        "size": len(content),
        "mime_type": file_metadata.mime_type if file_metadata else "text/plain",
    }

    if explanation:
        response_data["explanation"] = explanation

    return {"data": response_data}


@router.delete("/{file_id}")
@inject("container_service")
@inject("api_service")
@inject("auth_service")
async def delete_file_in_container(
    container_id: str,
    file_id: str,
    container_service: ContainerService,
    api_service: ApiService,
    auth_service: AuthService,
    request: Request,
):
    current_user = await get_current_user_from_request(request, auth_service)

    container_result = await container_service.get_container(container_id)
    if container_result.is_err() or not container_result.unwrap():
        raise HTTPException(status_code=404, detail="Container not found")

    api_result = await api_service.files.delete_file(
        user_id=str(current_user.id), container_id=container_id, file_id=file_id
    )
    if api_result.is_err():
        raise HTTPException(
            status_code=500, detail="Error deleting files from container"
        )

    return {"data": {"success": True}}


@router.get("")
@inject("file_service")
@inject("container_service")
@inject("api_service")
@inject("auth_service")
async def list_files(
    container_id: str,
    file_service: FileService,
    container_service: ContainerService,
    api_service: ApiService,
    auth_service: AuthService,
    request: Request,
):
    current_user = await get_current_user_from_request(request, auth_service)

    container_result = await container_service.get_container(container_id)
    if container_result.is_err() or not container_result.unwrap():
        raise HTTPException(status_code=404, detail="Container not found")

    files_api_result = await api_service.containers.get_files_by_container_id(
        current_user.id, container_id
    )
    if files_api_result.is_err():
        raise HTTPException(
            status_code=500, detail="Error fetching files from container"
        )

    container_files = files_api_result.unwrap()

    files_db_result = await file_service.get_files_by_container(container_id)
    db_files = files_db_result.unwrap() if files_db_result.is_ok() else []
    db_files_map = {file.name: file for file in db_files}

    enriched_files = []
    for container_file in container_files:
        file_name = container_file.get("name", "")
        db_file = db_files_map.get(file_name)
        enriched_files.append(
            {
                "id": db_file.id if db_file else None,
                "name": file_name,
                "path": container_file.get("path", ""),
                "content": container_file.get("content", ""),
                "size": container_file.get("size", 0),
                "category": container_file.get("category", "unknown"),
                "is_directory": container_file.get("is_directory", False),
                "exists": container_file.get("exists", True),
                "container_id": container_id,
                "user_id": current_user.id,
                "created_at": (
                    db_file.created_at.isoformat()
                    if db_file and db_file.created_at
                    else None
                ),
                "mime_type": (
                    db_file.mime_type if db_file else _detect_mime_type(file_name)
                ),
            }
        )

    return {
        "data": enriched_files,
        "count": len(enriched_files),
        "container_id": container_id,
    }


@router.get("/refresh")
@inject("file_service")
@inject("container_service")
@inject("api_service")
@inject("auth_service")
async def list_files_and_rebuild(
    container_id: str,
    file_service: FileService,
    container_service: ContainerService,
    api_service: ApiService,
    auth_service: AuthService,
    request: Request,
):
    current_user = await get_current_user_from_request(request, auth_service)

    container_result = await container_service.get_container(container_id)
    if container_result.is_err() or not container_result.unwrap():
        raise HTTPException(status_code=404, detail="Container not found")

    files_api_result = (
        await api_service.containers.get_files_by_container_id_and_rebuild_index(
            current_user.id, container_id
        )
    )
    if files_api_result.is_err():
        raise HTTPException(
            status_code=500, detail="Error fetching files from container"
        )

    container_files = files_api_result.unwrap()

    files_db_result = await file_service.get_files_by_container(container_id)
    db_files = files_db_result.unwrap() if files_db_result.is_ok() else []
    db_files_map = {file.name: file for file in db_files}

    enriched_files = []
    for container_file in container_files:
        file_name = container_file.get("name", "")
        db_file = db_files_map.get(file_name)
        enriched_files.append(
            {
                "id": db_file.id if db_file else None,
                "name": file_name,
                "path": container_file.get("path", ""),
                "content": container_file.get("content", ""),
                "size": container_file.get("size", 0),
                "category": container_file.get("category", "unknown"),
                "is_directory": container_file.get("is_directory", False),
                "exists": container_file.get("exists", True),
                "container_id": container_id,
                "user_id": current_user.id,
                "created_at": (
                    db_file.created_at.isoformat()
                    if db_file and db_file.created_at
                    else None
                ),
                "mime_type": (
                    db_file.mime_type if db_file else _detect_mime_type(file_name)
                ),
            }
        )

    return {
        "data": enriched_files,
        "count": len(enriched_files),
        "container_id": container_id,
    }
