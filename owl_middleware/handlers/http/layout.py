from datetime import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastbot.logger.logger import Logger
import asyncio

from models.roles.user_role import UserRole

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

    if (
        container.user_id != str(current_user.tg_id)
        and not current_user.role == UserRole.admin
    ):

        await websocket.close(code=1003, reason="Access denied")
        return

    await api_service.recommendations.stream_manager.reset()
    await api_service.logs.stream_manager.reset()

    await ws_manager.connect(websocket, container_id, str(current_user.tg_id))

    recommendation_stream_id = None
    recommendation_task = None
    sent_paths = set()
    recommendation_queue = None

    logs_stream_id = None
    logs_task = None

    connected_msg = {
        "type": "connected",
        "container_id": container_id,
        "user_id": str(current_user.tg_id),
    }
    await websocket.send_json(connected_msg)

    def cleanup_recommendations():
        nonlocal recommendation_task, recommendation_stream_id
        if recommendation_task and not recommendation_task.done():
            recommendation_task.cancel()
        if recommendation_stream_id:
            try:
                asyncio.create_task(
                    api_service.recommendations.close_stream(recommendation_stream_id)
                )
            except:
                pass

    def cleanup_logs():
        nonlocal logs_task, logs_stream_id
        if logs_task and not logs_task.done():
            logs_task.cancel()
        if logs_stream_id:
            try:
                asyncio.create_task(api_service.logs.close_stream(logs_stream_id))
            except:
                pass

    try:
        while True:
            message = await websocket.receive_json()
            action = message.get("action")
            request_id = message.get("request_id")

            if action == "ping":
                pong_msg = {"type": "pong", "timestamp": datetime.now().isoformat()}
                if request_id:
                    pong_msg["request_id"] = request_id
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

            elif action == "get_recommendations":
                cleanup_recommendations()
                sent_paths.clear()
                recommendation_queue = asyncio.Queue()
                timeout = message.get("timeout", 30)

                def on_paths(container_id: str, user_id: str, paths: list):
                    new_paths = [p for p in paths if p not in sent_paths]
                    if new_paths:
                        sent_paths.update(new_paths)
                        asyncio.create_task(
                            recommendation_queue.put(
                                {
                                    "type": "recommendations_update",
                                    "data": {
                                        "paths": new_paths,
                                        "total_paths": list(sent_paths),
                                    },
                                }
                            )
                        )

                def on_complete():
                    asyncio.create_task(
                        recommendation_queue.put({"type": "recommendations_complete"})
                    )

                result = await api_service.recommendations.get_recommendations_stream(
                    user_id=str(current_user.id),
                    container_id=container_id,
                    on_paths=on_paths,
                    on_complete=on_complete,
                )

                if result.is_err():
                    await websocket.send_json(
                        {
                            "type": "recommendations_data",
                            "request_id": request_id,
                            "error": str(result.unwrap_err()),
                            "data": {"paths": []},
                        }
                    )
                else:
                    recommendation_stream_id = result.unwrap()

                    async def send_recommendations():
                        try:
                            while True:
                                try:
                                    msg = await asyncio.wait_for(
                                        recommendation_queue.get(), timeout=timeout
                                    )
                                    if msg["type"] == "recommendations_update":
                                        await websocket.send_json(
                                            {
                                                "type": "recommendations_update",
                                                "request_id": request_id,
                                                "data": msg["data"],
                                            }
                                        )
                                    elif msg["type"] == "recommendations_complete":
                                        await websocket.send_json(
                                            {
                                                "type": "recommendations_data",
                                                "request_id": request_id,
                                                "data": {"paths": list(sent_paths)},
                                            }
                                        )
                                        await websocket.send_json(
                                            {
                                                "type": "recommendations_complete",
                                                "request_id": request_id,
                                            }
                                        )
                                        break
                                except asyncio.TimeoutError:
                                    continue
                        except asyncio.CancelledError:
                            pass

                    recommendation_task = asyncio.create_task(send_recommendations())

            elif action == "get_logs":
                cleanup_logs()

                def on_log(log_message: str):
                    asyncio.create_task(
                        websocket.send_json(
                            {
                                "type": "log_message",
                                "request_id": request_id,
                                "data": {"message": log_message},
                            }
                        )
                    )

                result = await api_service.logs.get_logs_stream(
                    container_id=container_id,
                    on_log=on_log,
                )

                if result.is_err():
                    await websocket.send_json(
                        {
                            "type": "logs_error",
                            "request_id": request_id,
                            "error": str(result.unwrap_err()),
                        }
                    )
                else:
                    logs_stream_id = result.unwrap()

            elif action == "subscribe_to_graph_updates":
                await ws_manager.subscribe(websocket, "graph_updates")
                await websocket.send_json(
                    {
                        "type": "subscribed",
                        "request_id": request_id,
                        "subscription": "graph_updates",
                        "container_id": container_id,
                    }
                )

            elif action == "unsubscribe_from_graph_updates":
                await ws_manager.unsubscribe(websocket, "graph_updates")
                await websocket.send_json(
                    {
                        "type": "unsubscribed",
                        "request_id": request_id,
                        "subscription": "graph_updates",
                        "container_id": container_id,
                    }
                )

            elif action == "subscribe_to_recommendations":
                await ws_manager.subscribe(websocket, "recommendations")
                await websocket.send_json(
                    {
                        "type": "subscribed",
                        "request_id": request_id,
                        "subscription": "recommendations",
                        "container_id": container_id,
                    }
                )

            elif action == "unsubscribe_from_recommendations":
                await ws_manager.unsubscribe(websocket, "recommendations")
                await websocket.send_json(
                    {
                        "type": "unsubscribed",
                        "request_id": request_id,
                        "subscription": "recommendations",
                        "container_id": container_id,
                    }
                )

            elif action == "subscribe_to_logs":
                await ws_manager.subscribe(websocket, "logs")
                await websocket.send_json(
                    {
                        "type": "subscribed",
                        "request_id": request_id,
                        "subscription": "logs",
                        "container_id": container_id,
                    }
                )

            elif action == "unsubscribe_from_logs":
                await ws_manager.unsubscribe(websocket, "logs")
                await websocket.send_json(
                    {
                        "type": "unsubscribed",
                        "request_id": request_id,
                        "subscription": "logs",
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
        cleanup_recommendations()
        cleanup_logs()
        ws_manager.disconnect(websocket)
        Logger.info("=== WebSocket cleanup done ===")
