# websocket_routes.py
from datetime import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastbot.logger.logger import Logger
import json

router = APIRouter(tags=["websocket"])


# websocket_routes.py
@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    Logger.info("WebSocket connection accepted")

    try:
        auth_service = websocket.app.state.auth_service
        container_service = websocket.app.state.container_service
        ws_manager = websocket.app.state.ws_manager

        token = websocket.query_params.get("token")
        container_id = websocket.query_params.get("container_id")

        if not token:
            await websocket.close(code=1008, reason="Token required")
            return

        if not container_id:
            await websocket.close(
                code=1002, reason="container_id required in query params"
            )
            return

        user_result = await auth_service.get_user_by_token(token)
        if user_result.is_err():
            await websocket.close(code=1008, reason="Invalid token")
            return

        current_user = user_result.unwrap()
        Logger.info(f"User authenticated: {current_user.tg_id}")

        container_result = await container_service.get_container(container_id)
        if container_result.is_err() or not container_result.unwrap():
            await websocket.close(code=1003, reason="Container not found")
            return

        container = container_result.unwrap()
        if container.user_id != str(current_user.tg_id) and not current_user.is_admin:
            await websocket.close(code=1003, reason="Access denied")
            return

        await ws_manager.connect(websocket, container_id, str(current_user.tg_id))

        Logger.info(
            f"WebSocket connected: user={current_user.tg_id}, container={container_id}"
        )

        await websocket.send_json(
            {
                "type": "connected",
                "container_id": container_id,
                "user_id": str(current_user.tg_id),
            }
        )

        while True:
            try:
                message = await websocket.receive_json()
                action = message.get("action")

                if action == "ping":
                    await websocket.send_json(
                        {"type": "pong", "timestamp": datetime.now().isoformat()}
                    )
                elif action == "subscribe":
                    new_container_id = message.get("container_id")
                    if new_container_id and new_container_id != container_id:
                        new_container_result = await container_service.get_container(
                            new_container_id
                        )
                        if (
                            new_container_result.is_ok()
                            and new_container_result.unwrap()
                        ):
                            new_container = new_container_result.unwrap()
                            if (
                                new_container.user_id == str(current_user.tg_id)
                                or current_user.is_admin
                            ):
                                ws_manager.disconnect(websocket)
                                await ws_manager.connect(
                                    websocket, new_container_id, str(current_user.tg_id)
                                )
                                container_id = new_container_id
                                await websocket.send_json(
                                    {"type": "subscribed", "container_id": container_id}
                                )
                else:
                    await websocket.send_json(
                        {"type": "error", "message": f"Unknown action: {action}"}
                    )

            except json.JSONDecodeError:
                Logger.warning(f"Received non-JSON message")
                continue

    except WebSocketDisconnect:
        if (
            "ws_manager" in locals()
            and ws_manager
            and "current_user" in locals()
            and current_user
        ):
            ws_manager.disconnect(websocket)
        Logger.info("WebSocket disconnected")
    except Exception as e:
        Logger.error(f"WebSocket error: {e}")
        if (
            "ws_manager" in locals()
            and ws_manager
            and "current_user" in locals()
            and current_user
        ):
            ws_manager.disconnect(websocket)
        try:
            await websocket.close(code=1011, reason="Internal server error")
        except:
            pass
