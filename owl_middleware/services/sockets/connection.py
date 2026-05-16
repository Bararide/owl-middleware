from fastapi import WebSocket
from typing import Dict, List, Optional, Tuple
from datetime import datetime


class Connection:
    def __init__(self):
        self.container_connections: Dict[str, List[WebSocket]] = {}
        self.socket_info: Dict[WebSocket, Tuple[str, str]] = {}

    async def connect(self, websocket: WebSocket, container_id: str, user_id: str):
        self.container_connections.setdefault(container_id, []).append(websocket)
        self.socket_info[websocket] = (container_id, user_id)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.socket_info:
            cid, uid = self.socket_info.pop(websocket)
            if cid in self.container_connections:
                self.container_connections[cid].remove(websocket)
                if not self.container_connections[cid]:
                    del self.container_connections[cid]

    async def send_personal(self, websocket: WebSocket, message: dict):
        try:
            await websocket.send_json(message)
        except Exception:
            self.disconnect(websocket)

    async def broadcast_to_container(
        self, container_id: str, message: dict, exclude: Optional[WebSocket] = None
    ):
        if container_id not in self.container_connections:
            return
        disconnected = []
        for ws in self.container_connections[container_id]:
            if ws == exclude:
                continue
            try:
                await ws.send_json(message)
            except Exception:
                disconnected.append(ws)
        for ws in disconnected:
            self.disconnect(ws)
