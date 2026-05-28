from datetime import datetime
from typing import Container

from fastapi import HTTPException, Request
from fastbot.logger import Logger
from services import AuthService, ApiService, ContainerService
from models import User


async def get_current_user_from_request(
    request: Request,
    auth_service: AuthService,
) -> User:
    token = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:]
    else:
        token = request.query_params.get("token")

    if not token:
        raise HTTPException(status_code=401, detail="Token required")

    user_result = await auth_service.get_user_by_token(token)
    if user_result.is_err():
        raise HTTPException(status_code=401, detail="Invalid token")

    return user_result.unwrap()


async def get_current_container(
    request: Request, container_service: ContainerService
) -> Container:
    container_id = request.query_params.get("container_id")
    if not container_id:
        raise HTTPException(status_code=400, detail="Container ID is required")

    container_result = await container_service.get_container(container_id)
    if container_result.is_err() or not container_result.unwrap():
        raise HTTPException(status_code=404, detail="Container not found")

    return container_result.unwrap()


async def get_container_status(
    api_service: ApiService, user_id: int, container_id: str
) -> str:
    status_result = await api_service.containers.get_containers_status(
        user_id, [container_id]
    )
    status_data = status_result.unwrap()

    try:
        if status_data.get("success") and status_data.get("statuses"):
            status_value = status_data["statuses"][0]["status"]
            return "running" if status_value == "1" else "stopped"
    except (KeyError, IndexError, TypeError) as e:
        Logger.error(f"Error parsing container status: {e}")

    return "stopped"


async def get_container_stats(
    container_service: ContainerService, user_id: str, container_id: str
) -> dict:
    stats_result = await container_service.get_container_stats(user_id, container_id)
    if stats_result.is_ok():
        stats = stats_result.unwrap()
        return {
            "storage_usage_percent": stats.get("storage_usage_percent", 0),
            "total_size": stats.get("total_size", 0),
        }
    return {"storage_usage_percent": 0, "total_size": 0}


async def container_to_response(container: Container, stats: dict, status: str) -> dict:
    """Convert container model to API response"""
    storage_quota_mb = container.tariff.storage_quota
    storage_used = stats.get("total_size", 0)
    storage_usage_percent = stats.get("storage_usage_percent", 0)

    if storage_usage_percent == 0 and storage_quota_mb > 0:
        storage_usage_percent = (storage_used / (storage_quota_mb * 1024 * 1024)) * 100

    memory_usage = 0
    if storage_quota_mb > 0:
        memory_usage = storage_usage_percent / (storage_quota_mb * 1024) * 100
    memory_usage = min(memory_usage, 100)

    return {
        "id": container.id,
        "status": status,
        "memory_limit": container.tariff.memory_limit,
        "storage_quota": storage_quota_mb,
        "file_limit": container.tariff.file_limit,
        "env_label": {
            "key": container.env_label.key,
            "value": container.env_label.value,
        },
        "type_label": {
            "key": container.type_label.key,
            "value": container.type_label.value,
        },
        "created_at": datetime.now().isoformat(),
        "cpu_usage": 10,
        "memory_usage": memory_usage,
        "user_id": container.user_id,
        "commands": container.commands or [],
        "privileged": container.privileged,
        "storage_used": storage_used,
        "storage_usage_percent": storage_usage_percent,
    }
