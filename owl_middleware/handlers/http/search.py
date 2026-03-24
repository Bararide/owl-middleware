from fastapi import APIRouter, HTTPException, Request
from fastbot.decorators import inject
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

    if not token:
        raise HTTPException(status_code=401, detail="Token required")

    user_result = await auth_service.get_user_by_token(token)
    if user_result.is_err():
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

    search_result = await api_service.containers.semantic_search(
        query, current_user, container, limit=limit
    )
    if search_result.is_err():
        logger.error(f"SEMANTIC SEARCH ERROR: {search_result.unwrap_err()}")
        raise HTTPException(
            status_code=500, detail=f"Search error: {search_result.unwrap_err()}"
        )

    return {"data": search_result.unwrap()}


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

    current_user = user_result.unwrap()

    container_id = request.query_params.get("container_id")
    if not container_id:
        raise HTTPException(status_code=400, detail="Container ID is required")

    container_result = await container_service.get_container(container_id)
    if container_result.is_err() or not container_result.unwrap():
        raise HTTPException(status_code=404, detail="Container not found")

    container = container_result.unwrap()

    maybe_graph = await api_service.containers.get_semantic_graph(
        current_user, container
    )
    if maybe_graph.is_err():
        logger.error(f"ERROR IN GET SEMANTIC GRAPH {maybe_graph.unwrap_err()}")
        raise HTTPException(
            status_code=500,
            detail=f"get semantic graph error: {maybe_graph.unwrap_err()}",
        )

    return {"data": maybe_graph.unwrap()}
