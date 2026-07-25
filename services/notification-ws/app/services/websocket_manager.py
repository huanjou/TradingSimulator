from typing import Dict, List

import structlog
from fastapi import WebSocket

logger = structlog.get_logger()


class WebSocketManager:
    def __init__(self):
        # user_id -> list of active connections
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)
        logger.info(
            "user_connected",
            user_id=user_id,
            connections=len(self.active_connections[user_id]),
        )

    def disconnect(self, websocket: WebSocket, user_id: str):
        if user_id in self.active_connections:
            try:
                self.active_connections[user_id].remove(websocket)
                if not self.active_connections[user_id]:
                    del self.active_connections[user_id]
                logger.info("user_disconnected", user_id=user_id)
            except ValueError:
                pass

    async def send_personal_message(self, message: str, user_id: str):
        if user_id in self.active_connections:
            for connection in self.active_connections[user_id]:
                try:
                    await connection.send_text(message)
                except Exception as e:
                    logger.error(
                        "failed_to_send_message", user_id=user_id, error=str(e)
                    )
                    self.disconnect(connection, user_id)


manager = WebSocketManager()
