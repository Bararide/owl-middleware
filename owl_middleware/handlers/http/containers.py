from fastapi import APIRouter, Body, HTTPException, Request
from fastbot.decorators import inject
from fastbot.logger.logger import Logger
from .dependencies import get_current_user_from_request
from services import ContainerService, AuthService, ApiService
from models import User, Container, Tariff, Label
from datetime import datetime

import traceback

router = APIRouter(prefix="/containers", tags=["containers"])


@router.get("")
@inject("container_service")
@inject("auth_service")
@inject("api_service")
async def list_containers(
    container_service: ContainerService,
    auth_service: AuthService,
    api_service: ApiService,
    request: Request,
):
    current_user = await get_current_user_from_request(request, auth_service)

    containers_result = await container_service.get_containers_by_user_id(
        str(current_user.tg_id)
    )
    if containers_result.is_err():
        raise HTTPException(status_code=500, detail="Error fetching containers")

    containers = containers_result.unwrap()
    containers_data = []
    for container in containers:
        stats_result = await container_service.get_container_stats(container.id)
        if stats_result.is_ok():
            stats = stats_result.unwrap()
            storage_usage_percent = stats["storage_usage_percent"]
            total_size = stats["total_size"]
        else:
            storage_usage_percent = 0
            total_size = 0

        containers_data.append(
            {
                "id": container.id,
                "status": await api_service.containers.get_containers_status(
                    current_user.id, [container.id]
                ),
                "memory_limit": container.tariff.memory_limit,
                "storage_quota": container.tariff.storage_quota,
                "file_limit": container.tariff.file_limit,
                "env_label": container.env_label,
                "type_label": container.type_label,
                "created_at": datetime.now().isoformat(),
                "cpu_usage": "10",
                "memory_usage": storage_usage_percent
                / (container.tariff.storage_quota * 1024)
                * 100,
                "user_id": container.user_id,
                "commands": container.commands,
                "privileged": container.privileged,
                "storage_used": total_size,
                "storage_usage_percent": storage_usage_percent,
            }
        )

    return {"data": containers_data}


@router.post("")
@inject("container_service")
@inject("auth_service")
@inject("api_service")
async def create_container(
    request: Request,
    container_service: ContainerService,
    auth_service: AuthService,
    api_service: ApiService,
):
    try:
        body = await request.body()

        import json

        request_data_dict = json.loads(body)
        current_user = await get_current_user_from_request(request, auth_service)

        user_id = request_data_dict.get("user_id", str(current_user.tg_id))

        tariff = Tariff(
            memory_limit=request_data_dict["memory_limit"],
            storage_quota=request_data_dict["storage_quota"],
            file_limit=request_data_dict["file_limit"],
        )

        env_label = Label(
            key=request_data_dict["env_label"]["key"],
            value=request_data_dict["env_label"]["value"],
        )

        type_label = Label(
            key=request_data_dict["type_label"]["key"],
            value=request_data_dict["type_label"]["value"],
        )

        container = Container(
            id=request_data_dict["container_id"],
            user_id=user_id,
            tariff=tariff,
            env_label=env_label,
            type_label=type_label,
            privileged=request_data_dict.get("privileged", False),
            commands=request_data_dict.get("commands", []),
        )

        container_data_for_db = {
            "container_id": container.id,
            "user_id": container.user_id,
            "memory_limit": container.tariff.memory_limit,
            "storage_quota": container.tariff.storage_quota,
            "file_limit": container.tariff.file_limit,
            "env_label": {
                "key": container.env_label.key,
                "value": container.env_label.value,
            },
            "type_label": {
                "key": container.type_label.key,
                "value": container.type_label.value,
            },
            "commands": container.commands,
            "privileged": container.privileged,
        }

        container_result = await container_service.create_container(
            container_data_for_db
        )

        if container_result.is_err():
            error = container_result.unwrap_err()
            Logger.error(f"Container creation failed: {error}")
            if "already exists" in str(error).lower():
                raise HTTPException(
                    status_code=409,
                    detail=f"Container with ID '{container.id}' already exists",
                )
            raise HTTPException(
                status_code=500, detail=f"Error creating container: {str(error)}"
            )

        created_container = container_result.unwrap()

        api_result = await api_service.containers.create_container(
            user_id=user_id,
            container_id=container.id,
            tariff=tariff,
            env_label=env_label,
            type_label=type_label,
            commands=container.commands,
            privileged=container.privileged,
        )

        if api_result.is_err():
            error = api_result.unwrap_err()
            Logger.error(f"API service error: {error}")
            await container_service.delete_container(user_id, container.id)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to create container in backend: {str(error)}",
            )

        response_data = {
            "data": {
                "container_id": created_container.id,
                "user_id": created_container.user_id,
                "status": "created",
                "memory_limit": created_container.tariff.memory_limit,
                "storage_quota": created_container.tariff.storage_quota,
                "file_limit": created_container.tariff.file_limit,
                "env_label": {
                    "key": created_container.env_label.key,
                    "value": created_container.env_label.value,
                },
                "type_label": {
                    "key": created_container.type_label.key,
                    "value": created_container.type_label.value,
                },
                "commands": created_container.commands,
                "privileged": created_container.privileged,
                "created_at": datetime.now().isoformat(),
                "cpu_usage": 0,
                "memory_usage": 0,
                "storage_used": 0,
                "storage_usage_percent": 0,
            }
        }

        return response_data

    except HTTPException:
        raise
    except Exception as e:
        Logger.error(f"Unexpected error in create_container: {e}")
        Logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/{container_id}")
@inject("container_service")
@inject("auth_service")
async def get_container(
    container_id: str,
    container_service: ContainerService,
    auth_service: AuthService,
    request: Request,
):
    current_user = await get_current_user_from_request(request, auth_service)

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


@router.delete("/{container_id}")
@inject("container_service")
@inject("auth_service")
async def delete_container(
    container_id: str,
    container_service: ContainerService,
    auth_service: AuthService,
    request: Request,
):
    current_user = await get_current_user_from_request(request, auth_service)

    container_result = await container_service.get_container(container_id)
    if container_result.is_err() or not container_result.unwrap():
        raise HTTPException(status_code=404, detail="Container not found")

    delete_result = await container_service.delete_container(
        current_user.id, container_id
    )
    if delete_result.is_err():
        raise HTTPException(status_code=500, detail="Error deleting container")

    return {"message": "Container deleted successfully"}


@router.get("/metrics/{container_id}")
@inject("container_service")
@inject("api_service")
@inject("auth_service")
async def get_container_metrics(
    container_id: str,
    container_service: ContainerService,
    api_service: ApiService,
    auth_service: AuthService,
    request: Request,
):
    current_user = await get_current_user_from_request(request, auth_service)

    container_result = await container_service.get_container(container_id)
    if container_result.is_err() or not container_result.unwrap():
        raise HTTPException(status_code=404, detail="Container not found")

    container = container_result.unwrap()
    if container.user_id != str(current_user.id) and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Access denied")

    metrics_result = await api_service.get_container_metrics(container_id)
    if metrics_result.is_err():
        raise HTTPException(status_code=500, detail="Error fetching metrics")

    metrics = metrics_result.unwrap()
    return {"data": metrics}


@router.get("/statuses")
@inject("container_service")
@inject("api_service")
@inject("auth_service")
async def get_containers_status(
    container_service: ContainerService,
    api_service: ApiService,
    auth_service: AuthService,
    request: Request,
):
    current_user = await get_current_user_from_request(request, auth_service)

    containers_result = await container_service.get_containers_by_user_id(
        str(current_user.tg_id)
    )

    if containers_result.is_err():
        raise HTTPException(status_code=500, detail="Error fetching containers")

    containers = containers_result.unwrap()
    container_ids = [container.id for container in containers]

    statuses_result = await api_service.get_containers_status(
        current_user.id, container_ids
    )
    if statuses_result.is_err():
        raise HTTPException(status_code=500, detail="Error fetching statuses")

    statuses = statuses_result.unwrap()
    return {"data": statuses}
