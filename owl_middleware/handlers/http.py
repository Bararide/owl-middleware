from fastapi import (
    APIRouter,
    HTTPException,
    Request,
    UploadFile,
    File as FastAPIFile,
    Form,
    Depends,
)
from fastapi.responses import StreamingResponse
from typing import List, Optional
import json
from datetime import datetime

from fastbot.decorators import inject
from services import AuthService, FileService, ApiService, ContainerService, TextService
from models import User, Container as ContainerModel, File as FileModel

http_router = APIRouter()


@inject("auth_service")
async def get_current_user(request: Request, auth_service: AuthService) -> User:
    user_id = request.headers.get("X-User-ID")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = await auth_service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user


@http_router.get("/containers")
@inject("container_service")
async def list_containers(
    container_service: ContainerService, current_user: User = Depends(get_current_user)
):
    """Get all containers for current user"""
    containers_result = await container_service.get_containers_by_user_id(
        str(current_user.id)
    )

    if containers_result.is_err():
        raise HTTPException(status_code=500, detail="Error fetching containers")

    containers = containers_result.unwrap()
    return {
        "data": [
            {
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
            for container in containers
        ]
    }


@http_router.get("/containers/{container_id}")
@inject("container_service")
async def get_container(
    container_id: str,
    container_service: ContainerService,
    current_user: User = Depends(get_current_user),
):
    """Get specific container"""
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
async def create_container(
    request: dict,
    container_service: ContainerService,
    api_service: ApiService,
    current_user: User = Depends(get_current_user),
):
    container_data = {
        "user_id": str(current_user.id),
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
        await container_service.delete_container(request["container_id"])
        raise HTTPException(
            status_code=500, detail=f"Service error: {api_result.unwrap_err()}"
        )

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
            "user_id": container.user_id,
            "commands": container.commands,
            "privileged": container.privileged,
        }
    }


@http_router.delete("/containers/{container_id}")
@inject("container_service")
async def delete_container(
    container_id: str,
    container_service: ContainerService,
    current_user: User = Depends(get_current_user),
):
    """Delete container"""
    container_result = await container_service.get_container(container_id)

    if container_result.is_err() or not container_result.unwrap():
        raise HTTPException(status_code=404, detail="Container not found")

    container = container_result.unwrap()

    if container.user_id != str(current_user.id) and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Access denied")

    delete_result = await container_service.delete_container(container_id)

    if delete_result.is_err():
        raise HTTPException(status_code=500, detail="Error deleting container")

    return {"message": "Container deleted successfully"}


# @http_router.post("/containers/{container_id}/restart")
# async def restart_container(
#     container_id: str, current_user: User = Depends(get_current_user)
# ):
#     """Restart container"""
#     # Implement container restart logic
#     return {"message": "Container restart initiated"}


# @http_router.post("/containers/{container_id}/stop")
# async def stop_container(
#     container_id: str, current_user: User = Depends(get_current_user)
# ):
#     """Stop container"""
#     # Implement container stop logic
#     return {"message": "Container stop initiated"}


# # Files endpoints
# @http_router.get("/containers/{container_id}/files")
# async def list_files(
#     container_id: str,
#     current_user: User = Depends(get_current_user),
#     file_service: FileService = Depends(lambda: file_service),
# ):
#     """Get all files in container"""
#     # Verify container ownership
#     container_result = await container_service.get_container(container_id)
#     if container_result.is_err() or not container_result.unwrap():
#         raise HTTPException(status_code=404, detail="Container not found")

#     container = container_result.unwrap()
#     if container.user_id != str(current_user.id) and not current_user.is_admin:
#         raise HTTPException(status_code=403, detail="Access denied")

#     files_result = await file_service.get_files_by_container(container_id)

#     if files_result.is_err():
#         raise HTTPException(status_code=500, detail="Error fetching files")

#     files = files_result.unwrap()
#     return {
#         "data": [
#             {
#                 "id": file.id,
#                 "path": file.path,
#                 "name": file.name,
#                 "size": file.size,
#                 "container_id": file.container_id,
#                 "user_id": file.user_id,
#                 "created_at": file.created_at.isoformat() if file.created_at else None,
#                 "mime_type": file.mime_type,
#             }
#             for file in files
#         ]
#     }


# @http_router.post("/containers/{container_id}/files")
# async def upload_file(
#     container_id: str,
#     file: str = Form(...),
#     content: str = Form(...),
#     current_user: User = Depends(get_current_user),
#     file_service: FileService = Depends(lambda: file_service),
#     api_service: ApiService = Depends(lambda: api_service),
#     text_service: TextService = Depends(lambda: text_service),
# ):
#     """Upload file to container"""
#     # Verify container ownership
#     container_result = await container_service.get_container(container_id)
#     if container_result.is_err() or not container_result.unwrap():
#         raise HTTPException(status_code=404, detail="Container not found")

#     container = container_result.unwrap()
#     if container.user_id != str(current_user.id) and not current_user.is_admin:
#         raise HTTPException(status_code=403, detail="Access denied")

#     file_data = json.loads(file)

#     # Create file record in database
#     db_result = await file_service.create_file(
#         {
#             "id": file_data["id"],
#             "container_id": container_id,
#             "name": file_data["name"],
#             "size": file_data["size"],
#             "user_id": str(current_user.id),
#             "created_at": datetime.now(),
#             "mime_type": file_data.get("mime_type", "application/octet-stream"),
#         }
#     )

#     if db_result.is_err():
#         raise HTTPException(
#             status_code=500, detail=f"Database error: {db_result.unwrap_err()}"
#         )

#     file_obj = db_result.unwrap()

#     # Upload to C++ service
#     api_result = await api_service.create_file(
#         path=file_obj.id,
#         content=content,
#         user_id=str(current_user.id),
#         container_id=container_id,
#     )

#     if api_result.is_err():
#         # Rollback database creation
#         await file_service.delete_file(file_obj.id)
#         raise HTTPException(
#             status_code=500, detail=f"Service error: {api_result.unwrap_err()}"
#         )

#     return {
#         "data": {
#             "id": file_obj.id,
#             "path": file_obj.path,
#             "name": file_obj.name,
#             "size": file_obj.size,
#             "container_id": file_obj.container_id,
#             "user_id": file_obj.user_id,
#             "created_at": (
#                 file_obj.created_at.isoformat() if file_obj.created_at else None
#             ),
#             "mime_type": file_obj.mime_type,
#         }
#     }


# @http_router.get("/containers/{container_id}/files/{file_id}/content")
# async def read_file_content(
#     container_id: str,
#     file_id: str,
#     current_user: User = Depends(get_current_user),
#     api_service: ApiService = Depends(lambda: api_service),
# ):
#     """Read file content"""
#     # Verify container and file ownership
#     container_result = await container_service.get_container(container_id)
#     if container_result.is_err() or not container_result.unwrap():
#         raise HTTPException(status_code=404, detail="Container not found")

#     container = container_result.unwrap()
#     if container.user_id != str(current_user.id) and not current_user.is_admin:
#         raise HTTPException(status_code=403, detail="Access denied")

#     content_result = await api_service.get_file_content(file_id, container_id)

#     if content_result.is_err():
#         raise HTTPException(
#             status_code=500, detail=f"Error reading file: {content_result.unwrap_err()}"
#         )

#     return {"data": {"content": content_result.unwrap()}}


# @http_router.get("/containers/{container_id}/files/{file_id}/download")
# async def download_file(
#     container_id: str,
#     file_id: str,
#     current_user: User = Depends(get_current_user),
#     api_service: ApiService = Depends(lambda: api_service),
# ):
#     """Download file"""
#     # Verify container and file ownership
#     container_result = await container_service.get_container(container_id)
#     if container_result.is_err() or not container_result.unwrap():
#         raise HTTPException(status_code=404, detail="Container not found")

#     container = container_result.unwrap()
#     if container.user_id != str(current_user.id) and not current_user.is_admin:
#         raise HTTPException(status_code=403, detail="Access denied")

#     content_result = await api_service.get_file_content(file_id, container_id)

#     if content_result.is_err():
#         raise HTTPException(
#             status_code=500, detail=f"Error reading file: {content_result.unwrap_err()}"
#         )

#     content = content_result.unwrap()

#     # Determine filename and content type
#     file_result = await file_service.get_file(file_id)
#     if file_result.is_ok() and file_result.unwrap():
#         file_obj = file_result.unwrap()
#         filename = file_obj.name or f"file_{file_id}"
#         mime_type = file_obj.mime_type or "application/octet-stream"
#     else:
#         filename = f"file_{file_id}"
#         mime_type = "application/octet-stream"

#     # Return as downloadable file
#     return StreamingResponse(
#         iter([content.encode("utf-8")]),
#         media_type=mime_type,
#         headers={"Content-Disposition": f"attachment; filename={filename}"},
#     )


# @http_router.delete("/containers/{container_id}/files/{file_id}")
# async def delete_file(
#     container_id: str,
#     file_id: str,
#     current_user: User = Depends(get_current_user),
#     file_service: FileService = Depends(lambda: file_service),
# ):
#     """Delete file"""
#     # Verify container and file ownership
#     container_result = await container_service.get_container(container_id)
#     if container_result.is_err() or not container_result.unwrap():
#         raise HTTPException(status_code=404, detail="Container not found")

#     container = container_result.unwrap()
#     if container.user_id != str(current_user.id) and not current_user.is_admin:
#         raise HTTPException(status_code=403, detail="Access denied")

#     file_result = await file_service.get_file(file_id)
#     if file_result.is_err() or not file_result.unwrap():
#         raise HTTPException(status_code=404, detail="File not found")

#     file_obj = file_result.unwrap()
#     if file_obj.user_id != str(current_user.id) and not current_user.is_admin:
#         raise HTTPException(status_code=403, detail="Access denied")

#     delete_result = await file_service.delete_file(file_id)

#     if delete_result.is_err():
#         raise HTTPException(status_code=500, detail="Error deleting file")

#     return {"message": "File deleted successfully"}


# # Search endpoints
# @http_router.post("/search/semantic")
# async def semantic_search(
#     request: dict,
#     current_user: User = Depends(get_current_user),
#     api_service: ApiService = Depends(lambda: api_service),
#     container_service: ContainerService = Depends(lambda: container_service),
# ):
#     """Perform semantic search"""
#     query = request.get("query", "").strip()
#     container_id = request.get("container_id")
#     limit = request.get("limit", 10)

#     if not query:
#         raise HTTPException(status_code=400, detail="Query is required")

#     if not container_id:
#         raise HTTPException(status_code=400, detail="Container ID is required")

#     # Verify container ownership
#     container_result = await container_service.get_container(container_id)
#     if container_result.is_err() or not container_result.unwrap():
#         raise HTTPException(status_code=404, detail="Container not found")

#     container = container_result.unwrap()
#     if container.user_id != str(current_user.id) and not current_user.is_admin:
#         raise HTTPException(status_code=403, detail="Access denied")

#     search_result = await api_service.semantic_search(
#         query,
#         current_user,
#         container,
#         limit=limit,
#     )

#     if search_result.is_err():
#         raise HTTPException(
#             status_code=500, detail=f"Search error: {search_result.unwrap_err()}"
#         )

#     return {"data": search_result.unwrap()}


# @http_router.post("/search/rebuild-index")
# async def rebuild_index(
#     current_user: User = Depends(get_current_user),
#     api_service: ApiService = Depends(lambda: api_service),
# ):
#     """Rebuild search index (admin only)"""
#     if not current_user.is_admin:
#         raise HTTPException(status_code=403, detail="Insufficient permissions")

#     rebuild_result = await api_service.rebuild_index()

#     if rebuild_result.is_err():
#         raise HTTPException(
#             status_code=500, detail=f"Rebuild error: {rebuild_result.unwrap_err()}"
#         )

#     return {"data": rebuild_result.unwrap()}


# @http_router.get("/health")
# @inject("api_service")
# async def health_check(api_service: ApiService):
#     """Health check"""
#     health_result = await api_service.health_check()

#     if health_result.is_err():
#         return {"data": {"status": "offline", "error": str(health_result.unwrap_err())}}

#     is_healthy = health_result.unwrap()
#     return {"data": {"status": "online" if is_healthy else "offline"}}


# @http_router.get("/system/status")
# async def system_status(
#     current_user: User = Depends(get_current_user),
#     api_service: ApiService = Depends(lambda: api_service),
# ):
#     if not current_user.is_admin:
#         raise HTTPException(status_code=403, detail="Insufficient permissions")

#     health_result = await api_service.health_check()
#     root_result = await api_service.get_root()

#     status_data = {
#         "service_status": (
#             "online" if health_result.is_ok() and health_result.unwrap() else "offline"
#         ),
#     }

#     if root_result.is_ok():
#         status_data["root_message"] = root_result.unwrap().get("message", "No message")

#     return {"data": status_data}
