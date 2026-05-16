from fastapi import WebSocket, WebSocketDisconnect
from fastbot.core import result_try, Result, Ok, Err
from fastbot.logger.logger import Logger
from datetime import datetime
from typing import List, Dict

import json


class Connection:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.user_connections: Dict[str, WebSocket] = {}
        self.online_users: List[str] = []
        self.message_history: List[Dict] = []
        self.max_history = 50

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections.append(websocket)
        self.user_connections[client_id] = websocket
        self.online_users.append(client_id)
        Logger.info(f"Client connected: {client_id}")

        if self.message_history:
            await websocket.send_text(
                json.dumps({"type": "history", "messages": self.message_history})
            )

        await self.broadcast_online_users()

    def disconnect(self, websocket: WebSocket, client_id: str):
        self.active_connections.remove(websocket)
        if client_id in self.user_connections:
            del self.user_connections[client_id]
        if client_id in self.online_users:
            self.online_users.remove(client_id)
        Logger.info(f"Client disconnected: {client_id}")

    async def broadcast_online_users(self):
        message = json.dumps(
            {
                "type": "users_list",
                "users": self.online_users,
                "count": len(self.online_users),
            }
        )
        await self.broadcast(message)

    async def broadcast(self, message: str):
        try:
            msg_data = json.loads(message)
            if msg_data.get("type") == "message":
                if "timestamp" not in msg_data:
                    msg_data["timestamp"] = datetime.now().isoformat()

                self.message_history.append(msg_data)
                if len(self.message_history) > self.max_history:
                    self.message_history = self.message_history[-self.max_history :]
        except:
            pass

        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                Logger.error(f"Error sending message: {e}")
                disconnected.append(connection)

        for conn in disconnected:
            if conn in self.active_connections:
                self.active_connections.remove(conn)
