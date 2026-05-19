from fastapi import APIRouter, HTTPException, Request
from fastbot.decorators import inject
from fastbot.logger.logger import Logger
from .dependencies import get_current_container, get_current_user_from_request
from services import ApiService, ContainerService, AuthService
from models import User
import logging

router = APIRouter(prefix="/search", tags=["search"])
logger = logging.getLogger(__name__)


@router.post("/semantic")
@inject("api_service")
@inject("container_service")
@inject("auth_service")
async def semantic_search(
    request: Request,
    api_service: ApiService,
    container_service: ContainerService,
    auth_service: AuthService,
):
    user = await get_current_user_from_request(request, auth_service)

    body = await request.json()
    query = body.get("query", "").strip()
    limit = body.get("limit", 10)

    if not query:
        raise HTTPException(status_code=400, detail="Query is required")

    container = await get_current_container(request, container_service)

    search_result = await api_service.containers.semantic_search(
        query, user, container, limit=limit
    )
    if search_result.is_err():
        raise HTTPException(
            status_code=500, detail=f"Search error: {search_result.unwrap_err()}"
        )

    return {"data": search_result.unwrap()}


@router.get("/history")
@inject("api_service")
@inject("container_service")
@inject("auth_service")
async def get_search_history(
    request: Request,
    api_service: ApiService,
    container_service: ContainerService,
    auth_service: AuthService,
):
    user = await get_current_user_from_request(request, auth_service)
    container = await get_current_container(request, container_service)

    maybe_history = await api_service.containers.get_search_history(user, container)

    if maybe_history.is_err():
        raise HTTPException(
            status_code=500,
            detail=f"get search history error: {maybe_history.unwrap_err()}",
        )

    return {"data": maybe_history.unwrap()}


@router.get("/graph")
@inject("api_service")
@inject("container_service")
@inject("auth_service")
async def get_semantic_graph(
    request: Request,
    api_service: ApiService,
    container_service: ContainerService,
    auth_service: AuthService,
):
    user = await get_current_user_from_request(request, auth_service)

    container_id = request.query_params.get("container_id")
    if not container_id:
        raise HTTPException(status_code=400, detail="Container ID is required")

    container_result = await container_service.get_container(container_id)
    if container_result.is_err() or not container_result.unwrap():
        raise HTTPException(status_code=404, detail="Container not found")

    container = container_result.unwrap()

    maybe_graph = await api_service.containers.get_semantic_graph(user, container)

    if maybe_graph.is_err():
        raise HTTPException(
            status_code=500,
            detail=f"get semantic graph error: {maybe_graph.unwrap_err()}",
        )

    return {"data": maybe_graph.unwrap()}
