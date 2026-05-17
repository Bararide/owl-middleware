from datetime import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastbot.logger.logger import Logger
import json

router = APIRouter(tags=["websocket"])


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    auth_service = websocket.app.state.auth_service
    container_service = websocket.app.state.container_service
    api_service = websocket.app.state.api_service
    group_service = websocket.app.state.group_service
    ws_manager = websocket.app.state.ws_manager

    token = websocket.query_params.get("token")
    container_id = websocket.query_params.get("container_id")

    if not token:
        await websocket.close(code=1008, reason="Token required")
        return
    if not container_id:
        await websocket.close(code=1002, reason="container_id required")
        return

    user_result = await auth_service.get_user_by_token(token)
    if user_result.is_err():
        await websocket.close(code=1008, reason="Invalid token")
        return
    current_user = user_result.unwrap()

    container_result = await container_service.get_container(container_id)
    if container_result.is_err() or not container_result.unwrap():
        await websocket.close(code=1003, reason="Container not found")
        return
    container = container_result.unwrap()
    if container.user_id != str(current_user.tg_id) and not current_user.is_admin:
        await websocket.close(code=1003, reason="Access denied")
        return

    await ws_manager.connect(websocket, container_id, str(current_user.tg_id))

    connected_msg = {
        "type": "connected",
        "container_id": container_id,
        "user_id": str(current_user.tg_id),
    }
    await websocket.send_json(connected_msg)

    try:
        while True:
            message = await websocket.receive_json()
            action = message.get("action")
            request_id = message.get("request_id")

            if action == "ping":
                pong_msg = {"type": "pong", "timestamp": datetime.now().isoformat()}
                await websocket.send_json(pong_msg)

            elif action == "get_graph_data":
                try:
                    container_result = await container_service.get_container(
                        container_id
                    )
                    container = container_result.unwrap()
                    graph_result = await api_service.containers.get_semantic_graph(
                        current_user, container
                    )
                    if graph_result.is_ok():
                        raw = graph_result.unwrap()
                        nodes = raw.get("nodes", []) if isinstance(raw, dict) else []
                        raw_edges = (
                            (
                                raw.get("edges")
                                or raw.get("links")
                                or raw.get("graph")
                                or []
                            )
                            if isinstance(raw, dict)
                            else (raw if isinstance(raw, list) else [])
                        )
                        edges = []
                        for e in raw_edges:
                            src = e.get("source") or e.get("from")
                            tgt = e.get("target") or e.get("to")
                            if src and tgt:
                                edges.append(
                                    {
                                        "source": src,
                                        "target": tgt,
                                        "weight": e.get("scope")
                                        or e.get("weight")
                                        or 1,
                                        "bidirectional": e.get("bidirectional")
                                        or e.get("reverse")
                                        or False,
                                    }
                                )
                        response = {
                            "type": "graph_data",
                            "request_id": request_id,
                            "data": {
                                "nodes": nodes,
                                "edges": edges,
                                "container_id": container_id,
                                "success": True,
                                "count": len(nodes),
                            },
                        }
                    else:
                        err = str(graph_result.unwrap_err())
                        response = {
                            "type": "graph_data",
                            "request_id": request_id,
                            "data": {
                                "nodes": [],
                                "edges": [],
                                "container_id": container_id,
                                "success": False,
                                "error": err,
                            },
                        }
                except Exception as e:
                    response = {
                        "type": "graph_data",
                        "request_id": request_id,
                        "data": {
                            "nodes": [],
                            "edges": [],
                            "container_id": container_id,
                            "success": False,
                            "error": f"{type(e).__name__}: {e}",
                        },
                    }
                await websocket.send_json(response)

            elif action == "get_groups":
                try:
                    groups_result = await group_service.get_groups_by_container(
                        container_id
                    )
                    if groups_result.is_ok():
                        groups = [
                            {
                                "id": g.id,
                                "container_id": g.container_id,
                                "description": g.description,
                                "created_at": (
                                    g.created_at.isoformat() if g.created_at else None
                                ),
                                "color": g.color or "#ff9800",
                            }
                            for g in groups_result.unwrap()
                        ]
                        await websocket.send_json(
                            {
                                "type": "groups_data",
                                "request_id": request_id,
                                "data": groups,
                            }
                        )
                    else:
                        await websocket.send_json(
                            {
                                "type": "groups_data",
                                "request_id": request_id,
                                "data": [],
                            }
                        )
                except Exception as e:
                    await websocket.send_json(
                        {"type": "groups_data", "request_id": request_id, "data": []}
                    )

            elif action == "get_file_groups_map":
                try:
                    file_groups_map = {}
                    groups_result = await group_service.get_groups_by_container(
                        container_id
                    )
                    if groups_result.is_ok():
                        for group in groups_result.unwrap():
                            files_result = await group_service.get_files_by_group(
                                group.id
                            )
                            if files_result.is_ok():
                                for f in files_result.unwrap():
                                    fp = f.id or f.name
                                    if fp:
                                        if fp not in file_groups_map:
                                            file_groups_map[fp] = []
                                        file_groups_map[fp].append(
                                            {
                                                "groupId": group.id,
                                                "color": group.color or "#ff9800",
                                            }
                                        )

                    await websocket.send_json(
                        {
                            "type": "file_groups_map_data",
                            "request_id": request_id,
                            "data": {
                                "container_id": container_id,
                                "file_groups_map": file_groups_map,
                            },
                        }
                    )
                except Exception as e:
                    await websocket.send_json(
                        {
                            "type": "file_groups_map_data",
                            "request_id": request_id,
                            "data": {
                                "container_id": container_id,
                                "file_groups_map": {},
                            },
                        }
                    )

            elif action == "subscribe_to_graph_updates":
                await websocket.send_json(
                    {
                        "type": "subscribed",
                        "request_id": request_id,
                        "container_id": container_id,
                    }
                )

            elif action == "unsubscribe_from_graph_updates":
                await websocket.send_json(
                    {
                        "type": "unsubscribed",
                        "request_id": request_id,
                        "container_id": container_id,
                    }
                )

            else:
                await websocket.send_json(
                    {
                        "type": "error",
                        "request_id": request_id,
                        "message": f"Unknown action: {action}",
                    }
                )

    except WebSocketDisconnect:
        Logger.info("=== WebSocket disconnected by client ===")
    except Exception as e:
        Logger.error(f"=== WebSocket loop error: {type(e).__name__}: {e} ===")
    finally:
        ws_manager.disconnect(websocket)
        Logger.info("=== WebSocket cleanup done ===")
