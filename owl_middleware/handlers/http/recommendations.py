import asyncio
import json
from typing import List
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse
from fastbot.decorators import inject
from services import ApiService, ContainerService, AuthService
from models import User
import logging

router = APIRouter(prefix="/recommendations", tags=["recommendations"])
logger = logging.getLogger(__name__)


@router.get("/stream")
@inject("auth_service")
@inject("container_service")
@inject("api_service")
async def recommendations_stream(
    request: Request,
    auth_service: AuthService,
    container_service: ContainerService,
    api_service: ApiService,
):
    logger.info("RECOMMENDATIONS STREAM")
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
        raise HTTPException(status_code=400, detail="container_id is required")

    container_result = await container_service.get_container(container_id)
    if container_result.is_err() or not container_result.unwrap():
        raise HTTPException(status_code=404, detail="Container not found")

    container = container_result.unwrap()
    if container.user_id != str(current_user.tg_id) and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Access denied")

    async def event_generator():
        stream_id = None
        sent_paths = set()
        try:
            queue = asyncio.Queue()

            def on_paths(container_id: str, user_id: str, paths: List[str]):
                new_paths = [p for p in paths if p not in sent_paths]
                if new_paths:
                    sent_paths.update(new_paths)
                    event_data = {
                        "container_id": container_id,
                        "user_id": user_id,
                        "paths": new_paths,
                        "total_paths": list(sent_paths),
                        "type": "paths_update",
                    }
                    asyncio.create_task(queue.put(("data", event_data)))

            def on_complete():
                final_data = {
                    "container_id": container_id,
                    "user_id": str(current_user.id),
                    "paths": list(sent_paths),
                    "type": "complete",
                    "count": len(sent_paths),
                }
                asyncio.create_task(queue.put(("data", final_data)))
                asyncio.create_task(queue.put(("event", "end")))

            result = await api_service.recommendations.get_recommendations_stream(
                user_id=str(current_user.id),
                container_id=container_id,
                on_paths=on_paths,
                on_complete=on_complete,
            )

            if result.is_err():
                error_msg = (
                    f"Failed to create recommendation stream: {result.unwrap_err()}"
                )
                logger.error(error_msg)
                yield f"event: error\ndata: {json.dumps({'error': error_msg})}\n\n"
                return

            stream_id = result.unwrap()
            logger.info(f"Recommendation stream created: {stream_id}")
            yield f"event: connected\ndata: {json.dumps({'stream_id': stream_id, 'container_id': container_id})}\n\n"

            while True:
                try:
                    event_type, data = await asyncio.wait_for(queue.get(), timeout=60)
                    if event_type == "data":
                        logger.info(f"{json.dumps(data)}")
                        yield f"data: {json.dumps(data)}\n\n"
                    elif event_type == "event" and data == "end":
                        yield f"event: end\n\n"
                        break
                except asyncio.TimeoutError:
                    yield f": heartbeat\n\n"
                    continue

        except Exception as e:
            logger.error(f"Error in recommendations stream: {e}")
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

    origin = request.headers.get("origin", "http://localhost:3001")
    response = StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "Authorization, Content-Type, Accept",
        },
    )
    return response


@router.options("/stream")
async def recommendations_stream_options(request: Request):
    origin = request.headers.get("origin", "http://localhost:3001")
    headers = {
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Credentials": "true",
        "Access-Control-Allow-Methods": "GET, OPTIONS",
        "Access-Control-Allow-Headers": "Authorization, Content-Type, Accept",
        "Access-Control-Max-Age": "3600",
    }
    return JSONResponse(content={}, headers=headers)
