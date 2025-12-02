import base64
from fastapi import APIRouter, HTTPException, Request, UploadFile, File
from datetime import datetime

from fastbot.decorators import inject
from fastbot.logger import Logger
from services import (
    AuthService,
    FileService,
    ApiService,
    ContainerService,
    AgentService,
    Ocr,
    TextService,
)
from models import User

from pampy import match, _

http_router = APIRouter()


@http_router.post("/auth/register")
@inject("auth_service")
async def register_email_user(
    request: dict,
    auth_service: AuthService,
):
    email = request.get("email")
    password = request.get("password")
    first_name = request.get("first_name", "Unknown")
    last_name = request.get("last_name")

    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password required")

    user_result = await auth_service.register_email_user(
        email, password, {"first_name": first_name, "last_name": last_name}
    )

    if user_result.is_err():
        raise HTTPException(status_code=400, detail=str(user_result.unwrap_err()))

    user = user_result.unwrap()
    token = auth_service.generate_jwt_token(user)

    return {
        "data": {
            "user": {
                "id": user.id,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
            },
            "token": token,
        }
    }


@http_router.post("/auth/login")
@inject("auth_service")
async def login_email_user(
    request: dict,
    auth_service: AuthService,
):
    email = request.get("email")
    password = request.get("password")

    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password required")

    auth_result = await auth_service.authenticate_email(email, password)
    if auth_result.is_err():
        raise HTTPException(status_code=401, detail="Invalid credentials")

    user = auth_result.unwrap()
    token = auth_service.generate_jwt_token(user)

    return {
        "data": {
            "user": {
                "id": user.id,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
            },
            "token": token,
        }
    }


@http_router.post("/auth/telegram-token")
@inject("auth_service")
async def get_telegram_token(
    request: Request,
    auth_service: AuthService,
    current_user: User,
):
    if not current_user.tg_id:
        raise HTTPException(status_code=400, detail="Not a Telegram user")

    token = auth_service.generate_jwt_token(current_user)

    return {
        "data": {
            "token": token,
            "user": {
                "id": current_user.id,
                "tg_id": current_user.tg_id,
                "username": current_user.username,
                "first_name": current_user.first_name,
            },
        }
    }


@http_router.get("/containers")
@inject("container_service")
@inject("auth_service")
async def list_containers(
    container_service: ContainerService,
    auth_service: AuthService,
    request: Request,
):
    token = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:]
    else:
        token = request.query_params.get("token")
        Logger.error(f"Query token: {request.query_params.get('token')}")

    if not token:
        Logger.error("No token provided")
        raise HTTPException(status_code=401, detail="Token required")

    user_result = await auth_service.get_user_by_token(token)
    if user_result.is_err():
        Logger.error(f"Invalid token: {user_result.unwrap_err()}")
        raise HTTPException(status_code=401, detail="Invalid token")

    current_user = user_result.unwrap()

    containers_result = await container_service.get_containers_by_user_id(
        str(current_user.tg_id)
    )

    if containers_result.is_err():
        Logger.error(f"Error fetching containers: {containers_result.unwrap_err()}")
        raise HTTPException(status_code=500, detail="Error fetching containers")

    containers = containers_result.unwrap()
    return {
        "data": [
            {
                "id": container.id,
                "status": "running",
                "memory_limit": container.tariff.memory_limit,
                "storage_quota": container.tariff.storage_quota,
                "file_limit": container.tariff.file_limit,
                "env_label": container.env_label,
                "type_label": container.type_label,
                # "created_at": (
                #     container.created_at.isoformat() if container.created_at else None
                # ),
                "created_at": datetime.now().isoformat(),
                "cpu_usage": "10",
                "memory_usage": "10",
                "user_id": container.user_id,
                "commands": container.commands,
                "privileged": container.privileged,
                # "cpu_usage": container.cpu_usage,
                # "memory_usage": container.memory_usage,
                # "user_id": container.user_id,
                # "commands": container.commands,
                # "privileged": container.privileged,
            }
            for container in containers
        ]
    }


@http_router.get("/containers/{container_id}/files/{file_id}/content")
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
    try:
        token = None
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]
        else:
            token = request.query_params.get("token")

        if not token:
            Logger.error("No token provided for file content")
            raise HTTPException(status_code=401, detail="Token required")

        user_result = await auth_service.get_user_by_token(token)
        if user_result.is_err():
            Logger.error(f"Invalid token for file content: {user_result.unwrap_err()}")
            raise HTTPException(status_code=401, detail="Invalid token")

        current_user = user_result.unwrap()
        Logger.info(
            f"User {current_user.tg_id} requesting file content: {file_id} from container: {container_id}"
        )

        container_result = await container_service.get_container(container_id)
        if container_result.is_err() or not container_result.unwrap():
            Logger.error(f"Container not found: {container_id}")
            raise HTTPException(status_code=404, detail="Container not found")

        container = container_result.unwrap()
        if container.user_id != str(current_user.tg_id) and not current_user.is_admin:
            Logger.error(
                f"Access denied for user {current_user.tg_id} to container {container_id}"
            )
            raise HTTPException(status_code=403, detail="Access denied")

        content_result = await api_service.get_file_content(
            str(file_id), str(container_id)
        )

        if content_result.is_err():
            error = content_result.unwrap_err()
            Logger.error(f"Error getting file content: {error}")
            raise HTTPException(
                status_code=500, detail=f"Error reading file content: {error}"
            )

        content = content_result.unwrap()

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

        Logger.info(
            f"File content retrieved successfully: {file_id} from container {container_id}"
        )

        return {"data": response_data}

    except HTTPException:
        raise
    except Exception as e:
        Logger.error(f"Unexpected error in get_file_content: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@http_router.post("/containers/{container_id}/files")
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
):
    Logger.info("=" * 50)
    Logger.info("UPLOAD FILE HANDLER CALLED")
    Logger.info(f"Container ID from path: {container_id}")

    try:
        token = None
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]
        else:
            token = request.query_params.get("token")

        if not token:
            Logger.error("No token provided for file upload")
            raise HTTPException(status_code=401, detail="Token required")

        user_result = await auth_service.get_user_by_token(token)
        if user_result.is_err():
            Logger.error(f"Invalid token for file upload: {user_result.unwrap_err()}")
            raise HTTPException(status_code=401, detail="Invalid token")

        current_user = user_result.unwrap()
        Logger.info(f"File upload request from user: {current_user.tg_id}")

        container_result = await container_service.get_container(container_id)
        if container_result.is_err():
            Logger.error(f"Error getting container: {container_result.unwrap_err()}")
            raise HTTPException(status_code=500, detail="Error accessing container")

        container = container_result.unwrap()
        if not container:
            Logger.error(f"Container not found: {container_id}")
            raise HTTPException(status_code=404, detail="Container not found")

        if container.user_id != str(current_user.tg_id) and not current_user.is_admin:
            Logger.error(
                f"Access denied for user {current_user.tg_id} to container {container_id}"
            )
            raise HTTPException(status_code=403, detail="Access denied")

        form = await request.form()
        Logger.info(f"Form keys: {list(form.keys())}")

        file_upload = form.get("file")
        if not file_upload:
            Logger.error("No 'file' field in form-data")
            raise HTTPException(status_code=400, detail="No file provided")

        Logger.info(f"File upload type: {type(file_upload)}")

        if not hasattr(file_upload, "read"):
            Logger.error(f"Expected UploadFile, got {type(file_upload)}")
            raise HTTPException(status_code=400, detail="Invalid file format")

        file_content = await file_upload.read()
        file_size = len(file_content)
        file_name = (
            file_upload.filename or f"file_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        mime_type = file_upload.content_type or "application/octet-stream"

        Logger.info(f"File: {file_name}, size: {file_size} bytes, type: {mime_type}")

        max_file_size = 10 * 1024 * 1024
        if file_size > max_file_size:
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Maximum size: {max_file_size // 1024 // 1024}MB",
            )

        Logger.info("1. Checking container limits...")
        limits_result = await container_service.check_container_limits(container_id)
        if limits_result.is_ok():
            limits = limits_result.unwrap()
            storage_used = limits["storage"]["used"]
            storage_limit = limits["storage"]["limit"]

            if storage_used + file_size > storage_limit:
                raise HTTPException(
                    status_code=400,
                    detail=f"Storage quota exceeded. Available: {storage_limit - storage_used} bytes, file size: {file_size} bytes",
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

        Logger.info(2)
        db_result = await file_service.create_file(file_data)
        if db_result.is_err():
            error = db_result.unwrap_err()
            Logger.error(f"Error creating file in DB: {error}")
            raise HTTPException(status_code=500, detail=f"Database error: {error}")

        file_entity = db_result.unwrap()

        try:
            binary_content = file_content
            Logger.info(
                f"File info: name={file_entity.name}, size={len(binary_content)} bytes, container={container.id}, mime_type={mime_type}"
            )

            if mime_type == "application/pdf":
                text_result = await text_service.extract_text_from_pdf(
                    stream=binary_content
                )

                if text_result.is_err():
                    await file_service.delete_file(file_entity.id)
                    error = text_result.unwrap_err()
                    Logger.error(f"Error extracting text from PDF: {error}")
                    raise HTTPException(
                        status_code=400,
                        detail=f"Error extracting text from PDF: {str(error)}",
                    )

                extracted_text = text_result.unwrap()
                Logger.info(f"Extracted {len(extracted_text)} characters from PDF")

                if not extracted_text.strip():
                    await file_service.delete_file(file_entity.id)
                    raise HTTPException(
                        status_code=400,
                        detail="Could not extract text from PDF file. The file may be scanned or protected.",
                    )

                api_result = await api_service.create_file(
                    path=file_entity.id,
                    content=extracted_text,
                    user_id=str(current_user.id),
                    container_id=container.id,
                )

            elif mime_type and mime_type.startswith("text/"):
                content_text = binary_content.decode("utf-8", errors="ignore")
                api_result = await api_service.create_file(
                    path=file_entity.id,
                    content=content_text,
                    user_id=str(current_user.id),
                    container_id=container.id,
                )
            else:
                content_base64 = base64.b64encode(binary_content).decode("ascii")
                api_result = await api_service.create_file(
                    path=file_entity.id,
                    content=content_base64,
                    user_id=str(current_user.id),
                    container_id=container.id,
                )

            if api_result.is_err():
                await file_service.delete_file(file_entity.id)
                error = api_result.unwrap_err()
                Logger.error(f"Error uploading to C++ service: {error}")

                error_msg = str(error)
                if "413" in error_msg:
                    error_msg = f"File too large ({len(binary_content)} bytes). Try a smaller file."
                elif "mimetype" in error_msg.lower():
                    error_msg = (
                        "Storage service communication error. Please try again later."
                    )

                raise HTTPException(
                    status_code=500, detail=f"Upload error: {error_msg}"
                )

            Logger.info(
                f"File uploaded successfully: {file_name} to container {container_id} by user {current_user.tg_id}"
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
            await file_service.delete_file(file_entity.id)
            Logger.error(f"Error processing file upload: {e}")
            raise HTTPException(status_code=500, detail=f"Processing error: {str(e)}")

    except HTTPException:
        raise
    except Exception as e:
        Logger.error(f"Unexpected error in file upload: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@http_router.delete("/containers/{file_id}/files/{container_id}")
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
    token = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:]
    else:
        token = request.query_params.get("token")
        Logger.error(f"Query token: {request.query_params.get('token')}")

    if not token:
        Logger.error("No token provided")
        raise HTTPException(status_code=401, detail="Token required")

    user_result = await auth_service.get_user_by_token(token)
    if user_result.is_err():
        Logger.error(f"Invalid token: {user_result.unwrap_err()}")
        raise HTTPException(status_code=401, detail="Invalid token")

    current_user = user_result.unwrap()

    container_result = await container_service.get_container(container_id)
    if container_result.is_err() or not container_result.unwrap():
        raise HTTPException(status_code=404, detail="Container not found")

    api_result = await api_service.delete_file(
        user_id=str(current_user.id), container_id=container_id, file_id=file_id
    )

    if api_result.is_err():
        raise HTTPException(
            status_code=500, detail="Error deleting files from container"
        )

    return {"data": {"success": True}}


@http_router.get("/health")
@inject("api_service")
async def check_health(request: Request, api_service: ApiService):
    health_check_result = await api_service.health_check()

    if health_check_result.is_err():
        raise HTTPException(status_code=500, detail="Health check failed")

    return {"status": "healthy", "success": True}


@http_router.get("/containers/{container_id}/files")
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
    token = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:]
    else:
        token = request.query_params.get("token")
        Logger.error(f"Query token: {request.query_params.get('token')}")

    if not token:
        Logger.error("No token provided")
        raise HTTPException(status_code=401, detail="Token required")

    user_result = await auth_service.get_user_by_token(token)
    if user_result.is_err():
        Logger.error(f"Invalid token: {user_result.unwrap_err()}")
        raise HTTPException(status_code=401, detail="Invalid token")

    current_user = user_result.unwrap()

    container_result = await container_service.get_container(container_id)
    if container_result.is_err() or not container_result.unwrap():
        raise HTTPException(status_code=404, detail="Container not found")

    files_api_result = await api_service.get_files_by_container_id(
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

        enriched_file = {
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
        enriched_files.append(enriched_file)

    return {
        "data": enriched_files,
        "count": len(enriched_files),
        "container_id": container_id,
    }


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


@http_router.get("/containers/{container_id}")
@inject("container_service")
@inject("user_resolver")
@inject("api_service")
async def get_container(
    container_id: str,
    container_service: ContainerService,
    current_user: User,
):
    container_result = await container_service.get_container(container_id)

    if container_result.is_err() or not container_result.unwrap():
        raise HTTPException(status_code=404, detail="Container not found")

    container = container_result.unwrap()

    if container.user_id != str(current_user.id) and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Access denied")

    return {
        "data": {
            "id": container.id,
            "status": container.status,
            "memory_limit": container.memory_limit,
            "storage_quota": container.storage_quota,
            "file_limit": container.file_limit,
            "env_label": container.env_label,
            "type_label": container.type_label,
            "created_at": (
                container.created_at.isoformat() if container.created_at else None
            ),
            "cpu_usage": container.cpu_usage,
            "memory_usage": container.memory_usage,
            "user_id": container.user_id,
            "commands": container.commands,
            "privileged": container.privileged,
        }
    }


@http_router.post("/containers")
@inject("container_service")
@inject("api_service")
@inject("auth_service")
async def create_container(
    request: dict,
    req: Request,
    container_service: ContainerService,
    api_service: ApiService,
    auth_service: AuthService,
):
    token = None
    auth_header = req.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:]
    else:
        token = req.query_params.get("token")
        Logger.error(f"Query token: {req.query_params.get('token')}")

    if not token:
        Logger.error("No token provided")
        raise HTTPException(status_code=401, detail="Token required")

    user_result = await auth_service.get_user_by_token(token)
    if user_result.is_err():
        Logger.error(f"Invalid token: {user_result.unwrap_err()}")
        raise HTTPException(status_code=401, detail="Invalid token")

    current_user = user_result.unwrap()

    container_data = {
        "user_id": str(current_user.tg_id),
        "container_id": request["container_id"],
        "memory_limit": request["memory_limit"],
        "storage_quota": request["storage_quota"],
        "file_limit": request["file_limit"],
        "env_label": request.get(
            "env_label", {"key": "environment", "value": "development"}
        ),
        "type_label": request.get("type_label", {"key": "type", "value": "workspace"}),
        "commands": request.get("commands", ["search", "debug", "all", "create"]),
        "privileged": request.get("privileged", False),
    }

    db_result = await container_service.create_container(container_data)

    if db_result.is_err():
        raise HTTPException(
            status_code=500, detail=f"Database error: {db_result.unwrap_err()}"
        )

    container = db_result.unwrap()

    api_result = await api_service.create_container(
        user_id=str(current_user.id),
        container_id=request["container_id"],
        tariff=container.tariff,
        env_label=container.env_label,
        type_label=container.type_label,
        commands=container.commands,
        privileged=container.privileged,
    )

    if api_result.is_err():
        await container_service.delete_container(
            current_user.tg_id, request["container_id"]
        )
        raise HTTPException(
            status_code=500, detail=f"Service error: {api_result.unwrap_err()}"
        )

    return {
        "data": [
            {
                "id": container.id,
                "status": "running",
                "memory_limit": container.tariff.memory_limit,
                "storage_quota": container.tariff.storage_quota,
                "file_limit": container.tariff.file_limit,
                "env_label": container.env_label,
                "type_label": container.type_label,
                # "created_at": (
                #     container.created_at.isoformat() if container.created_at else None
                # ),
                "created_at": datetime.now().isoformat(),
                "cpu_usage": "10",
                "memory_usage": "10",
                "user_id": container.user_id,
                "commands": container.commands,
                "privileged": container.privileged,
                # "cpu_usage": container.cpu_usage,
                # "memory_usage": container.memory_usage,
                # "user_id": container.user_id,
                # "commands": container.commands,
                # "privileged": container.privileged,
            }
        ]
    }


@http_router.get("/user")
@inject("auth_service")
async def get_user(request: Request, auth_service: AuthService):
    token = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:]
    else:
        token = request.query_params.get("token")

    if not token:
        Logger.error("No token provided for OCR")
        raise HTTPException(status_code=401, detail="Token required")

    user_result = await auth_service.get_user_by_token(token)
    if user_result.is_err():
        Logger.error(f"Invalid token for OCR: {user_result.unwrap_err()}")
        raise HTTPException(status_code=401, detail="Invalid token")

    current_user = user_result.unwrap()

    return {
        "data": {
            "id": current_user.id,
            "name": current_user.username,
            "email": current_user.email,
            "role": current_user.is_admin,
        }
    }


@http_router.post("/ocr/process")
@inject("api_service")
@inject("container_service")
@inject("auth_service")
@inject("ocr_service")
async def process_ocr(
    request: dict,
    api_service: ApiService,
    container_service: ContainerService,
    auth_service: AuthService,
    ocr_service: Ocr,
    req: Request,
):
    try:
        token = None
        auth_header = req.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]
        else:
            token = req.query_params.get("token")

        if not token:
            Logger.error("No token provided for OCR")
            raise HTTPException(status_code=401, detail="Token required")

        user_result = await auth_service.get_user_by_token(token)
        if user_result.is_err():
            Logger.error(f"Invalid token for OCR: {user_result.unwrap_err()}")
            raise HTTPException(status_code=401, detail="Invalid token")

        current_user = user_result.unwrap()
        Logger.info(f"OCR request from user: {current_user.tg_id}")

        container_id = request.get("container_id")
        file_data_base64 = request.get("file_data")
        file_name = request.get("file_name")
        mime_type = request.get("mime_type", "image/jpeg")

        Logger.info(f"Container ID: {container_id}")
        Logger.info(f"File name: {file_name}")
        Logger.info(f"MIME type: {mime_type}")
        Logger.info(
            f"File data length: {len(file_data_base64) if file_data_base64 else 0}"
        )

        if not container_id:
            Logger.error("Container ID is missing")
            raise HTTPException(status_code=400, detail="Container ID is required")

        if not file_data_base64:
            Logger.error("File data is missing")
            raise HTTPException(status_code=400, detail="File data is required")

        if not file_name:
            Logger.error("File name is missing")
            raise HTTPException(status_code=400, detail="File name is required")

        container_result = await container_service.get_container(container_id)
        if container_result.is_err() or not container_result.unwrap():
            Logger.error(f"Container not found: {container_id}")
            raise HTTPException(status_code=404, detail="Container not found")

        container = container_result.unwrap()
        if container.user_id != str(current_user.tg_id) and not current_user.is_admin:
            Logger.error(
                f"Access denied for user {current_user.tg_id} to container {container_id}"
            )
            raise HTTPException(status_code=403, detail="Access denied")

        try:
            file_data = base64.b64decode(file_data_base64)
        except Exception as e:
            Logger.error(f"Failed to decode base64 file data: {e}")
            raise HTTPException(status_code=400, detail="Invalid file data encoding")

        Logger.info(f"File decoded: {file_name}, size: {len(file_data)} bytes")

        if len(file_data) == 0:
            Logger.error("Empty file received")
            raise HTTPException(status_code=400, detail="Empty file")

        supported_formats = [".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".pdf"]
        if not any(file_name.lower().endswith(ext) for ext in supported_formats):
            Logger.error(f"Unsupported file format: {file_name}")
            raise HTTPException(
                status_code=400,
                detail="Unsupported file format. Only images and PDF are supported",
            )

        Logger.info(
            f"OCR processing for user {current_user.tg_id}, file: {file_name}, size: {len(file_data)} bytes"
        )

        ocr_result = await ocr_service.extract_from_bytes(file_data, file_name)

        if ocr_result.is_err():
            error = ocr_result.unwrap_err()
            Logger.error(f"OCR processing failed: {error}")
            raise HTTPException(
                status_code=500, detail=f"OCR processing failed: {str(error)}"
            )

        extracted_text = ocr_result.unwrap()
        Logger.info(f"OCR completed, extracted {len(extracted_text)} characters")

        cleaned_text = ocr_service.clean_html_tags(extracted_text)
        Logger.info(f"After cleaning: {len(cleaned_text)} characters")

        visualized_data = None
        boxes_count = 0

        if file_name.lower().endswith(
            (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff")
        ):
            try:
                visualized_data = ocr_service.draw_bounding_boxes(
                    file_data, extracted_text
                )
                boxes = ocr_service.parse_bounding_boxes(extracted_text)
                boxes_count = len(boxes)
                Logger.info(
                    f"Generated visualization with {boxes_count} bounding boxes"
                )
            except Exception as e:
                Logger.warning(f"Could not generate visualization: {e}")
                visualized_data = None

        result_file_name = f"ocr_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file_name.split('.')[0]}.txt"

        api_result = await api_service.create_file(
            path=result_file_name,
            content=cleaned_text,
            user_id=str(current_user.id),
            container_id=container_id,
        )

        if api_result.is_err():
            Logger.error(
                f"Failed to save OCR result to container: {api_result.unwrap_err()}"
            )

        response_data = {
            "text": cleaned_text,
            "confidence": 0.95,
            "processing_time": 0,
            "file_name": file_name,
            "extracted_text_length": len(cleaned_text),
            "boxes_count": boxes_count,
            "has_visualization": visualized_data is not None,
        }

        if visualized_data:
            response_data["visualization"] = base64.b64encode(visualized_data).decode(
                "utf-8"
            )
            response_data["visualization_format"] = "image/jpeg"

        Logger.info(
            f"OCR processing completed successfully for user {current_user.tg_id}"
        )

        return {"data": response_data}

    except HTTPException:
        raise
    except Exception as e:
        Logger.error(f"Unexpected error in OCR processing: {e}")
        import traceback

        Logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@http_router.post("/chat")
@inject("api_service")
@inject("container_service")
@inject("auth_service")
@inject("agent_service")
@inject("deepseek_agent_service")
async def chat_with_bot(
    request: dict,
    req: Request,
    api_service: ApiService,
    container_service: ContainerService,
    auth_service: AuthService,
    agent_service: AgentService,
    deepseek_agent_service: AgentService,
):
    token = None
    auth_header = req.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:]
    else:
        token = req.query_params.get("token")
        Logger.error(f"Query token: {req.query_params.get('token')}")

    if not token:
        Logger.error("No token provided")
        raise HTTPException(status_code=401, detail="Token required")

    user_result = await auth_service.get_user_by_token(token)
    if user_result.is_err():
        Logger.error(f"Invalid token: {user_result.unwrap_err()}")
        raise HTTPException(status_code=401, detail="Invalid token")

    current_user = user_result.unwrap()

    query = request.get("query", "").strip()
    container_id = request.get("container_id")
    conversation_history = request.get("conversation_history", [])
    model = request.get("model", 0)
    limit = request.get("limit", 5)

    if not query:
        raise HTTPException(status_code=400, detail="Query is required")

    if not container_id:
        raise HTTPException(status_code=400, detail="Container ID is required")

    container_result = await container_service.get_container(container_id)
    if container_result.is_err() or not container_result.unwrap():
        raise HTTPException(status_code=404, detail="Container not found")

    container = container_result.unwrap()

    search_result = await api_service.semantic_search(
        query,
        current_user,
        container,
        limit,
    )

    if search_result.is_err():
        raise HTTPException(
            status_code=500, detail=f"Search error: {search_result.unwrap_err()}"
        )

    search_data = search_result.unwrap()

    context_parts = []
    used_files = []

    for file_info in search_data.get("results", []):
        file_path = file_info.get("path", "")

        file_id = file_path.split("/")[-1] if "/" in file_path else file_path

        content_result = await api_service.get_file_content(file_id, container_id)

        content_snippet = ""
        if content_result.is_ok():
            content_data = content_result.unwrap()
            if isinstance(content_data, str):
                content_snippet = content_data
            elif isinstance(content_data, dict) and "content" in content_data:
                content_snippet = content_data["content"]
            elif isinstance(content_data, dict) and "data" in content_data:
                content_data_inner = content_data["data"]
                if (
                    isinstance(content_data_inner, dict)
                    and "content" in content_data_inner
                ):
                    content_snippet = content_data_inner["content"]
                elif isinstance(content_data_inner, str):
                    content_snippet = content_data_inner

        else:
            Logger.warning(
                f"Could not get content for file {file_id}: {content_result.unwrap_err()}"
            )

        file_name = file_path.split("/")[-1] if "/" in file_path else file_id

        context_parts.append(f"File: {file_name}")
        context_parts.append(f"Path: {file_path}")
        if content_snippet:
            context_parts.append(f"Content: {content_snippet}")
        else:
            context_parts.append("Content: [No content available or file is empty]")
        context_parts.append("---")

        used_files.append(
            {
                "file_path": file_path,
                "file_name": file_name,
                "relevance_score": file_info.get("score", 0.0),
                "content_snippet": content_snippet if content_snippet else "",
            }
        )

    context = "\n".join(context_parts) if context_parts else "No relevant files found."

    system_prompt = f"""You are an AI assistant that helps users analyze their files. 

    Context from files:
    {context}

    User question: {query}

    Analyze the file contents and provide a helpful response. If the files don't contain relevant information, explain this politely and suggest what the user can do next."""

    chat_result = match(
        model,
        0,
        await agent_service.chat(
            message=query,
            conversation_history=conversation_history,
            user=current_user,
            system_prompt=system_prompt,
        ),
        1,
        await deepseek_agent_service.chat(
            message=query,
            conversation_history=conversation_history,
            user=current_user,
            system_prompt=system_prompt,
        ),
    )

    if chat_result.is_err():
        error_msg = str(chat_result.unwrap_err())
        print(f"Chat error: {error_msg}")
        Logger.error(f"Chat error: {error_msg}")
        raise HTTPException(status_code=500, detail=f"Chat error: {error_msg}")

    chat_response = chat_result.unwrap()

    return {
        "data": {
            "answer": chat_response.get("content", ""),
            "used_files": used_files,
            "conversation_history": chat_response.get("conversation_history", []),
            "model": chat_response.get("model", ""),
            "metadata": chat_response.get("metadata", {}),
        }
    }


@http_router.post("/search/semantic")
@inject("api_service")
@inject("container_service")
@inject("auth_service")
async def semantic_search(
    request: dict,
    req: Request,
    api_service: ApiService,
    container_service: ContainerService,
    auth_service: AuthService,
):
    token = None
    auth_header = req.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:]
    else:
        token = req.query_params.get("token")
        Logger.error(f"Query token: {req.query_params.get('token')}")

    if not token:
        Logger.error("No token provided")
        raise HTTPException(status_code=401, detail="Token required")

    user_result = await auth_service.get_user_by_token(token)
    if user_result.is_err():
        Logger.error(f"Invalid token: {user_result.unwrap_err()}")
        raise HTTPException(status_code=401, detail="Invalid token")

    current_user = user_result.unwrap()

    query = request.get("query", "").strip()
    container_id = request.get("container_id")
    limit = request.get("limit", 10)

    if not query:
        raise HTTPException(status_code=400, detail="Query is required")

    if not container_id:
        raise HTTPException(status_code=400, detail="Container ID is required")

    container_result = await container_service.get_container(container_id)
    if container_result.is_err() or not container_result.unwrap():
        raise HTTPException(status_code=404, detail="Container not found")

    container = container_result.unwrap()
    # if container.user_id != str(current_user.tg_id) and not current_user.is_admin:
    #     raise HTTPException(status_code=403, detail="Access denied")

    search_result = await api_service.semantic_search(
        query,
        current_user,
        container,
        limit=limit,
    )

    if search_result.is_err():
        raise HTTPException(
            status_code=500, detail=f"Search error: {search_result.unwrap_err()}"
        )

    return {"data": search_result.unwrap()}


@http_router.delete("/containers/{container_id}")
@inject("container_service")
@inject("auth_service")
async def delete_container(
    container_id: str,
    container_service: ContainerService,
    auth_service: AuthService,
    request: Request,
):
    token = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:]
    else:
        token = request.query_params.get("token")
        Logger.error(f"Query token: {request.query_params.get('token')}")

    if not token:
        Logger.error("No token provided")
        raise HTTPException(status_code=401, detail="Token required")

    user_result = await auth_service.get_user_by_token(token)
    if user_result.is_err():
        Logger.error(f"Invalid token: {user_result.unwrap_err()}")
        raise HTTPException(status_code=401, detail="Invalid token")

    container_result = await container_service.get_container(container_id)

    if container_result.is_err() or not container_result.unwrap():
        raise HTTPException(status_code=404, detail="Container not found")

    delete_result = await container_service.delete_container(
        (user_result.unwrap().id), container_id
    )

    if delete_result.is_err():
        raise HTTPException(status_code=500, detail="Error deleting container")

    return {"message": "Container deleted successfully"}
