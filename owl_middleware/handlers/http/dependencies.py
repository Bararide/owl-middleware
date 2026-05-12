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
    container_service: ContainerService, container_id: str
) -> dict:
    stats_result = await container_service.get_container_stats(container_id)
    if stats_result.is_ok():
        stats = stats_result.unwrap()
        return {
            "storage_usage_percent": stats["storage_usage_percent"],
            "total_size": stats["total_size"],
        }
    return {"storage_usage_percent": 0, "total_size": 0}


async def container_to_response(container: Container, stats: dict, status: str) -> dict:
    """Convert container model to API response"""
    return {
        "id": container.id,
        "status": status,
        "memory_limit": container.tariff.memory_limit,
        "storage_quota": container.tariff.storage_quota,
        "file_limit": container.tariff.file_limit,
        "env_label": container.env_label,
        "type_label": container.type_label,
        "created_at": datetime.now().isoformat(),
        "cpu_usage": "10",
        "memory_usage": stats["storage_usage_percent"]
        / (container.tariff.storage_quota * 1024)
        * 100,
        "user_id": container.user_id,
        "commands": container.commands,
        "privileged": container.privileged,
        "storage_used": stats["total_size"],
        "storage_usage_percent": stats["storage_usage_percent"],
    }
