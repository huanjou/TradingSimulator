import structlog
from app.api.deps import get_current_user_id_ws
from app.services.websocket_manager import manager
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

logger = structlog.get_logger()

router = APIRouter()


@router.websocket("/notifications")
async def websocket_endpoint(
    websocket: WebSocket, user_id: str = Depends(get_current_user_id_ws)
):
    await manager.connect(websocket, user_id)
    try:
        while True:
            data = await websocket.receive_text()
            logger.debug("received_message", user_id=user_id, data=data)
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)
